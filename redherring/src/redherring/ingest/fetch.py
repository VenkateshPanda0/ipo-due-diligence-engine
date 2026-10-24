"""Polite, idempotent, integrity-checked PDF fetcher.

- identifies itself with a descriptive User-Agent
- honours robots.txt (a non-robots response, e.g. an HTML app shell, is treated as "no rules")
- rate-limits per host
- streams to a temp file, enforces a size cap, checks the %PDF magic
- detects short transfers (fewer bytes than the server announced) and resumes with HTTP Range;
  large filings are routinely cut off mid-body, and silently keeping a truncated PDF is the failure
  this guards against
- rejects files without a trailing %%EOF marker, and re-fetches cached files that fail that check
- skips documents already in the manifest whose file still matches the recorded hash
"""

from __future__ import annotations

import http.client
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from redherring.ingest.manifest import Manifest, ManifestEntry, SourceSpec, sha256_file

DEFAULT_USER_AGENT = "RedHerring-research/0.1 (+https://github.com/VenkateshPanda0)"
MAX_BYTES = 600 * 1024 * 1024
MAX_RESUMES = 8
_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)")


class FetchError(RuntimeError):
    pass


def looks_complete(path: Path) -> bool:
    """A well-formed PDF ends with %%EOF (allowing trailing padding)."""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(f.tell() - 4096, 0))
        return b"%%EOF" in f.read()


class Fetcher:
    def __init__(
        self,
        data_dir: Path,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_s: float = 3.0,
        timeout_s: float = 60.0,
        max_bytes: int = MAX_BYTES,
        max_resumes: int = MAX_RESUMES,
        opener: urllib.request.OpenerDirector | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.data_dir = data_dir
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes
        self.max_resumes = max_resumes
        self._opener = opener or urllib.request.build_opener()
        self._sleep = sleep
        self._clock = clock
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    # -- politeness -----------------------------------------------------------------------

    def _throttle(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.min_interval_s - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_hit[host] = self._clock()

    def _request(self, url: str, extra: dict[str, str] | None = None) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"User-Agent": self.user_agent, **(extra or {})})

    def _robots_for(self, scheme: str, host: str) -> RobotFileParser | None:
        key = f"{scheme}://{host}"
        if key not in self._robots:
            self._throttle(host)
            parser: RobotFileParser | None = None
            try:
                with self._opener.open(
                    self._request(f"{key}/robots.txt"), timeout=self.timeout_s
                ) as resp:
                    text = resp.read(256 * 1024).decode("utf-8", errors="replace")
                # Some sites return their HTML app shell for /robots.txt: no rules.
                if "user-agent" in text.lower() and "<html" not in text.lower()[:500]:
                    parser = RobotFileParser()
                    parser.parse(text.splitlines())
            except urllib.error.HTTPError as e:
                if e.code >= 500:  # RFC 9309: an unreachable robots.txt means "do not crawl yet"
                    raise FetchError(
                        f"{key}/robots.txt unavailable (HTTP {e.code}); not fetching"
                    ) from e
                parser = None  # 4xx: no robots.txt, no rules
            except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
                raise FetchError(f"{key}/robots.txt unreachable ({e}); not fetching") from e
            self._robots[key] = parser
        return self._robots[key]

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        robots = self._robots_for(parts.scheme, parts.netloc)
        return True if robots is None else robots.can_fetch(self.user_agent, url)

    # -- downloading ----------------------------------------------------------------------

    def _download(self, url: str, tmp: Path) -> str:
        """Stream `url` into `tmp`, resuming after cut-offs. Returns the Content-Type."""
        host = urlsplit(url).netloc
        content_type = ""
        expected: int | None = None
        resumes = 0
        tmp.unlink(missing_ok=True)
        while True:
            have = tmp.stat().st_size if tmp.exists() else 0
            self._throttle(host)
            extra = {"Range": f"bytes={have}-"} if have else None
            try:
                resp = self._opener.open(self._request(url, extra), timeout=self.timeout_s)
            except urllib.error.HTTPError as e:
                if e.code == 416 and have and expected == have:
                    return content_type  # already have every byte
                raise FetchError(f"fetching {url} failed: HTTP {e.code}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise FetchError(f"fetching {url} failed: {e}") from e

            with resp:
                content_type = content_type or resp.headers.get("Content-Type", "")
                resuming = bool(have) and resp.status == 206
                if resuming:
                    m = _CONTENT_RANGE.fullmatch(resp.headers.get("Content-Range", ""))
                    if not m or int(m.group(1)) != have:
                        raise FetchError(f"{url}: unusable Content-Range for resume at {have}")
                    if m.group(3) != "*":
                        expected = int(m.group(3))
                else:  # first request, or server ignored Range and sent the whole body again
                    have = 0
                    length = resp.headers.get("Content-Length")
                    expected = int(length) if length and length.isdigit() else expected
                size = have
                try:
                    with tmp.open("ab" if resuming else "wb") as out:
                        while chunk := resp.read(1 << 20):
                            if size == 0 and not chunk.startswith(b"%PDF-"):
                                raise FetchError(f"{url} did not return a PDF ({content_type!r})")
                            size += len(chunk)
                            if size > self.max_bytes:
                                raise FetchError(f"{url} exceeds size cap of {self.max_bytes} B")
                            out.write(chunk)
                except (http.client.HTTPException, OSError):
                    pass  # cut off mid-body; the size check below decides whether to resume

            if expected is None or size == expected:
                return content_type
            if size > expected:
                raise FetchError(f"{url}: received {size} B but server announced {expected} B")
            resumes += 1
            if resumes > self.max_resumes:
                raise FetchError(
                    f"{url}: transfer incomplete after {self.max_resumes} resumes "
                    f"({size} of {expected} B)"
                )

    # -- public ---------------------------------------------------------------------------

    def fetch(self, spec: SourceSpec, manifest: Manifest) -> tuple[ManifestEntry, bool]:
        """Return (entry, downloaded). `downloaded` is False when already present and intact."""
        existing = manifest.get(spec.doc_id)
        if existing and existing.url == spec.url:
            path = self.data_dir / existing.local_path
            if path.exists() and sha256_file(path) == existing.sha256 and looks_complete(path):
                described = spec.model_dump()
                if any(getattr(existing, k) != v for k, v in described.items()):
                    # sources.toml was corrected (a filing date, a note): the manifest follows
                    existing = existing.model_copy(update=described)
                    manifest.add(existing)
                return existing, False

        if not self.allowed(spec.url):
            raise FetchError(f"robots.txt disallows {spec.url}")

        raw_dir = self.data_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        final = raw_dir / f"{spec.doc_id}.pdf"
        tmp = final.with_suffix(".pdf.part")
        try:
            content_type = self._download(spec.url, tmp)
            size = tmp.stat().st_size if tmp.exists() else 0
            if size == 0:
                raise FetchError(f"{spec.url} returned an empty body")
            if not looks_complete(tmp):
                raise FetchError(f"{spec.url}: downloaded file has no %%EOF marker (truncated?)")
            os.replace(tmp, final)
        finally:
            tmp.unlink(missing_ok=True)

        entry = ManifestEntry(
            **spec.model_dump(),
            sha256=sha256_file(final),
            size_bytes=final.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path=str(final.relative_to(self.data_dir)),
            content_type=content_type,
        )
        manifest.add(entry)
        return entry, True

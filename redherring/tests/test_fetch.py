import threading
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from redherring.ingest.fetch import Fetcher, FetchError
from redherring.ingest.manifest import DocType, Manifest, Platform, SourceSpec, load_sources
from tests.pdfgen import PageSpec, build_pdf

PDF = build_pdf([PageSpec().text(72, 72, "hello")])
ROBOTS = b"User-agent: *\nDisallow: /blocked/\n"


class _Handler(BaseHTTPRequestHandler):
    hits: list[str] = []  # noqa: RUF012

    def _cut_first_response(self) -> None:
        """Announce the full length, send half the bytes, then drop the connection."""
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(PDF)))
        self.end_headers()
        self.wfile.write(PDF[: len(PDF) // 2])
        self.wfile.flush()
        self.close_connection = True

    def _serve_range(self, start: int) -> None:
        self.send_response(206)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Range", f"bytes {start}-{len(PDF) - 1}/{len(PDF)}")
        self.send_header("Content-Length", str(len(PDF) - start))
        self.end_headers()
        self.wfile.write(PDF[start:])

    def do_GET(self) -> None:
        _Handler.hits.append(self.path)
        range_hdr = self.headers.get("Range")
        n_prior = _Handler.hits.count(self.path) - 1
        if self.path == "/cut.pdf":  # first request cut off; Range resume supported
            if range_hdr:
                return self._serve_range(int(range_hdr.removeprefix("bytes=").rstrip("-")))
            return self._cut_first_response()
        if self.path == "/cut-ignores-range.pdf" and n_prior == 0:  # cut once, then full body
            return self._cut_first_response()
        if self.path == "/always-cut.pdf":  # never completes
            return self._cut_first_response()
        routes = {
            "/robots.txt": (200, "text/plain", ROBOTS),
            "/ok.pdf": (200, "application/pdf", PDF),
            "/cut-ignores-range.pdf": (200, "application/pdf", PDF),
            "/no-eof.pdf": (200, "application/pdf", PDF[: PDF.rindex(b"%%EOF")]),
            "/blocked/x.pdf": (200, "application/pdf", PDF),
            "/page.html": (200, "text/html", b"<html>login</html>"),
        }
        status, ctype, body = routes.get(self.path, (404, "text/plain", b"nope"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.hits = []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _spec(base: str, path: str, doc_id: str = "d1") -> SourceSpec:
    return SourceSpec(
        doc_id=doc_id,
        url=base + path,
        issuer="Test Ltd",
        doc_type=DocType.RHP,
        platform=Platform.MAINBOARD,
    )


def _fetcher(tmp_path: Path, sleeps: list[float] | None = None, **kw: object) -> Fetcher:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    clock = {"t": 0.0}

    def sleep(s: float) -> None:
        if sleeps is not None:
            sleeps.append(s)
        clock["t"] += s

    return Fetcher(
        tmp_path,
        opener=opener,
        sleep=sleep,
        clock=lambda: clock["t"],
        **kw,  # type: ignore[arg-type]
    )


def test_fetch_records_hash_and_is_idempotent(server: str, tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.jsonl")
    f = _fetcher(tmp_path)
    entry, downloaded = f.fetch(_spec(server, "/ok.pdf"), manifest)
    assert downloaded
    assert (tmp_path / entry.local_path).read_bytes() == PDF
    import hashlib

    assert entry.sha256 == hashlib.sha256(PDF).hexdigest()
    assert entry.size_bytes == len(PDF)

    n_hits = len(_Handler.hits)
    entry2, downloaded2 = f.fetch(_spec(server, "/ok.pdf"), manifest)
    assert not downloaded2
    assert entry2.sha256 == entry.sha256
    assert len(_Handler.hits) == n_hits  # no network on cache hit

    # Manifest survives reload.
    assert Manifest(tmp_path / "manifest.jsonl").get("d1") == entry


def test_refetch_when_local_file_is_corrupted(server: str, tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.jsonl")
    f = _fetcher(tmp_path)
    entry, _ = f.fetch(_spec(server, "/ok.pdf"), manifest)
    (tmp_path / entry.local_path).write_bytes(b"%PDF-tampered")
    _, downloaded = f.fetch(_spec(server, "/ok.pdf"), manifest)
    assert downloaded


def test_robots_disallow_blocks_fetch(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    with pytest.raises(FetchError, match="robots"):
        f.fetch(_spec(server, "/blocked/x.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert "/blocked/x.pdf" not in _Handler.hits


def test_non_pdf_is_rejected_and_leaves_no_file(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    with pytest.raises(FetchError, match="did not return a PDF"):
        f.fetch(_spec(server, "/page.html"), Manifest(tmp_path / "m.jsonl"))
    assert list((tmp_path / "raw").glob("*")) == []


def test_http_error_is_wrapped(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    with pytest.raises(FetchError):
        f.fetch(_spec(server, "/missing.pdf"), Manifest(tmp_path / "m.jsonl"))


def test_size_cap(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path, max_bytes=100)
    with pytest.raises(FetchError, match="size cap"):
        f.fetch(_spec(server, "/ok.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert list((tmp_path / "raw").glob("*")) == []


def test_requests_to_same_host_are_rate_limited(server: str, tmp_path: Path) -> None:
    sleeps: list[float] = []
    f = _fetcher(tmp_path, sleeps, min_interval_s=3.0)
    m = Manifest(tmp_path / "m.jsonl")
    f.fetch(_spec(server, "/ok.pdf", "a"), m)
    f.fetch(_spec(server, "/ok.pdf", "b"), m)
    assert sleeps, "second request to the same host must wait"
    assert all(0 < s <= 3.0 for s in sleeps)


def test_user_agent_is_sent(server: str, tmp_path: Path) -> None:
    seen: list[str] = []
    orig = _Handler.do_GET

    def spy(self: _Handler) -> None:
        seen.append(self.headers.get("User-Agent", ""))
        orig(self)

    _Handler.do_GET = spy  # type: ignore[method-assign]
    try:
        _fetcher(tmp_path).fetch(_spec(server, "/ok.pdf"), Manifest(tmp_path / "m.jsonl"))
    finally:
        _Handler.do_GET = orig  # type: ignore[method-assign]
    assert seen
    assert all(ua.startswith("RedHerring-research/") for ua in seen)


def test_load_sources_rejects_duplicate_ids(tmp_path: Path) -> None:
    toml = tmp_path / "s.toml"
    block = (
        '[[document]]\ndoc_id = "x"\nurl = "https://e.com/a.pdf"\nissuer = "A"\n'
        'doc_type = "rhp"\nplatform = "sme"\n'
    )
    toml.write_text(block + "\n" + block)
    with pytest.raises(ValueError, match="duplicate"):
        load_sources(toml)
    toml.write_text(block)
    (spec,) = load_sources(toml)
    assert spec.doc_type is DocType.RHP
    assert spec.platform is Platform.SME


def test_truncated_transfer_is_resumed_with_range(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    entry, downloaded = f.fetch(_spec(server, "/cut.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert downloaded
    assert (tmp_path / entry.local_path).read_bytes() == PDF
    assert entry.size_bytes == len(PDF)
    assert _Handler.hits.count("/cut.pdf") == 2  # initial request + one Range resume


def test_resume_falls_back_when_server_ignores_range(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    entry, _ = f.fetch(_spec(server, "/cut-ignores-range.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert (tmp_path / entry.local_path).read_bytes() == PDF


def test_gives_up_after_max_resumes_and_keeps_no_file(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path, max_resumes=2)
    with pytest.raises(FetchError, match="incomplete"):
        f.fetch(_spec(server, "/always-cut.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert list((tmp_path / "raw").glob("*")) == []
    assert _Handler.hits.count("/always-cut.pdf") == 3  # first try + 2 resumes


def test_file_without_eof_marker_is_rejected(server: str, tmp_path: Path) -> None:
    f = _fetcher(tmp_path)
    with pytest.raises(FetchError, match="EOF"):
        f.fetch(_spec(server, "/no-eof.pdf"), Manifest(tmp_path / "m.jsonl"))
    assert list((tmp_path / "raw").glob("*")) == []


def test_cached_truncated_file_is_refetched(server: str, tmp_path: Path) -> None:
    """A truncated file already recorded in the manifest (older buggy fetch) must not be trusted."""
    from datetime import UTC, datetime

    from redherring.ingest.manifest import ManifestEntry, sha256_file

    raw = tmp_path / "raw"
    raw.mkdir()
    bad = raw / "d1.pdf"
    bad.write_bytes(PDF[: len(PDF) // 2])
    manifest = Manifest(tmp_path / "m.jsonl")
    spec = _spec(server, "/ok.pdf")
    manifest.add(
        ManifestEntry(
            **spec.model_dump(),
            sha256=sha256_file(bad),
            size_bytes=bad.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path="raw/d1.pdf",
            content_type="application/pdf",
        )
    )
    entry, downloaded = _fetcher(tmp_path).fetch(spec, manifest)
    assert downloaded
    assert (tmp_path / entry.local_path).read_bytes() == PDF

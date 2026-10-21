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

    def do_GET(self) -> None:
        _Handler.hits.append(self.path)
        routes = {
            "/robots.txt": (200, "text/plain", ROBOTS),
            "/ok.pdf": (200, "application/pdf", PDF),
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

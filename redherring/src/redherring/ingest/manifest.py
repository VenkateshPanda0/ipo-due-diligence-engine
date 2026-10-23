"""Source specs (what to fetch) and the manifest (what was fetched, with hashes)."""

from __future__ import annotations

import hashlib
import tomllib
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class DocType(StrEnum):
    DRHP = "drhp"
    DRAFT_ABRIDGED = "draft_abridged_prospectus"
    RHP = "rhp"
    ABRIDGED = "abridged_prospectus"
    PROSPECTUS = "prospectus"
    ADDENDUM = "addendum"
    ENFORCEMENT_ORDER = "enforcement_order"
    REGULATION = "regulation"
    OTHER = "other"


class Platform(StrEnum):
    MAINBOARD = "mainboard"
    SME = "sme"


class SourceSpec(BaseModel):
    """One document to fetch, as declared in a sources TOML file."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    url: str
    issuer: str
    doc_type: DocType
    platform: Platform | None = None  # None for non-filings (regulations, orders)
    filing_date: date | None = None
    notes: str = ""


class ManifestEntry(SourceSpec):
    """A fetched document. `sha256` is of the exact bytes stored at `local_path`."""

    sha256: str
    size_bytes: int
    fetched_at: datetime
    local_path: str  # relative to the data directory
    content_type: str


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def load_sources(path: Path) -> list[SourceSpec]:
    """Read `[[document]]` tables from a TOML file."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    specs = [SourceSpec.model_validate(d) for d in raw.get("document", [])]
    ids = [s.doc_id for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate doc_id in {path}")
    return specs


class Manifest:
    """Append-only JSONL manifest keyed by doc_id (last entry wins on reload)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, ManifestEntry] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = ManifestEntry.model_validate_json(line)
                    self._entries[entry.doc_id] = entry

    def get(self, doc_id: str) -> ManifestEntry | None:
        return self._entries.get(doc_id)

    def entries(self) -> list[ManifestEntry]:
        return list(self._entries.values())

    def add(self, entry: ManifestEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        self._entries[entry.doc_id] = entry

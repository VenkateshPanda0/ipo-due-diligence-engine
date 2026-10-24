"""Ground-truth label files for the benchmark, and their validation.

One JSON file per document. A label says what the document itself states for a key (a fact the
extractor reports), where, and how it is printed. Labels are checked against the PDF text layer,
so a typo in a label cannot silently corrupt the benchmark. Drafts (`*.draft.json`, pre-filled
from the extractor, status `unreviewed`) are never read as ground truth.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 1
Status = Literal["present", "absent", "unsure", "unreviewed"]


class Label(BaseModel):
    key: str
    status: Status
    value_rupees: Decimal | None = None
    raw: str | None = Field(default=None, description="The figure exactly as printed")
    pages: list[int] = Field(default_factory=list, description="PDF pages that state it")
    span: str | None = None
    note: str = ""
    suggested_rupees: Decimal | None = Field(
        default=None, description="Draft files only: the extractor's value, to confirm or fix"
    )

    @model_validator(mode="after")
    def _shape(self) -> Label:
        if self.status == "present" and (
            self.value_rupees is None or not self.pages or not self.span
        ):
            raise ValueError(f"{self.key}: a present label needs value_rupees, pages and span")
        if self.status == "absent" and self.value_rupees is not None:
            raise ValueError(f"{self.key}: an absent label must not carry a value")
        return self


class LabelFile(BaseModel):
    schema_version: int = SCHEMA_VERSION
    doc_id: str
    doc_sha256: str
    labelled_by: str
    labelled_on: date
    method: str = Field(description="How the labels were produced, stated plainly")
    split: Literal["dev", "heldout"] = Field(
        default="dev",
        description="heldout: labelled before the extractor was run on the document and never "
        "tuned against; dev documents were used to build the extractor",
    )
    fields: list[Label]

    @model_validator(mode="after")
    def _unique_keys(self) -> LabelFile:
        keys = [f.key for f in self.fields]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"duplicate label keys: {sorted(dupes)}")
        return self


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def check_labels(file: LabelFile, page_text: Callable[[int], str]) -> list[str]:
    """Problems that make a label file unfit to score against (empty list = fine)."""
    problems: list[str] = []
    for f in file.fields:
        if f.status == "unreviewed":
            problems.append(f"{f.key}: still unreviewed")
        if f.status != "present":
            continue
        if not f.raw:
            problems.append(f"{f.key}: present label needs `raw` (the figure as printed)")
            continue
        assert f.span is not None
        if _squash(f.raw) not in _squash(f.span):
            problems.append(f"{f.key}: raw value {f.raw!r} not in the label's span")
        if not any(_squash(f.raw) in _squash(page_text(p)) for p in f.pages):
            where = ", ".join(str(p) for p in f.pages)
            noun = "page" if len(f.pages) == 1 else "pages"
            problems.append(f"{f.key}: raw value {f.raw!r} not found on cited {noun} {where}")
    return problems


def load_labels(directory: Path) -> dict[str, LabelFile]:
    """Final label files in `directory` by doc_id; `*.draft.json` files are skipped."""
    out: dict[str, LabelFile] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        file = LabelFile.model_validate_json(path.read_text(encoding="utf-8"))
        out[file.doc_id] = file
    return out

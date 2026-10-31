"""Build a label file from a short spec of values the labeller read off the PDF.

    uv run python tools/label_build.py SPEC.json [--split dev|heldout]
    uv run python tools/label_build.py SPEC.json --audit-absent

SPEC.json: {"doc_id": "...", "fields": [ {key, label, raw[, unit, value, extra_pages,
extra_raw, note]} | {key, status: "absent"|"not_applicable", note} ]}. `label` is a regex and
`raw` the figure as printed; pages and spans are found as lines carrying both (poppler text), so
a field the PDF does not contain is an error, never a guess. `--audit-absent` prints every line
that could contradict each absent label (all of them, not the first few) for the labeller to read
before committing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pg import ROOT, pages

from redherring.parse.units import MULTIPLIER, Unit, parse_amount

UNITS = {"million": Unit.MILLION, "lakh": Unit.LAKH, "crore": Unit.CRORE, "rupees": Unit.RUPEES}
AUDIT = {  # absent field family -> (pattern, last page to search)
    "objects.monitoring_agency_appointed": (r"monitoring\s+agency", 10**6),
    "objects.gcp_amount": (r"general\s+corporate\s+purposes", 10**6),
    "objects.unidentified_acquisition_amount": (r"unidentified|inorganic", 10**6),
    "issue.": (r"fresh\s+issue|offer\s+for\s+sale|aggregating", 6),
}


def _flat(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _sha(doc: str) -> str:
    for line in (ROOT / "data" / "manifest.jsonl").read_text().splitlines():
        entry = json.loads(line)
        if entry["doc_id"] == doc:
            return str(entry["sha256"])
    raise SystemExit(f"{doc} is not in data/manifest.jsonl (run rh ingest)")


def _hits(text: list[str], label: str, raw: str) -> list[tuple[int, str]]:
    pat, need = re.compile(label, re.IGNORECASE), _flat(raw)
    found: list[tuple[int, str]] = []
    for n, page in enumerate(text, 1):
        for line in page.splitlines():
            if pat.search(line) and need in _flat(line):
                found.append((n, re.sub(r"\s+", " ", line.strip())))
                break
    return found


def _field(text: list[str], doc: str, spec: dict[str, str | list[int]]) -> dict[str, object]:
    key, status = str(spec["key"]), str(spec.get("status", "present"))
    if status != "present":
        return {"key": key, "status": status, "note": spec.get("note", "")}
    raw, label = str(spec["raw"]), str(spec["label"])
    hits = _hits(text, label, raw)
    primary = hits[0] if hits else None
    for n in spec.get("extra_pages", []):
        extra = _flat(str(spec.get("extra_raw", raw)))
        if extra not in _flat(text[int(n) - 1]):
            raise SystemExit(f"{doc} {key}: {raw!r} not on extra page {n}")
        if int(n) not in [h[0] for h in hits]:
            hits.append((int(n), ""))
    if not hits or primary is None:
        raise SystemExit(f"{doc} {key}: no line with /{label}/ and {raw!r}")
    unit = str(spec.get("unit", "million"))
    value = parse_amount(raw)
    if value is None:
        if "value" not in spec:
            raise SystemExit(f'{doc} {key}: {raw!r} is not an amount; give "value" and unit none')
        value = Decimal(str(spec["value"]))  # a yes/no fact (1 or 0)
    elif unit != "none":
        value = value * MULTIPLIER[UNITS[unit]]
    return {
        "key": key,
        "status": "present",
        "value_rupees": str(value),
        "raw": raw,
        "pages": sorted({h[0] for h in hits}),
        "span": primary[1][:240],
        "note": spec.get("note", ""),
    }


def audit_absent(text: list[str], spec: dict[str, object]) -> None:
    for f in spec["fields"]:  # type: ignore[attr-defined]
        if f.get("status") != "absent":
            continue
        for prefix, (pattern, last) in AUDIT.items():
            if f["key"].startswith(prefix):
                print(f"\n## {f['key']}  (labelled absent: {f.get('note', '')})")
                pat = re.compile(pattern, re.IGNORECASE)
                for n, page in enumerate(text[:last], 1):
                    for line in page.splitlines():
                        if pat.search(line):
                            print(f"  p{n}: {re.sub(r'\s+', ' ', line.strip())[:170]}")
                break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--split", default="dev", choices=["dev", "heldout"])
    ap.add_argument("--audit-absent", action="store_true")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    doc = spec["doc_id"]
    text = pages(doc)
    if args.audit_absent:
        audit_absent(text, spec)
        return
    out = {
        "schema_version": 1,
        "doc_id": doc,
        "doc_sha256": _sha(doc),
        "labelled_by": "maintainer (an AI) reading the PDF text; not independent human labelling",
        "labelled_on": str(date.today()),
        "split": args.split,
        "method": (
            "Each value was read from the cited page of the PDF (poppler pdftotext, a different "
            "extraction path from the extractor) and typed in; pages/spans were then located "
            "mechanically as lines carrying both the concept wording and the figure. No "
            "inter-annotator agreement has been measured. "
        ),
        "fields": [_field(text, doc, f) for f in spec["fields"]],
    }
    path = ROOT / "labels" / f"{doc}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{doc}: {len(out['fields'])} labels -> {path}")


if __name__ == "__main__":
    main()

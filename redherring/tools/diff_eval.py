"""Per-field comparison of labels and predictions: only the misses are printed.

python tools/diff_eval.py DOC [DOC ...]    (run from redherring/, after `rh analyze`)
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(docs: list[str]) -> None:
    for d in docs:
        labels = {
            f["key"]: f for f in json.loads((ROOT / "labels" / f"{d}.json").read_text())["fields"]
        }
        out = json.loads((ROOT / "data" / "extracted" / f"{d}.financials.json").read_text())
        facts = {f["key"]: f for f in out["facts"]}
        print(f"\n== {d}")
        for key, lab in labels.items():
            pred = facts.get(key)
            if lab["status"] == "present":
                want = Decimal(lab["value_rupees"])
                if pred is None:
                    tag = "MISS (abstained)"
                elif abs(Decimal(pred["value"]) - want) <= max(abs(want) * Decimal("0.0005"), 1):
                    if pred["pdf_page"] in lab["pages"]:
                        continue
                    tag = f"ok  (page {pred['pdf_page']} not in {lab['pages']})"
                else:
                    tag = f"WRONG pred={pred['value']} p{pred['pdf_page']}"
                print(f"  {key:46s} label={want:>16,.0f}  {tag}")
            elif lab["status"] == "absent" and pred is not None:
                print(f"  {key:46s} HALLUCINATION pred={pred['value']} p{pred['pdf_page']}")


if __name__ == "__main__":
    main(sys.argv[1:])

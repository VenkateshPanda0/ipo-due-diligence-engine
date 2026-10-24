"""Score predictions against labels: value accuracy, citation accuracy, hallucination, abstention.

Definitions (all over *labelled* fields; `unsure` labels are not scored):
- value accuracy      correct / present labels (a prediction within tolerance of the label)
- citation accuracy   of the correct values, the share whose cited page is one of the label's
- abstention rate     present labels with no prediction / present labels
- hallucination rate  absent labels with a prediction / absent labels (the document states no such
                      value, yet one was reported)
Tolerance: the coarser of the two printed precisions. A label printed as "2,239.15" (million) is
exact to 10,000 rupees; a prediction read from a table printing whole millions is exact to
1,000,000. Two different line items a hair apart (2,239.30 vs 2,239.15) are therefore not a match.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from pydantic import BaseModel, computed_field

from redherring.eval.labels import Label, LabelFile
from redherring.parse.units import parse_amount


class Prediction(BaseModel):
    key: str
    value: Decimal
    pdf_page: int
    span: str
    step: Decimal = Decimal(1)  # printed precision in rupees (0.01 million = 10,000)


def label_step(f: Label) -> Decimal:
    """Printed precision of a label in rupees, from its raw text and rupee value."""
    if f.raw and f.value_rupees:
        parsed = parse_amount(f.raw)
        match = re.search(r"\.(\d+)", f.raw)
        if parsed:
            quantum = Decimal(1).scaleb(-len(match.group(1))) if match else Decimal(1)
            return quantum * abs(f.value_rupees / parsed)
    return Decimal(1)


def family_of(key: str) -> str:
    """'financials.total_income.FY2026' -> 'financials.total_income'; other keys unchanged."""
    parts = key.split(".")
    return ".".join(parts[:2]) if parts[0] == "financials" and len(parts) == 3 else key


class _Counts(BaseModel):
    n_present: int = 0
    n_absent: int = 0
    correct: int = 0
    wrong: int = 0
    abstained: int = 0
    hallucinated: int = 0
    correct_abstentions: int = 0
    citation_correct: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def n_labelled(self) -> int:
        return self.n_present + self.n_absent

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_accuracy(self) -> float | None:
        return self.correct / self.n_present if self.n_present else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def citation_accuracy(self) -> float | None:
        return self.citation_correct / self.correct if self.correct else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def abstention_rate(self) -> float | None:
        return self.abstained / self.n_present if self.n_present else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hallucination_rate(self) -> float | None:
        return self.hallucinated / self.n_absent if self.n_absent else None


class FamilyScore(_Counts):
    family: str


class EvalReport(_Counts):
    families: list[FamilyScore]


def _within(pred: Prediction, label: Label) -> bool:
    assert label.value_rupees is not None
    return abs(pred.value - label.value_rupees) <= max(label_step(label), pred.step)


def score(labels: dict[str, LabelFile], predictions: dict[str, list[Prediction]]) -> EvalReport:
    total = _Counts()
    by_family: dict[str, _Counts] = defaultdict(_Counts)
    for doc_id, file in labels.items():
        by_key = {p.key: p for p in predictions.get(doc_id, [])}
        for f in file.fields:
            if f.status not in ("present", "absent"):
                continue
            fam = by_family[family_of(f.key)]
            pred = by_key.get(f.key)
            for c in (total, fam):
                if f.status == "present":
                    assert f.value_rupees is not None
                    c.n_present += 1
                    if pred is None:
                        c.abstained += 1
                    elif _within(pred, f):
                        c.correct += 1
                        c.citation_correct += pred.pdf_page in f.pages
                    else:
                        c.wrong += 1
                else:
                    c.n_absent += 1
                    if pred is None:
                        c.correct_abstentions += 1
                    else:
                        c.hallucinated += 1
    families = [FamilyScore(family=k, **v.model_dump()) for k, v in sorted(by_family.items())]
    return EvalReport(**total.model_dump(), families=families)

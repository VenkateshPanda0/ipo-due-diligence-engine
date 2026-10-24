"""Run extraction and every deterministic check over one parsed document."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from redherring.extract.consensus import Consensus, build_consensus
from redherring.extract.financials import extract_financials
from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import period_key
from redherring.parse.models import ParsedDocument
from redherring.verify.cited import PdfiumPageText, check_cited_number
from redherring.verify.footing import FootingCheck, run_footing


class VerifiedNumber(CitedNumber):
    verified: bool
    failures: list[str]


class FootingRecord(BaseModel):
    name: str
    table_id: int
    period_key: str
    expected: Decimal
    actual: Decimal
    tolerance: Decimal
    ok: bool


class ConsensusRecord(BaseModel):
    concept: Concept
    period_key: str
    chosen_raw: str
    chosen_page: int
    chosen_rupees: Decimal | None
    supporters: int
    total: int
    unanimous: bool
    alternatives_raw: list[str]


class Summary(BaseModel):
    doc_id: str
    values_total: int
    values_verified: int
    footing_checked: int
    footing_passed: int
    consensus_groups: int
    consensus_multi_source: int  # groups with at least two values
    consensus_unanimous_multi: int  # of those, groups where every value agrees
    values_without_period: int
    values_without_unit: int
    concepts: dict[str, int]


class AnalysisReport(BaseModel):
    summary: Summary
    values: list[VerifiedNumber]
    footing: list[FootingRecord]
    consensus: list[ConsensusRecord]


def _footing_record(c: FootingCheck) -> FootingRecord:
    return FootingRecord(**c.__dict__)


def _consensus_record(c: Consensus) -> ConsensusRecord:
    return ConsensusRecord(
        concept=c.concept,
        period_key=c.period_key,
        chosen_raw=c.chosen.raw,
        chosen_page=c.chosen.pdf_page,
        chosen_rupees=c.chosen.rupees,
        supporters=c.supporters,
        total=c.total,
        unanimous=c.unanimous,
        alternatives_raw=[a.raw for a in c.alternatives],
    )


def analyze_document(doc: ParsedDocument, pdf_path: Path) -> AnalysisReport:
    values = extract_financials(doc)
    with PdfiumPageText(pdf_path) as page_text:
        verified = []
        for v in values:
            res = check_cited_number(v, page_text)
            verified.append(VerifiedNumber(**v.model_dump(), verified=res.ok, failures=res.reasons))
    footing = run_footing(values)
    consensus = build_consensus(values)
    multi = [c for c in consensus if c.total >= 2]
    summary = Summary(
        doc_id=doc.doc_id,
        values_total=len(values),
        values_verified=sum(v.verified for v in verified),
        footing_checked=len(footing),
        footing_passed=sum(c.ok for c in footing),
        consensus_groups=len(consensus),
        consensus_multi_source=len(multi),
        consensus_unanimous_multi=sum(c.unanimous for c in multi),
        values_without_period=sum(v.period is None for v in values),
        values_without_unit=sum(v.unit is None for v in values),
        concepts=dict(Counter(v.concept.value for v in values)),
    )
    return AnalysisReport(
        summary=summary,
        values=verified,
        footing=[_footing_record(c) for c in footing],
        consensus=[_consensus_record(c) for c in consensus],
    )


def coverage(report: AnalysisReport, concept: Concept) -> list[str]:
    """Period keys for which `concept` has a consensus value, oldest first."""
    keys = {c.period_key for c in report.consensus if c.concept is concept}
    return sorted(keys)


__all__ = ["AnalysisReport", "analyze_document", "coverage", "period_key"]

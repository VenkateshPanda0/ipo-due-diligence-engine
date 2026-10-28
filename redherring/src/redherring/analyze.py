"""Run extraction and every deterministic check over one parsed document."""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from redherring.extract.consensus import Consensus, build_consensus, drop_ambiguous
from redherring.extract.financials import extract_financials
from redherring.extract.issue import IssueFact, extract_issue_facts
from redherring.extract.models import CitedNumber, Concept
from redherring.extract.periods import period_key
from redherring.extract.sector import SectorEvidence, detect_sectors
from redherring.flags.engine import Flag, RuleAudit, audit, evaluate, load_rules
from redherring.flags.facts import facts_from
from redherring.parse.models import ParsedDocument
from redherring.verify.cited import PdfiumPageText, check_cited_number, check_evidence
from redherring.verify.footing import FootingCheck, run_footing, trusted_columns

# Bump when AnalysisReport changes shape or meaning; older files are refused with a clear message.
ANALYSIS_VERSION = 21

# A page is reported as carrying invisible text from this many white-on-nothing characters up: a
# sentence worth planting is longer, while chart labels and the odd figure on a coloured shape that
# the parser did not recognise as one (11, 9 and 3 characters on nine sampled pages) stay below.
INVISIBLE_PAGE_THRESHOLD = 15


class VerifiedNumber(CitedNumber):
    verified: bool
    failures: list[str]


class VerifiedIssueFact(IssueFact):
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


class FactRecord(BaseModel):
    """A figure that reached the rules (and the benchmark): value in rupees, with its evidence."""

    key: str
    value: Decimal
    step: Decimal  # printed precision in rupees
    pdf_page: int
    span: str


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
    issue_facts_total: int
    issue_facts_verified: int
    values_ambiguous_dropped: int
    flags: int
    rules_decisive: int  # rules that could be evaluated (flagged or clear)
    rules_applicable: int  # rules in force for this platform and date


class AnalysisReport(BaseModel):
    analysis_version: int = 0  # 0 = written before versioning
    summary: Summary
    values: list[VerifiedNumber]
    issue_facts: list[VerifiedIssueFact]
    footing: list[FootingRecord]
    consensus: list[ConsensusRecord]
    facts: list[FactRecord]
    sectors: list[SectorEvidence] = []
    # pages whose text layer holds characters a reader of the page cannot see (see parse.pdf)
    pages_with_hidden_text: list[int] = []
    facts_held_back_hidden_text: list[str] = []  # keys kept out of the rules for that reason
    flags: list[Flag]
    rule_audit: list[RuleAudit]


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


def _hidden_pages(doc: ParsedDocument) -> set[int]:
    return {
        pg.pdf_page
        for pg in doc.pages
        if pg.hidden_chars_removed or pg.invisible_chars >= INVISIBLE_PAGE_THRESHOLD
    }


def analyze_document(
    doc: ParsedDocument,
    pdf_path: Path,
    *,
    platform: str | None = None,
    as_of: date | None = None,
) -> AnalysisReport:
    """Extract, verify against the PDF text layer, cross-check, and run the rules.

    Only facts that pass the PDF re-check reach the consensus and the rules, so a flag can never
    rest on a number that is not on the page it cites.
    """
    values = extract_financials(doc)
    issue = extract_issue_facts(doc)
    with PdfiumPageText(pdf_path) as page_text:
        verified: list[VerifiedNumber] = []
        for v in values:
            res = check_cited_number(v, page_text)
            verified.append(VerifiedNumber(**v.model_dump(), verified=res.ok, failures=res.reasons))
        verified_issue: list[VerifiedIssueFact] = []
        for f in issue:
            reasons: list[str] = []
            for part in f.parts or [f.raw]:  # a sum is verified part by part
                reasons += check_evidence(part, f.span, f.pdf_page, page_text).reasons
            verified_issue.append(
                VerifiedIssueFact(**f.model_dump(), verified=not reasons, failures=reasons)
            )
    good_values = [v for v, vv in zip(values, verified, strict=True) if vv.verified]
    footing = run_footing(good_values)
    unambiguous, ambiguous_dropped = drop_ambiguous(good_values)
    consensus = build_consensus(unambiguous, trusted_columns(footing), n_pages=doc.n_pages)
    multi = [c for c in consensus if c.total >= 2]
    good_issue = [f for f, vf in zip(issue, verified_issue, strict=True) if vf.verified]
    hidden_pages = _hidden_pages(doc)
    facts = facts_from(consensus, good_issue)
    # A rule must not rest on text a reader cannot see: a fact whose every citation sits on such a
    # page is kept out of the rules (it still appears in the report, marked).
    held_back = sorted(
        k
        for k, f in facts.items()
        if f.citations and all(c.pdf_page in hidden_pages for c in f.citations)
    )
    facts = {k: f for k, f in facts.items() if k not in held_back}
    sectors = detect_sectors(doc)
    flags: list[Flag] = []
    rule_audit: list[RuleAudit] = []
    if platform is not None:
        rules = load_rules()
        found = {s.sector for s in sectors}
        flags = evaluate(rules, facts, platform=platform, as_of=as_of, sectors=found)
        rule_audit = audit(rules, facts, platform=platform, as_of=as_of, sectors=found)
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
        issue_facts_total=len(issue),
        issue_facts_verified=sum(f.verified for f in verified_issue),
        values_ambiguous_dropped=ambiguous_dropped,
        flags=len(flags),
        rules_decisive=sum(a.status in ("flagged", "clear") for a in rule_audit),
        rules_applicable=sum(
            a.status not in ("other_platform", "not_in_force", "not_applicable") for a in rule_audit
        ),
    )
    return AnalysisReport(
        analysis_version=ANALYSIS_VERSION,
        summary=summary,
        values=verified,
        issue_facts=verified_issue,
        footing=[_footing_record(c) for c in footing],
        consensus=[_consensus_record(c) for c in consensus],
        facts=[
            FactRecord(
                key=k,
                value=f.value,
                step=f.step,
                pdf_page=f.citations[0].pdf_page,
                span=f.citations[0].span,
            )
            for k, f in sorted(facts.items())
        ],
        sectors=sectors,
        pages_with_hidden_text=sorted(hidden_pages),
        facts_held_back_hidden_text=held_back,
        flags=flags,
        rule_audit=rule_audit,
    )


def coverage(report: AnalysisReport, concept: Concept) -> list[str]:
    """Period keys for which `concept` has a consensus value, oldest first."""
    keys = {c.period_key for c in report.consensus if c.concept is concept}
    return sorted(keys)


__all__ = ["AnalysisReport", "analyze_document", "coverage", "period_key"]

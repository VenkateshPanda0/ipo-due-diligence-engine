"""
Stages F–I — semantic field extraction, candidate ranking, normalisation and
validation for fiscal-year financial fields.

Scoring (0–1, documented in docs/DOCUMENT_INTELLIGENCE.md):

  0.35 × label strength (lexicon)
  0.20 × source quality (native table 1.0; OCR scaled by word confidence)
  0.15 × unit evidence (header/caption 1.0, page heading 0.8, none 0)
  0.10 × period quality (12-month period 1.0, stub 0.7)
  0.10 × statement basis (consolidated 1.0, unknown 0.6, standalone 0.5)
  0.10 × section context (eligibility / restated / summary tables)

Candidates are clustered by normalised value with a tolerance derived from the
printed precision, so the same figure printed in lakhs and in millions agrees.
Consolidated figures are preferred to standalone ones; they are different facts,
not conflicts. Disagreeing clusters with comparable scores are reported as
CONFLICTING_CANDIDATES and never silently resolved.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from decimal import Decimal

from app.intelligence.lexicon import match_label
from app.intelligence.numbers import UNIT_TO_CRORE
from app.intelligence.tables import FinancialTable
from app.models.enums import FieldStatus
from app.models.field_paths import fiscal_year_path

CRITICAL_FIELDS = frozenset(
    {"net_tangible_assets", "monetary_assets", "operating_profit", "net_worth"}
)
_SECTION_RE = re.compile(
    r"eligib|regulation 6|restated|summary (?:of )?(?:restated )?financial|financial information",
    re.I,
)
_HIGH_THRESHOLD = 0.72
_CRITICAL_HIGH_THRESHOLD = 0.78
_CONFLICT_MARGIN = 0.15


@dataclass
class Candidate:
    field_path: str
    field: str
    value: Decimal | None  # normalised ₹ crore; None when the unit is unknown
    raw_value: Decimal | None
    original_text: str
    original_unit: str | None
    unit_source: str | None
    page: int
    period_label: str
    period_end: str | None
    months: int
    basis: str | None
    method: str  # "table_geometric" | "table_vector" | "table_ocr"
    label: str
    raw_label: str
    context: str
    table_id: str
    ocr_conf: float | None
    score: float = 0.0
    components: dict[str, float] = dc_field(default_factory=dict)
    warnings: list[str] = dc_field(default_factory=list)
    is_null: bool = False

    def tolerance(self) -> Decimal:
        """Half a unit of the last printed decimal place, in ₹ crore."""
        digits = self.original_text.split(".")[1] if "." in self.original_text else ""
        places = len(re.sub(r"\D", "", digits))
        factor = UNIT_TO_CRORE.get(self.original_unit or "INR_CRORE", Decimal(1))
        return (Decimal(5) / Decimal(10) ** (places + 1)) * factor

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        for key in ("value", "raw_value"):
            d[key] = None if d[key] is None else str(d[key])
        return d


def _score(c: Candidate, label_strength: float, table: FinancialTable) -> None:
    source = 1.0 if c.ocr_conf is None else max(0.2, min(1.0, c.ocr_conf / 100))
    unit = {"header": 1.0, "caption": 1.0, "page_heading": 0.8}.get(c.unit_source or "", 0.0)
    period = 1.0 if c.months == 12 else 0.7
    basis = {"consolidated": 1.0, "standalone": 0.5}.get(c.basis or "", 0.6)
    section = 1.0 if _SECTION_RE.search(table.title or "") else 0.5
    comps = {
        "label": 0.35 * label_strength,
        "source": 0.20 * source,
        "unit": 0.15 * unit,
        "period": 0.10 * period,
        "basis": 0.10 * basis,
        "section": 0.10 * section,
    }
    c.components = {k: round(v, 4) for k, v in comps.items()}
    c.score = round(sum(comps.values()), 4)


def generate(tables: list[FinancialTable]) -> list[Candidate]:
    """Turn matched table rows into candidates (one per field × period)."""
    out: list[Candidate] = []
    for table in tables:
        period_by_label = {c.period.label: c.period for c in table.columns}
        for row in table.rows:
            match = match_label(row.raw_label)
            if match is None:
                continue
            for period_label, cell in row.values.items():
                period = period_by_label[period_label]
                raw = cell.parsed.value
                warnings = list(cell.parsed.warnings)
                value: Decimal | None = None
                if cell.parsed.is_percent:
                    continue  # a percentage is never an amount
                if raw is not None and table.unit is not None:
                    value = raw * UNIT_TO_CRORE[table.unit]
                elif raw is not None:
                    warnings.append(
                        "monetary unit not declared near the table; value not normalised"
                    )
                method = "table_ocr" if table.ocr else f"table_{table.method}"
                c = Candidate(
                    field_path=fiscal_year_path(period_label, match.field),
                    field=match.field,
                    value=value,
                    raw_value=raw,
                    original_text=cell.text,
                    original_unit=table.unit,
                    unit_source=table.unit_source,
                    page=row.page,
                    period_label=period_label,
                    period_end=period.end.isoformat() if period.end else None,
                    months=period.months,
                    basis=table.basis,
                    method=method,
                    label=match.label,
                    raw_label=row.raw_label,
                    context=(f"{table.title} | {row.line_text}" if table.title else row.line_text)[
                        :500
                    ],
                    table_id=table.table_id,
                    ocr_conf=cell.conf,
                    warnings=warnings,
                    is_null=cell.parsed.is_null_marker,
                )
                _score(c, match.strength, table)
                out.append(c)
    return out


@dataclass
class FieldDecision:
    field_path: str
    status: FieldStatus
    selected: Candidate | None
    candidates: list[Candidate]
    reason: str
    agreement: int = 0


def _cluster(cands: list[Candidate]) -> list[list[Candidate]]:
    clusters: list[list[Candidate]] = []
    for c in sorted(cands, key=lambda x: -x.score):
        assert c.value is not None
        for cl in clusters:
            ref = cl[0]
            assert ref.value is not None
            if abs(ref.value - c.value) <= max(ref.tolerance(), c.tolerance()) + Decimal(
                "0.000001"
            ):
                cl.append(c)
                break
        else:
            clusters.append([c])
    return clusters


def _cluster_score(cl: list[Candidate]) -> float:
    distinct_sources = len({(c.table_id, c.method) for c in cl})
    return max(c.score for c in cl) + min(0.1, 0.05 * (distinct_sources - 1))


def decide(field_path: str, cands: list[Candidate]) -> FieldDecision:
    """Select a value for one field path, or abstain / flag a conflict."""
    usable = [c for c in cands if c.value is not None and not c.is_null]
    if not usable:
        if any(c.raw_value is not None for c in cands):
            return FieldDecision(
                field_path,
                FieldStatus.EXTRACTED_NEEDS_VERIFICATION,
                None,
                cands,
                "Value found but its monetary unit could not be determined.",
            )
        if any(c.is_null for c in cands):
            return FieldDecision(
                field_path,
                FieldStatus.NOT_FOUND,
                None,
                cands,
                "Source shows a dash / 'NA' for this period (no value; not treated as zero).",
            )
        return FieldDecision(field_path, FieldStatus.NOT_FOUND, None, cands, "No candidate found.")
    # Prefer consolidated, then unknown basis, then standalone; other bases kept as alternatives.
    for basis_group in ("consolidated", None, "standalone"):
        group = [c for c in usable if c.basis == basis_group]
        if group:
            break
    clusters = sorted(_cluster(group), key=_cluster_score, reverse=True)
    best = clusters[0]
    top = max(best, key=lambda c: c.score)
    best_score = _cluster_score(best)
    rivals = [cl for cl in clusters[1:] if _cluster_score(cl) >= best_score - _CONFLICT_MARGIN]
    distinct_sources = len({(c.table_id, c.method) for c in best})
    if rivals:
        others = ", ".join(f"{cl[0].value:.4f} Cr (p.{cl[0].page})" for cl in rivals[:3])
        return FieldDecision(
            field_path,
            FieldStatus.CONFLICTING_CANDIDATES,
            top,
            cands,
            f"Comparable candidates disagree: {top.value:.4f} Cr vs {others}.",
            distinct_sources,
        )
    threshold = _CRITICAL_HIGH_THRESHOLD if top.field in CRITICAL_FIELDS else _HIGH_THRESHOLD
    strong = best_score >= threshold and top.unit_source is not None and top.ocr_conf is None
    corroborated = distinct_sources >= 2 or top.components.get("section", 0) >= 0.1
    if strong and corroborated:
        return FieldDecision(
            field_path,
            FieldStatus.EXTRACTED_HIGH_CONFIDENCE,
            top,
            cands,
            f"Selected (score {best_score:.2f}, {distinct_sources} source(s)).",
            distinct_sources,
        )
    reasons = []
    if top.ocr_conf is not None:
        reasons.append("value read by OCR")
    if best_score < threshold:
        reasons.append(f"score {best_score:.2f} below {threshold:.2f}")
    if not corroborated:
        reasons.append(
            "single uncorroborated source outside a recognised financial-summary section"
        )
    return FieldDecision(
        field_path,
        FieldStatus.EXTRACTED_NEEDS_VERIFICATION,
        top,
        cands,
        "Needs verification: " + "; ".join(reasons) + ".",
        distinct_sources,
    )


def validate(decisions: dict[str, FieldDecision]) -> list[str]:
    """Cross-field checks; failing checks downgrade the fields involved (never reject)."""
    notes: list[str] = []
    by_period: dict[str, dict[str, FieldDecision]] = {}
    for d in decisions.values():
        if d.selected is not None:
            by_period.setdefault(d.selected.period_label, {})[d.selected.field] = d

    def val(p: dict[str, FieldDecision], f: str) -> Decimal | None:
        d = p.get(f)
        return None if d is None or d.selected is None else d.selected.value

    def downgrade(d: FieldDecision, note: str) -> None:
        if d.status == FieldStatus.EXTRACTED_HIGH_CONFIDENCE:
            d.status = FieldStatus.EXTRACTED_NEEDS_VERIFICATION
        d.reason += f" Validation: {note}"
        notes.append(f"{d.field_path}: {note}")

    for period, fields in by_period.items():
        ta = val(fields, "total_assets")
        for f in ("net_tangible_assets", "monetary_assets"):
            v = val(fields, f)
            if ta is not None and v is not None and v > ta * Decimal("1.001"):
                downgrade(fields[f], f"{f} exceeds total assets in {period}")
        mon, nta = val(fields, "monetary_assets"), val(fields, "net_tangible_assets")
        if mon is not None and mon < 0:
            downgrade(fields["monetary_assets"], "negative monetary assets")
        if mon is not None and nta is not None and nta > 0 and mon > nta * 5:
            downgrade(
                fields["monetary_assets"], "monetary assets implausibly large relative to NTA"
            )
        nw, cap, res = (
            val(fields, "net_worth"),
            val(fields, "paid_up_capital"),
            val(fields, "reserves_and_surplus"),
        )
        if (
            nw is not None
            and cap is not None
            and res is not None
            and nw != 0
            and abs((cap + res) - nw) / abs(nw) > Decimal("0.05")
        ):
            # Net worth (Reg 2(1)(hh)) can legitimately differ from total equity; warn only.
            fields["net_worth"].reason += (
                " Note: share capital + other equity differs from net worth by more than 5% "
                "(may be legitimate: Reg 2(1)(hh) exclusions)."
            )
        rev = val(fields, "revenue")
        if rev is not None and rev < 0:
            downgrade(fields["revenue"], "negative revenue")
    return notes

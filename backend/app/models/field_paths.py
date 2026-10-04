"""
Field-path addressing for CompanyData payloads.

Paths are dotted, with fiscal years addressed by label:

    identification.company_name
    issue_details.issue_size
    governance.audit_committee.total_members
    declarations.debarred_by_sebi
    financials.fiscal_years[FY2024].net_worth

Paths operate on the JSON payload (``CompanyData.model_dump(mode="json")``) so that
data versions can be stored and patched without losing provenance metadata.
"""

from __future__ import annotations

import calendar
import copy
import re
from datetime import date
from typing import Any

_FY_RE = re.compile(r"^financials\.fiscal_years\[(?P<label>[^\]]+)\]\.(?P<field>[a-z_]+)$")

FISCAL_YEAR_FIELDS: tuple[str, ...] = (
    "revenue",
    "operating_profit",
    "pat",
    "net_worth",
    "net_tangible_assets",
    "monetary_assets",
    "total_assets",
    "total_liabilities",
    "paid_up_capital",
    "reserves_and_surplus",
    "ebitda",
)

#: Every addressable ExtractedValue field outside fiscal years, with its value type.
SCALAR_FIELDS: dict[str, str] = {
    "promoter.holding_percentage": "decimal",
    "promoter.post_issue_holding": "decimal",
    "promoter.eligible_non_promoter_contribution": "decimal",
    "promoter.lock_in_months": "int",
    "governance.total_directors": "int",
    "governance.independent_directors": "int",
    "governance.is_chair_executive": "bool",
    "governance.is_chair_promoter": "bool",
    "governance.audit_committee.total_members": "int",
    "governance.audit_committee.independent_members": "int",
    "governance.audit_committee.chair_is_independent": "bool",
    "issue_details.issue_size": "decimal",
    "issue_details.post_issue_paid_up_capital": "decimal",
    "issue_details.expected_market_cap": "decimal",
    "issue_details.public_offer_percentage": "decimal",
    "issue_details.qib_net_offer_allocation": "decimal",
    "litigation.total_exposure": "decimal",
    "litigation.has_criminal_cases": "bool",
    "rpt.total_rpt_value": "decimal",
    "rpt.arm_length_certified": "bool",
    "auditor.has_qualifications": "bool",
    "auditor.has_modified_opinion": "bool",
    "auditor.years_as_auditor": "int",
    "declarations.debarred_by_sebi": "bool",
    "declarations.promoter_or_director_of_debarred_company": "bool",
    "declarations.wilful_defaulter_or_fraudulent_borrower": "bool",
    "declarations.fugitive_economic_offender": "bool",
    "declarations.outstanding_convertibles_not_exempt": "bool",
    "declarations.name_changed_within_last_year": "bool",
    "declarations.revenue_pct_from_new_name_activity": "decimal",
}


_FY_LABEL_RE = re.compile(r"^FY(\d{4})$")
_YE_LABEL_RE = re.compile(r"^YE(\d{4})-(\d{2})$")
_STUB_LABEL_RE = re.compile(r"^P(\d{4})-(\d{2})-(\d{2})-\d+M$")


def period_end_from_label(label: str) -> date | None:
    """Period end implied by a canonical label (FY2024, YE2024-12, P2024-09-30-6M)."""
    try:
        if m := _FY_LABEL_RE.match(label):
            return date(int(m[1]), 3, 31)
        if m := _YE_LABEL_RE.match(label):
            year, month = int(m[1]), int(m[2])
            return date(year, month, calendar.monthrange(year, month)[1])
        if m := _STUB_LABEL_RE.match(label):
            return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:  # e.g. month 13
        return None
    return None


def period_sort_key(label: str, period_end: date | str | None) -> tuple[int, str]:
    """Chronological sort key: stored period end, else the end implied by the label.

    Periods whose end cannot be determined sort after dated ones, by label.
    """
    end = period_end if isinstance(period_end, date) else None
    if isinstance(period_end, str):
        try:
            end = date.fromisoformat(period_end)
        except ValueError:
            end = None
    end = end or period_end_from_label(label)
    return (end.toordinal(), label) if end else (date.max.toordinal(), label)


class FieldPathError(ValueError):
    """Raised for an unknown or malformed field path."""


def fiscal_year_path(label: str, field: str) -> str:
    return f"financials.fiscal_years[{label}].{field}"


def value_type(path: str) -> str:
    """Return 'decimal' | 'int' | 'bool' for an addressable path."""
    m = _FY_RE.match(path)
    if m:
        if m.group("field") not in FISCAL_YEAR_FIELDS:
            raise FieldPathError(f"Unknown fiscal-year field in '{path}'.")
        return "decimal"
    if path in SCALAR_FIELDS:
        return SCALAR_FIELDS[path]
    raise FieldPathError(f"Unknown field path '{path}'.")


def get_value(payload: dict[str, Any], path: str) -> Any:
    """Return the ExtractedValue dict at ``path`` (or None)."""
    value_type(path)
    m = _FY_RE.match(path)
    if m:
        for fy in payload.get("financials", {}).get("fiscal_years", []):
            if fy.get("year_label") == m.group("label"):
                return fy.get(m.group("field"))
        return None
    node: Any = payload
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def set_value(
    payload: dict[str, Any],
    path: str,
    value: dict[str, Any] | None,
    *,
    period_end: str | None = None,
) -> dict[str, Any]:
    """Return a deep copy of ``payload`` with ``path`` set to ``value``.

    A missing fiscal year is created (unless ``value`` is None) and the list is
    re-sorted chronologically (see :func:`period_sort_key`).
    """
    out = copy.deepcopy(payload)
    set_value_in_place(out, path, value, period_end=period_end)
    return out


def set_value_in_place(
    payload: dict[str, Any],
    path: str,
    value: dict[str, Any] | None,
    *,
    period_end: str | None = None,
) -> None:
    """Like :func:`set_value` but mutates ``payload`` (for callers that own it)."""
    value_type(path)
    m = _FY_RE.match(path)
    if m:
        fin = payload.setdefault("financials", {})
        years: list[dict[str, Any]] = fin.setdefault("fiscal_years", [])
        target = next((fy for fy in years if fy.get("year_label") == m.group("label")), None)
        if target is None:
            if value is None:
                return  # clearing a field of a year that does not exist: no-op
            target = {"year_label": m.group("label"), "months": 12}
            if period_end:
                target["period_end"] = period_end
            years.append(target)
            years.sort(key=lambda fy: period_sort_key(fy["year_label"], fy.get("period_end")))
        target[m.group("field")] = value
        return
    parts = path.split(".")
    node = payload
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def iter_paths(payload: dict[str, Any]) -> list[str]:
    """All addressable paths for this payload (fiscal years present + scalars)."""
    paths = [
        fiscal_year_path(fy["year_label"], f)
        for fy in payload.get("financials", {}).get("fiscal_years", [])
        for f in FISCAL_YEAR_FIELDS
    ]
    return paths + list(SCALAR_FIELDS)

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

import copy
import re
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

    A missing fiscal year is created and the list is re-sorted (by period_end when
    all years have one, otherwise by label).
    """
    value_type(path)
    out = copy.deepcopy(payload)
    m = _FY_RE.match(path)
    if m:
        fin = out.setdefault("financials", {})
        years: list[dict[str, Any]] = fin.setdefault("fiscal_years", [])
        target = next((fy for fy in years if fy.get("year_label") == m.group("label")), None)
        if target is None:
            target = {"year_label": m.group("label"), "months": 12}
            if period_end:
                target["period_end"] = period_end
            years.append(target)
            if all(fy.get("period_end") for fy in years):
                years.sort(key=lambda fy: str(fy["period_end"]))
            else:
                years.sort(key=lambda fy: str(fy["year_label"]))
        target[m.group("field")] = value
        return out
    parts = path.split(".")
    node = out
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    return out


def iter_paths(payload: dict[str, Any]) -> list[str]:
    """All addressable paths for this payload (fiscal years present + scalars)."""
    paths = [
        fiscal_year_path(fy["year_label"], f)
        for fy in payload.get("financials", {}).get("fiscal_years", [])
        for f in FISCAL_YEAR_FIELDS
    ]
    return paths + list(SCALAR_FIELDS)

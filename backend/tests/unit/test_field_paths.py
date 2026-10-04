"""Field-path helpers: chronological ordering and set_value edge cases."""

from __future__ import annotations

from datetime import date

from app.models.field_paths import period_end_from_label, period_sort_key, set_value


def test_period_end_from_label() -> None:
    assert period_end_from_label("FY2024") == date(2024, 3, 31)
    assert period_end_from_label("YE2024-12") == date(2024, 12, 31)
    assert period_end_from_label("YE2024-02") == date(2024, 2, 29)
    assert period_end_from_label("P2024-09-30-6M") == date(2024, 9, 30)
    assert period_end_from_label("Year 1") is None


def test_period_sort_key_orders_by_date() -> None:
    labels = ["FY2025", "YE2024-12", "P2025-09-30-6M", "FY2024"]
    ordered = sorted(labels, key=lambda lbl: period_sort_key(lbl, None))
    assert ordered == ["FY2024", "YE2024-12", "FY2025", "P2025-09-30-6M"]


def test_set_value_inserts_year_chronologically() -> None:
    payload = {"financials": {"fiscal_years": [{"year_label": "FY2025"}]}}
    out = set_value(payload, "financials.fiscal_years[YE2024-12].net_worth", {"value": "1"})
    assert [fy["year_label"] for fy in out["financials"]["fiscal_years"]] == ["YE2024-12", "FY2025"]


def test_clearing_a_missing_year_does_not_create_it() -> None:
    payload = {"financials": {"fiscal_years": [{"year_label": "FY2025"}]}}
    out = set_value(payload, "financials.fiscal_years[FY2023].net_worth", None)
    assert [fy["year_label"] for fy in out["financials"]["fiscal_years"]] == ["FY2025"]

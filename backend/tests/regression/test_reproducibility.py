"""
Regression tests for deterministic engine output.

The audit metadata fields are intentionally generated per run. Everything
else in the CompanyData -> IPOReport path must remain byte-identical for a
fixed input and ruleset.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.engine.decision_engine import DecisionEngine
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory

GENERATED_METADATA_FIELDS = {"report_id", "evaluated_at"}


def _strip_generated_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_generated_metadata(item)
            for key, item in value.items()
            if key not in GENERATED_METADATA_FIELDS
        }
    if isinstance(value, list):
        return [_strip_generated_metadata(item) for item in value]
    return value


@pytest.mark.regression
def test_engine_output_is_reproducible_after_audit_metadata_is_removed() -> None:
    engine = DecisionEngine(RuleRegistry())
    company = CompanyDataFactory.create()

    baseline_report = engine.evaluate(company).model_dump(mode="json")
    baseline = json.dumps(
        _strip_generated_metadata(baseline_report),
        sort_keys=True,
        separators=(",", ":"),
    )

    for _ in range(100):
        next_report = engine.evaluate(company).model_dump(mode="json")
        assert (
            json.dumps(
                _strip_generated_metadata(next_report),
                sort_keys=True,
                separators=(",", ":"),
            )
            == baseline
        )

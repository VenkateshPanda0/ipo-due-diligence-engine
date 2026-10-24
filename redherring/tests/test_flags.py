from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from redherring.flags.engine import Citation, Fact, evaluate, load_rules
from redherring.flags.spec import RuleSpec, load_rule_file

RULES_DIR = Path(__file__).parent.parent / "src" / "redherring" / "flags" / "rules"


def fact(key: str, value: str, page: int = 10, span: str = "row") -> Fact:
    return Fact(key=key, value=Decimal(value), citations=[Citation(pdf_page=page, span=span)])


def spec(toml: str, tmp_path: Path) -> RuleSpec:
    path = tmp_path / "r.toml"
    path.write_text(toml)
    return load_rule_file(path)


GCP = """
id = "T-GCP"
name = "GCP near cap"
rationale = "General corporate purposes close to the regulatory cap leave little accountable use."
platforms = ["mainboard"]
severity = "medium"
heuristic = false
citation_requirement = "Cite the objects table row and the issue-size row."

[logic]
kind = "ratio_vs_cap"
numerators = ["objects.gcp_amount"]
denominator = "issue.fresh_issue_amount"
cap = 0.25
near_cap_fraction = 0.9

[[sources]]
kind = "regulation"
ref = "SEBI (ICDR) Regulations, 2018"
clause = "Regulation 7(2)"
checked_on = 2026-10-24
effective = 2022-01-14
"""


def test_every_shipped_rule_loads_and_cites_a_source() -> None:
    rules = load_rules(RULES_DIR)
    assert rules, "no rules shipped"
    assert len({r.id for r in rules}) == len(rules)
    for r in rules:
        assert r.sources, r.id
        assert r.rationale.endswith("."), r.id
        for s in r.sources:
            assert s.checked_on <= date.today(), r.id
            if s.kind == "regulation":
                assert s.clause, f"{r.id}: regulation source needs a clause"


def test_ratio_vs_cap_flags_when_near_cap(tmp_path: Path) -> None:
    rule = spec(GCP, tmp_path)
    facts = {
        "objects.gcp_amount": fact("objects.gcp_amount", "230", page=88, span="GCP | 230"),
        "issue.fresh_issue_amount": fact(
            "issue.fresh_issue_amount", "1000", page=12, span="Fresh | 1000"
        ),
    }
    (flag,) = evaluate([rule], facts, platform="mainboard")
    assert flag.rule_id == "T-GCP"
    assert flag.severity == "medium"
    assert flag.numbers["ratio"] == Decimal("0.23")
    assert flag.numbers["cap"] == Decimal("0.25")
    assert {c.pdf_page for c in flag.citations} == {88, 12}
    assert "23%" in flag.explanation
    assert flag.sources[0].clause == "Regulation 7(2)"


def test_ratio_vs_cap_quiet_when_comfortably_below(tmp_path: Path) -> None:
    rule = spec(GCP, tmp_path)
    facts = {
        "objects.gcp_amount": fact("objects.gcp_amount", "100"),
        "issue.fresh_issue_amount": fact("issue.fresh_issue_amount", "1000"),
    }
    assert evaluate([rule], facts, platform="mainboard") == []


def test_ratio_above_cap_is_flagged_high(tmp_path: Path) -> None:
    rule = spec(GCP, tmp_path)
    facts = {
        "objects.gcp_amount": fact("objects.gcp_amount", "300"),
        "issue.fresh_issue_amount": fact("issue.fresh_issue_amount", "1000"),
    }
    (flag,) = evaluate([rule], facts, platform="mainboard")
    assert flag.severity == "high"
    assert "above" in flag.explanation


def test_rule_skipped_for_other_platform_and_for_missing_inputs(tmp_path: Path) -> None:
    rule = spec(GCP, tmp_path)
    facts = {
        "objects.gcp_amount": fact("objects.gcp_amount", "300"),
        "issue.fresh_issue_amount": fact("issue.fresh_issue_amount", "1000"),
    }
    assert evaluate([rule], facts, platform="sme") == []
    assert (
        evaluate([rule], {"objects.gcp_amount": facts["objects.gcp_amount"]}, platform="mainboard")
        == []
    )


def test_uncited_facts_never_produce_a_flag(tmp_path: Path) -> None:
    rule = spec(GCP, tmp_path)
    facts = {
        "objects.gcp_amount": Fact(key="objects.gcp_amount", value=Decimal("300"), citations=[]),
        "issue.fresh_issue_amount": fact("issue.fresh_issue_amount", "1000"),
    }
    assert evaluate([rule], facts, platform="mainboard") == []


def test_spec_rejects_unknown_logic_and_missing_clause(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        spec(GCP.replace('kind = "ratio_vs_cap"', 'kind = "made_up"'), tmp_path)
    with pytest.raises(ValueError, match="clause"):
        spec(GCP.replace('clause = "Regulation 7(2)"\n', ""), tmp_path)


CFO = """
id = "T-CFO"
name = "Operating cash flow persistently below profit"
rationale = "Profit not backed by operating cash flow is an earnings-quality warning."
platforms = ["mainboard", "sme"]
severity = "medium"
heuristic = true
citation_requirement = "Cite the cash-flow and profit rows for each year."

[logic]
kind = "persistent_below"
left = "financials.cash_from_operations"
right = "financials.profit_after_tax"
min_periods = 3
min_breaches = 2
require_right_positive = true

[[sources]]
kind = "literature"
ref = "Sloan (1996), The Accounting Review 71(3)"
checked_on = 2026-10-24
"""


CFO_KEY = "financials.cash_from_operations"
PAT_KEY = "financials.profit_after_tax"


def series(prefix: str, vals: dict[str, str], page: int) -> dict[str, Fact]:
    return {f"{prefix}.{k}": fact(f"{prefix}.{k}", v, page=page) for k, v in vals.items()}


def test_persistent_below_flags_when_cfo_trails_profit(tmp_path: Path) -> None:
    rule = spec(CFO, tmp_path)
    facts = {
        **series(CFO_KEY, {"FY2024": "50", "FY2025": "-20", "FY2026": "10"}, 200),
        **series(PAT_KEY, {"FY2024": "40", "FY2025": "60", "FY2026": "80"}, 150),
    }
    (flag,) = evaluate([rule], facts, platform="sme")
    assert flag.numbers["breaches"] == Decimal(2)
    assert flag.numbers["periods"] == Decimal(3)
    assert flag.severity == "medium"
    assert {c.pdf_page for c in flag.citations} == {200, 150}


def test_persistent_below_needs_enough_periods_and_ignores_losses(tmp_path: Path) -> None:
    rule = spec(CFO, tmp_path)
    two = {
        **series(CFO_KEY, {"FY2025": "-20", "FY2026": "10"}, 200),
        **series(PAT_KEY, {"FY2025": "60", "FY2026": "80"}, 150),
    }
    assert evaluate([rule], two, platform="sme") == []
    losses = {
        **series(CFO_KEY, {"FY2024": "-5", "FY2025": "-20", "FY2026": "-10"}, 200),
        **series(PAT_KEY, {"FY2024": "-4", "FY2025": "-6", "FY2026": "-8"}, 150),
    }
    assert evaluate([rule], losses, platform="sme") == []  # loss-making: right is not positive

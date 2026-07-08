"""
Run local demo companies through the IPO due-diligence engine.

The demo data is synthetic and self-contained. It exercises the same
CompanyData -> DecisionEngine -> ReportGenerator path used by the API.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.engine.decision_engine import DecisionEngine
from app.models.company_data import CompanyData
from app.reports.report_generator import ReportGenerator
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "sample_data" / "companies"
REPORT_DIR = ROOT / "sample_data" / "reports"


DemoFactory = Callable[[], CompanyData]


def _demo_companies() -> dict[str, DemoFactory]:
    return {
        "eligible-mainboard": CompanyDataFactory.create,
        "not-eligible-profitability": CompanyDataFactory.create_not_eligible,
        "needs-review-low-confidence": CompanyDataFactory.create_needs_review,
        "eligible-with-advisory-warnings": lambda: CompanyDataFactory.create(
            independent_directors=1,
            audit_independent_members=1,
            audit_chair_is_independent=False,
            arm_length_certified=False,
            has_qualifications=True,
            has_criminal_cases=True,
            total_litigation_exposure=15,
        ),
    }


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_demo(
    company_names: list[str] | None = None,
    *,
    write_inputs: bool = False,
    write_reports: bool = False,
) -> int:
    engine = DecisionEngine(RuleRegistry())
    generator = ReportGenerator()
    factories = _demo_companies()
    selected_names = company_names or list(factories)

    unknown = sorted(set(selected_names) - set(factories))
    if unknown:
        raise ValueError(f"Unknown demo compan{'y' if len(unknown) == 1 else 'ies'}: {unknown}")

    for name in selected_names:
        company = factories[name]()
        report = engine.evaluate(company)
        text_output = generator.generate(report, format="text")

        print(f"\n=== {name} ===")
        print(text_output)

        if write_inputs:
            input_path = INPUT_DIR / name / "company_data.json"
            serialized = json.dumps(
                company.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
            _write_text(input_path, f"{serialized}\n")

        if write_reports:
            _write_text(REPORT_DIR / f"{name}.txt", text_output)
            _write_text(REPORT_DIR / f"{name}.json", generator.generate(report, format="json"))
            _write_text(REPORT_DIR / f"{name}.html", generator.generate(report, format="html"))

    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--company",
        action="append",
        dest="companies",
        help="Run one demo company by slug. Can be passed multiple times.",
    )
    parser.add_argument(
        "--write-inputs",
        action="store_true",
        help="Write CompanyData JSON files under sample_data/companies/.",
    )
    parser.add_argument(
        "--write-reports",
        action="store_true",
        help="Write text, JSON, and HTML reports under sample_data/reports/.",
    )
    args = parser.parse_args()
    return run_demo(
        args.companies,
        write_inputs=args.write_inputs,
        write_reports=args.write_reports,
    )


if __name__ == "__main__":
    raise SystemExit(main())

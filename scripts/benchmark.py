"""
Benchmark the deterministic CompanyData -> IPOReport pipeline.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from pathlib import Path

from app.engine.decision_engine import DecisionEngine
from app.models.company_data import CompanyData
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "sample_data" / "benchmark_results.md"

DemoFactory = Callable[[], CompanyData]


def _companies() -> dict[str, DemoFactory]:
    return {
        "eligible-mainboard": CompanyDataFactory.create,
        "not-eligible-profitability": CompanyDataFactory.create_not_eligible,
        "needs-review-low-confidence": CompanyDataFactory.create_needs_review,
        "young-company": lambda: CompanyDataFactory.create(years_of_operation=2),
        "large-cap-float": lambda: CompanyDataFactory.create(
            expected_market_cap=2_000,
            public_offer_percentage=10,
        ),
        "low-public-float": lambda: CompanyDataFactory.create(public_offer_percentage=5),
        "high-issue-size": lambda: CompanyDataFactory.create(issue_size=300),
        "low-market-cap": lambda: CompanyDataFactory.create(expected_market_cap=20),
        "capex-lock-in": lambda: CompanyDataFactory.create(
            is_capex_issue=True,
            lock_in_months=36,
        ),
        "advisory-warnings": lambda: CompanyDataFactory.create(
            independent_directors=1,
            audit_independent_members=1,
            audit_chair_is_independent=False,
            arm_length_certified=False,
            has_qualifications=True,
            has_criminal_cases=True,
            total_litigation_exposure=15,
        ),
    }


def run_benchmark(iterations: int = 100) -> str:
    engine = DecisionEngine(RuleRegistry())
    rows: list[tuple[str, float, float, float]] = []

    for name, factory in _companies().items():
        company = factory()
        timings_ms: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            engine.evaluate(company)
            timings_ms.append((time.perf_counter() - start) * 1000)
        rows.append(
            (
                name,
                statistics.mean(timings_ms),
                statistics.median(timings_ms),
                max(timings_ms),
            )
        )

    lines = [
        "# Deterministic Engine Benchmark",
        "",
        f"Iterations per company: {iterations}",
        "",
        "| Company | Mean ms | Median ms | Max ms |",
        "|---|---:|---:|---:|",
    ]
    for name, mean_ms, median_ms, max_ms in rows:
        lines.append(f"| {name} | {mean_ms:.3f} | {median_ms:.3f} | {max_ms:.3f} |")

    slowest = max(row[3] for row in rows)
    lines.extend(
        [
            "",
            f"Target: < 100 ms per evaluation. Slowest observed run: {slowest:.3f} ms.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    output = run_benchmark()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

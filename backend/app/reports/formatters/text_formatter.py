"""
backend/app/reports/formatters/text_formatter.py

Plain-text formatter for IPOReport.

This module produces terminal-friendly report output from a completed
IPOReport. It contains no regulatory or parser logic.
"""

from __future__ import annotations

from app.models.ipo_report import IPOReport
from app.models.rule_result import RuleResult
from app.reports.formatters.utils import format_date, format_status, format_verdict


class TextReportFormatter:
    """Render IPOReport as terminal-friendly plain text."""

    def format(self, report: IPOReport) -> str:
        """Render a complete plain-text report."""
        lines = [
            f"IPO Due Diligence Report: {report.company_name}",
            f"Status: {format_status(report.status)}",
            f"Ruleset: {report.ruleset_version.version}",
            f"Evaluated At: {format_date(report.evaluated_at)}",
            "Disclaimer: Screening output only; not legal, investment, or regulatory advice.",
            "",
            _progress_line(
                "Mandatory",
                report.mandatory_progress.passed,
                report.mandatory_progress.total_rules,
            ),
            _progress_line(
                "Advisory",
                report.advisory_progress.passed,
                report.advisory_progress.total_rules,
            ),
            "",
            "Mandatory Requirements",
            "----------------------",
        ]
        lines.extend(_format_results(report.mandatory_results))
        lines.extend(["", "Advisory Checks", "---------------"])
        lines.extend(_format_results(report.advisory_results))
        lines.extend(["", "Gap Analysis", "------------"])

        if report.gap_analysis:
            for item in report.gap_analysis:
                lines.extend(
                    [
                        f"- {item.rule_id}: {item.gap_size}",
                        f"  Current: {item.current_value}",
                        f"  Required: {item.required_value}",
                        f"  Earliest Eligibility: {item.earliest_eligible_fy}",
                        "  Remediation:",
                    ]
                )
                lines.extend(f"    - {step}" for step in item.remediation_steps)
        else:
            lines.append("- No failed mandatory requirements.")

        lines.extend(["", "Observations", "------------"])
        if report.observations:
            lines.extend(f"- {observation}" for observation in report.observations)
        else:
            lines.append("- No additional observations.")

        return "\n".join(lines)


def _progress_line(label: str, passed: int, total: int) -> str:
    return f"{label}: {passed} / {total} requirements satisfied"


def _format_results(results: list[RuleResult]) -> list[str]:
    lines: list[str] = []
    for result in results:
        lines.append(
            f"- {format_verdict(result.verdict)} {result.rule_id}: {result.description}"
        )
        lines.append(f"  Regulation: {result.regulation_reference}")
        lines.append(f"  Required: {result.required_value}")
        if result.actual_value is not None:
            lines.append(f"  Actual: {result.actual_value}")
        if result.gap is not None:
            lines.append(f"  Gap: {result.gap}")
        lines.append(f"  Explanation: {result.explanation}")
        if result.source_citation is not None:
            pages = ", ".join(str(page) for page in result.source_citation.page_numbers)
            lines.append(
                f"  Evidence: {result.source_citation.document_name}, page(s) {pages}"
            )
    return lines

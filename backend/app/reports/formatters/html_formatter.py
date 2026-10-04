"""
backend/app/reports/formatters/html_formatter.py

HTML formatter for IPOReport using Jinja2 templates.

This module renders completed reports only. It contains no rule evaluation,
document parsing, service orchestration, or API handling logic.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.ipo_report import IPOReport
from app.reports.formatters.utils import (
    format_date,
    format_outcome,
    format_status,
    format_verdict,
)


class HTMLReportFormatter:
    """Render IPOReport as standalone HTML."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Create a formatter using the given template directory."""
        base_dir = template_dir or Path(__file__).resolve().parents[1] / "templates"
        self._environment = Environment(
            loader=FileSystemLoader(base_dir),
            autoescape=select_autoescape(("html", "xml", "j2")),
        )
        self._environment.filters["format_status"] = format_status
        self._environment.filters["format_verdict"] = format_verdict
        self._environment.filters["format_date"] = format_date
        self._environment.filters["format_outcome"] = format_outcome

    def format(self, report: IPOReport) -> str:
        """Render a complete HTML report."""
        template = self._environment.get_template("report.html.j2")
        return template.render(report=report)

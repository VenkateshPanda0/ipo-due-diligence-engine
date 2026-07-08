"""
backend/app/reports/formatters/json_formatter.py

JSON formatter for IPOReport.

This module renders an already-computed IPOReport. It does not evaluate
rules, map evidence, parse documents, or make eligibility decisions.
"""

from __future__ import annotations

import json

from app.models.ipo_report import IPOReport


class JSONReportFormatter:
    """Render IPOReport as deterministic, pretty-printed JSON."""

    def format(self, report: IPOReport) -> str:
        """Serialize an IPOReport to JSON.

        Args:
            report: Completed IPOReport from the Decision Engine.

        Returns:
            JSON string with Decimal, UUID, and datetime values encoded by
            Pydantic's JSON serializer.
        """
        payload = report.model_dump(mode="json")
        payload.update(
            {
                "machine_assessment_only": True,
                "human_review_required": True,
                "decision_authority": "human_reviewer",
            }
        )
        return json.dumps(payload, indent=2)

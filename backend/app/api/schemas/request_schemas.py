"""API request schemas and domain converters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.company_data import CompanyData
from app.models.human_review import HumanFinalDecision


class CompanyDataSchema(BaseModel):
    """API-facing wrapper around CompanyData input."""

    model_config = ConfigDict(extra="forbid")

    company_data: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_raw_company_data(cls, data: Any) -> Any:
        """Accept either {"company_data": ...} or a raw CompanyData object."""
        if isinstance(data, dict) and "company_data" not in data and "identification" in data:
            return {"company_data": data}
        return data

    def to_domain(self) -> CompanyData:
        """Convert request payload to canonical CompanyData."""
        payload: dict[str, Any] = self.company_data if self.company_data is not None else {}
        return CompanyData.model_validate(payload)


class HumanReviewDecisionRequest(BaseModel):
    """Request body for a human final decision."""

    model_config = ConfigDict(extra="forbid")

    reviewer_name: str
    final_decision: HumanFinalDecision
    rationale: str
    conditions: list[str] = []

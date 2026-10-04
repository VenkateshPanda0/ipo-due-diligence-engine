"""
backend/app/models/__init__.py

Public model exports for the domain layer.

This module MUST NOT import from: app.parser, app.api, app.engine, app.rules.
It depends only on the standard library and Pydantic.

Exports:
    - All domain enumerations (IPOStatus, Verdict, RuleCategory, etc.)
    - All domain exceptions (InsufficientDataError, etc.)
    - Core value types (ExtractedValue, SourceCitation)
    - Domain models (CompanyData and all sub-models)
    - Result/report models (RuleResult, RuleMetadata, IPOReport, etc.)
    - Versioning models (RulesetVersion)
"""

from app.models.company_data import (
    AuditCommittee,
    AuditorData,
    CompanyData,
    CompanyIdentification,
    EligibilityDeclarations,
    FinancialHistory,
    FiscalYear,
    GovernanceData,
    IssueDetails,
    LitigationCase,
    LitigationData,
    PromoterData,
    PromoterEntity,
    RelatedPartyData,
    RPTTransaction,
)
from app.models.enums import (
    ConfidenceLevel,
    ExtractionMethod,
    FieldStatus,
    IPOStatus,
    LegalCategory,
    ListingRoute,
    RuleCategory,
    ScreeningOutcome,
    StatementBasis,
    Verdict,
    VerificationStatus,
)
from app.models.evidence import EvidenceRef
from app.models.exceptions import (
    DomainError,
    ExtractionError,
    InsufficientDataError,
    ReportNotFoundError,
    RuleEvaluationError,
    RulesetNotFoundError,
    UnsupportedDocumentError,
)
from app.models.extracted_value import ExtractedValue
from app.models.human_review import (
    HumanFinalDecision,
    HumanReviewRecord,
    HumanReviewStatus,
)
from app.models.ipo_report import EligibilityProgress, GapAnalysisItem, IPOReport
from app.models.rule_result import RuleMetadata, RuleResult
from app.models.ruleset_version import DEFAULT_RULESET_VERSION, RulesetVersion
from app.models.source_citation import SourceCitation

__all__ = [
    # Enumerations
    "FieldStatus",
    "LegalCategory",
    "ListingRoute",
    "ScreeningOutcome",
    "StatementBasis",
    "VerificationStatus",
    "EligibilityDeclarations",
    "EvidenceRef",
    "IPOStatus",
    "Verdict",
    "RuleCategory",
    "ConfidenceLevel",
    "ExtractionMethod",
    "HumanReviewStatus",
    "HumanFinalDecision",
    # Exceptions
    "DomainError",
    "InsufficientDataError",
    "RuleEvaluationError",
    "ExtractionError",
    "UnsupportedDocumentError",
    "ReportNotFoundError",
    "RulesetNotFoundError",
    # Value types
    "ExtractedValue",
    "SourceCitation",
    "HumanReviewRecord",
    # Company data models
    "CompanyData",
    "CompanyIdentification",
    "FinancialHistory",
    "FiscalYear",
    "PromoterData",
    "PromoterEntity",
    "GovernanceData",
    "AuditCommittee",
    "IssueDetails",
    "LitigationData",
    "LitigationCase",
    "RelatedPartyData",
    "RPTTransaction",
    "AuditorData",
    # Rule / result models
    "RuleMetadata",
    "RuleResult",
    # Report models
    "EligibilityProgress",
    "GapAnalysisItem",
    "IPOReport",
    # Versioning
    "RulesetVersion",
    "DEFAULT_RULESET_VERSION",
]

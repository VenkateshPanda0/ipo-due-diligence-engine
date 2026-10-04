"""
backend/app/models/enums.py

Domain enumerations for the IPO Due Diligence Engine.

This module MUST NOT import from app.rules, app.intelligence, app.api, app.engine.
All values are lowercase strings to keep JSON serialisation stable.
"""

from enum import Enum


class IPOStatus(str, Enum):
    """Legacy (API v0) case-level status, kept for backward compatibility.

    Derived from :class:`ScreeningOutcome` via ``ScreeningOutcome.legacy_status``.
    ``ELIGIBLE`` means only "no mandatory failure identified within the supported
    screening scope"; it is not a legal determination of IPO eligibility.
    """

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_REVIEW = "needs_review"


class ScreeningOutcome(str, Enum):
    """Case-level screening outcome (ruleset >= 2.0.0).

    Precedence (highest first): UNSUPPORTED_SCOPE, SCREENING_FAILURE,
    AWAITING_HUMAN_REVIEW, INSUFFICIENT_EVIDENCE, NO_FAILURE_IDENTIFIED.
    """

    NO_FAILURE_IDENTIFIED = "no_failure_identified"
    SCREENING_FAILURE = "screening_failure"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_SCOPE = "unsupported_scope"

    @property
    def legacy_status(self) -> "IPOStatus":
        """Map to the legacy three-value status used by API v0 clients."""
        if self is ScreeningOutcome.NO_FAILURE_IDENTIFIED:
            return IPOStatus.ELIGIBLE
        if self is ScreeningOutcome.SCREENING_FAILURE:
            return IPOStatus.NOT_ELIGIBLE
        return IPOStatus.NEEDS_REVIEW


class Verdict(str, Enum):
    """Per-rule evaluation outcome.

    PASS / FAIL: determinable from reliable evidence.
    INCONCLUSIVE: required evidence is missing.
    REQUIRES_HUMAN_REVIEW: evidence exists but is low-confidence, conflicting,
        or the rule needs interpretive judgement for this case.
    NOT_APPLICABLE: the rule does not apply to this issuer/route/issue.
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    NOT_APPLICABLE = "not_applicable"


class RuleCategory(str, Enum):
    """Whether a rule can block the screening outcome.

    MANDATORY results feed the case outcome; ADVISORY results never do.
    """

    MANDATORY = "mandatory"
    ADVISORY = "advisory"


class LegalCategory(str, Enum):
    """Legal nature of a check, independent of whether it blocks screening."""

    STATUTORY_ELIGIBILITY = "statutory_eligibility"
    STATUTORY_ISSUE_CONDITION = "statutory_issue_condition"
    EXCHANGE_LISTING_CRITERION = "exchange_listing_criterion"
    POST_LISTING_OBLIGATION = "post_listing_obligation"
    DILIGENCE_INDICATOR = "diligence_indicator"


class ListingRoute(str, Enum):
    """IPO route declared for the screening case."""

    MAINBOARD_REG6_1 = "mainboard_reg6_1"
    MAINBOARD_REG6_2 = "mainboard_reg6_2"
    SME_CHAPTER_IX = "sme_chapter_ix"


class VerificationStatus(str, Enum):
    """How a rule's legal basis has been checked.

    PRIMARY_TEXT_CHECKED: compared by engineering against the official
        consolidated text. This is NOT legal sign-off.
    SECONDARY_SOURCES_ONLY: primary text not retrieved; cross-checked against
        independent secondary summaries.
    UNVERIFIED: source not retrievable or rule is an engineering heuristic.
    LEGAL_REVIEWED: reviewed and approved by a qualified professional.
    """

    PRIMARY_TEXT_CHECKED = "primary_text_checked"
    SECONDARY_SOURCES_ONLY = "secondary_sources_only"
    UNVERIFIED = "unverified"
    LEGAL_REVIEWED = "legal_reviewed"


class ConfidenceLevel(str, Enum):
    """Extraction confidence level attached to every ExtractedValue.

    LOW values that are not human-confirmed produce REQUIRES_HUMAN_REVIEW.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractionMethod(str, Enum):
    """How a value was obtained."""

    PDF_TABLE = "pdf_table"
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    MANUAL = "manual"
    CALCULATED = "calculated"
    HUMAN_CORRECTED = "human_corrected"
    # Retained for backward compatibility with stored v1 payloads. No code path
    # in this repository produces it.
    AI_EXTRACTED = "ai_extracted"


class FieldStatus(str, Enum):
    """Field-level extraction status."""

    EXTRACTED_HIGH_CONFIDENCE = "extracted_high_confidence"
    EXTRACTED_NEEDS_VERIFICATION = "extracted_needs_verification"
    CONFLICTING_CANDIDATES = "conflicting_candidates"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    UNSUPPORTED_FORMAT = "unsupported_format"
    PROCESSING_FAILED = "processing_failed"
    HUMAN_CONFIRMED = "human_confirmed"
    MANUAL_ENTRY = "manual_entry"


class StatementBasis(str, Enum):
    """Whether financial statements are consolidated or standalone."""

    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"
    UNKNOWN = "unknown"

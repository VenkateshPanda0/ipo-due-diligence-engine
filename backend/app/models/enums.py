"""
backend/app/models/enums.py

Domain enumerations for the IPO Due Diligence Engine.

Contains all enumerated types used across the domain layer. These enums
define the vocabulary of the system: eligibility verdicts, rule categories,
confidence levels, and extraction methods.

This module MUST NOT import from:
  - app.rules (no rule logic)
  - app.parser (no document parsing)
  - app.api (no HTTP logic)
  - app.engine (no orchestration)

All values are lowercase strings to ensure clean JSON serialization.
"""

from enum import Enum


class IPOStatus(str, Enum):
    """Overall IPO eligibility determination produced by the Decision Engine.

    A company is ELIGIBLE only when every mandatory rule passes.
    NEEDS_REVIEW indicates one or more mandatory rules are INCONCLUSIVE,
    meaning extracted data had insufficient confidence for a definitive ruling.
    NOT_ELIGIBLE means at least one mandatory rule failed.

    Example:
        >>> status = IPOStatus.NOT_ELIGIBLE
        >>> status.value
        'not_eligible'
    """

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_REVIEW = "needs_review"


class Verdict(str, Enum):
    """Per-rule evaluation outcome.

    Produced by each BaseRule.evaluate() call. INCONCLUSIVE signals
    that the data was present but had LOW confidence without human
    confirmation, or that required data was absent.

    Example:
        >>> verdict = Verdict.PASS
        >>> verdict.value
        'pass'
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class RuleCategory(str, Enum):
    """Classification of a rule as mandatory or advisory.

    MANDATORY rules directly affect IPO eligibility — a single FAIL
    blocks the company. ADVISORY rules flag governance risks and
    best-practice deviations without blocking eligibility.

    Example:
        >>> category = RuleCategory.MANDATORY
        >>> category.value
        'mandatory'
    """

    MANDATORY = "mandatory"
    ADVISORY = "advisory"


class ConfidenceLevel(str, Enum):
    """Extraction confidence level attached to every ExtractedValue.

    HIGH: extracted from a well-formed digital table, cross-validated.
    MEDIUM: extracted via Camelot or AI from clear text, single-source.
    LOW: extracted via OCR from a scanned page or unverified AI output.

    A value with LOW confidence that has not been confirmed by a human
    causes the evaluating rule to return INCONCLUSIVE.

    Example:
        >>> level = ConfidenceLevel.HIGH
        >>> level.value
        'high'
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractionMethod(str, Enum):
    """Method used to extract a value from a source document.

    PDF_TABLE: pdfplumber or Camelot table extraction.
    OCR: Tesseract or EasyOCR for scanned documents.
    MANUAL: entered directly by a human — highest inherent trust.
    AI_EXTRACTED: extracted via LLM API call.

    Example:
        >>> method = ExtractionMethod.MANUAL
        >>> method.value
        'manual'
    """

    PDF_TABLE = "pdf_table"
    OCR = "ocr"
    MANUAL = "manual"
    AI_EXTRACTED = "ai_extracted"

from __future__ import annotations

from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.parser.confidence_scorer import ConfidenceScorer


def test_confidence_scorer_assigns_levels_by_method() -> None:
    scorer = ConfidenceScorer()

    assert scorer.score(ExtractionMethod.PDF_TABLE, corroborated=True) == ConfidenceLevel.HIGH
    assert scorer.score(ExtractionMethod.PDF_TABLE) == ConfidenceLevel.MEDIUM
    assert scorer.score(ExtractionMethod.OCR) == ConfidenceLevel.LOW

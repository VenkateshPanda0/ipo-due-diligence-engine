"""
backend/tests/unit/engine/test_evidence_mapper.py

Unit tests for EvidenceMapper citation attachment.
"""

from __future__ import annotations

from app.engine.evidence_mapper import EvidenceMapper
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import ConfidenceLevel, ExtractionMethod
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


class TestEvidenceMapper:
    """Source citations are derived from CompanyData provenance."""

    def test_attaches_citation_for_financial_rule(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        results = RulesEngine(registry).evaluate_all(company)
        nta_result = next(result for result in results if result.rule_id == "NTA_3CR")

        [annotated] = EvidenceMapper().annotate([nta_result], company)

        assert annotated.source_citation is not None
        assert annotated.source_citation.document_name == "Annual_Report_Test.pdf"
        assert annotated.source_citation.page_numbers == [1]
        assert annotated.source_citation.extraction_method == ExtractionMethod.MANUAL
        assert annotated.source_citation.confidence == ConfidenceLevel.HIGH
        assert len(annotated.source_citation.extracted_values) == 3

    def test_uses_lowest_confidence_across_values(self, registry: RuleRegistry) -> None:
        company = CompanyDataFactory.create_needs_review()
        results = RulesEngine(registry).evaluate_all(company)
        nta_result = next(result for result in results if result.rule_id == "NTA_3CR")

        [annotated] = EvidenceMapper().annotate([nta_result], company)

        assert annotated.source_citation is not None
        assert annotated.source_citation.confidence == ConfidenceLevel.LOW
        assert annotated.source_citation.extraction_method == ExtractionMethod.OCR

    def test_manual_values_are_cited_without_special_handling(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        results = RulesEngine(registry).evaluate_all(company)
        promoter_result = next(
            result for result in results if result.rule_id == "PROMOTER_LOCK_IN"
        )

        [annotated] = EvidenceMapper().annotate([promoter_result], company)

        assert annotated.source_citation is not None
        assert annotated.source_citation.extraction_method == ExtractionMethod.MANUAL

    def test_rule_without_extracted_values_is_left_unchanged(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        results = RulesEngine(registry).evaluate_all(company)
        track_record = next(result for result in results if result.rule_id == "TRACK_RECORD_3Y")

        [annotated] = EvidenceMapper().annotate([track_record], company)

        assert annotated.source_citation is None
        assert annotated == track_record

    def test_multi_page_citations_are_sorted_and_unique(
        self, registry: RuleRegistry, company: CompanyData
    ) -> None:
        fiscal_years = [
            year.model_copy(
                update={
                    "net_worth": year.net_worth.model_copy(
                        update={"page_number": 3 - index}
                    )
                }
            )
            for index, year in enumerate(company.financials.fiscal_years[-3:])
        ]
        company = CompanyDataFactory.create(fiscal_years=fiscal_years)
        results = RulesEngine(registry).evaluate_all(company)
        net_worth = next(result for result in results if result.rule_id == "NET_WORTH_1CR")

        [annotated] = EvidenceMapper().annotate([net_worth], company)

        assert annotated.source_citation is not None
        assert annotated.source_citation.page_numbers == [1, 2, 3]

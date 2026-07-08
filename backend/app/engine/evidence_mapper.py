"""
backend/app/engine/evidence_mapper.py

Evidence Mapper — M4-005.

Maps ExtractedValue provenance metadata from CompanyData into SourceCitation
objects and annotates RuleResult objects with them. The EvidenceMapper bridges
the extraction pipeline and the Rules Engine by making document provenance
visible in the final report.

ARCHITECTURAL CONSTRAINTS:
  - May import from: models/ only
  - MUST NOT import from: parser/, api/, services/
  - Pure transformation: no I/O, no side effects.

Design:
  - EvidenceMapper.annotate() takes a list of RuleResult and a CompanyData,
    and returns a new list with source_citation populated on each result.
  - Since ExtractedValue objects know their source_document and page_number,
    the mapper extracts the ExtractedValues and builds a SourceCitation.
  - The citation's confidence is the minimum confidence among all EVs.
  - The citation's extraction_method is taken from the first EV.
"""

from __future__ import annotations

from typing import cast

from app.models.company_data import CompanyData
from app.models.enums import ConfidenceLevel
from app.models.extracted_value import ExtractedValue
from app.models.rule_result import RuleResult
from app.models.source_citation import CitationExtractedValue, SourceCitation

# Rule-to-field mapping: which CompanyData fields each rule reads.
_RULE_FIELD_MAP: dict[str, list[str]] = {
    "NTA_3CR": ["financials.fiscal_years[-3:].net_tangible_assets"],
    "MONETARY_ASSETS_50PCT": [
        "financials.fiscal_years[-3:].net_tangible_assets",
        "financials.fiscal_years[-3:].monetary_assets",
    ],
    "AVG_OPERATING_PROFIT_15CR": ["financials.fiscal_years[*].operating_profit"],
    "NET_WORTH_1CR": ["financials.fiscal_years[-3:].net_worth"],
    "ISSUE_SIZE_5X": ["issue_details.issue_size", "issue_details.pre_issue_net_worth"],
    "TRACK_RECORD_3Y": [],  # uses plain int, no ExtractedValue
    "PUBLIC_OFFER_MIN": [
        "issue_details.public_offer_percentage",
        "issue_details.expected_market_cap",
    ],
    "PROMOTER_CONTRIBUTION_20": ["promoter.post_issue_holding"],
    "PROMOTER_LOCK_IN": ["promoter.lock_in_months"],
    "MIN_POST_ISSUE_CAPITAL": ["issue_details.post_issue_paid_up_capital"],
    "MIN_MARKET_CAP": ["issue_details.expected_market_cap"],
    "BOARD_INDEPENDENCE": [
        "governance.total_directors",
        "governance.independent_directors",
        "governance.is_chair_executive",
        "governance.is_chair_promoter",
    ],
    "AUDIT_COMMITTEE": [
        "governance.audit_committee.total_members",
        "governance.audit_committee.independent_members",
        "governance.audit_committee.chair_is_independent",
    ],
    "RPT_DISCLOSURE": ["rpt.arm_length_certified", "rpt.total_rpt_value"],
    "AUDITOR_QUALIFICATION": ["auditor.has_qualifications", "auditor.has_modified_opinion"],
    "LITIGATION_RISK": ["litigation.has_criminal_cases", "litigation.total_exposure"],
}


class EvidenceMapper:
    """Annotates RuleResult objects with source provenance from CompanyData.

    The EvidenceMapper is a pure transformation layer. Given the results from
    the Rules Engine and the CompanyData that produced them, it collects
    the ExtractedValue objects that each rule read, builds a SourceCitation,
    and returns new RuleResult instances with the citation attached.

    Example::

        mapper = EvidenceMapper()
        annotated = mapper.annotate(results, company)
        assert annotated[0].source_citation is not None
    """

    def annotate(
        self,
        results: list[RuleResult],
        company: CompanyData,
    ) -> list[RuleResult]:
        """Return a new list of RuleResult with source_citation populated.

        Args:
            results: Ordered list of RuleResult from the Rules Engine.
            company: The CompanyData that was evaluated.

        Returns:
            A new list of RuleResult with source_citation attached wherever
            source documents can be identified. Same length and order as input.
        """
        annotated: list[RuleResult] = []
        for result in results:
            citation = self._build_citation(result.rule_id, company)
            if citation is not None:
                annotated_result = result.model_copy(update={"source_citation": citation})
            else:
                annotated_result = result
            annotated.append(annotated_result)
        return annotated

    def _build_citation(
        self,
        rule_id: str,
        company: CompanyData,
    ) -> SourceCitation | None:
        """Build a SourceCitation for the given rule_id.

        Collects all ExtractedValue objects referenced by the rule's fields,
        derives confidence (minimum), extraction_method (first non-None),
        and builds a SourceCitation.

        Args:
            rule_id: The rule identifier.
            company: The canonical company data.

        Returns:
            A SourceCitation if any EVs are found, or None.
        """
        field_paths = _RULE_FIELD_MAP.get(rule_id)
        if field_paths is None or not field_paths:
            return None

        all_evs: list[ExtractedValue[object]] = []
        for path in field_paths:
            evs = self._collect_evs(path, company)
            all_evs.extend(evs)

        if not all_evs:
            return None

        # Derive the primary source document (most common)
        source_docs = [ev.source_document for ev in all_evs]
        primary_doc = max(set(source_docs), key=source_docs.count)

        # Derive confidence (minimum)
        confidence_rank = {
            ConfidenceLevel.HIGH: 2,
            ConfidenceLevel.MEDIUM: 1,
            ConfidenceLevel.LOW: 0,
        }
        min_conf = min(all_evs, key=lambda ev: confidence_rank[ev.confidence]).confidence

        # Derive extraction method (first)
        method = all_evs[0].extraction_method

        # Derive page numbers (non-None, sorted and unique)
        pages = sorted({ev.page_number for ev in all_evs if ev.page_number is not None})

        return SourceCitation(
            document_name=primary_doc,
            page_numbers=pages,
            table_reference=None,
            extracted_values=cast("list[CitationExtractedValue]", all_evs),
            extraction_method=method,
            confidence=min_conf,
        )

    def _collect_evs(
        self,
        field_path: str,
        company: CompanyData,
    ) -> list[ExtractedValue[object]]:
        """Collect ExtractedValue objects from a field path.

        Args:
            field_path: Dot-notation path, possibly with [*] for lists.
            company: The canonical company data.

        Returns:
            List of ExtractedValue objects found at the path.
        """
        evs: list[ExtractedValue[object]] = []
        try:
            if "[*]" in field_path or "[-3:]" in field_path:
                evs = self._collect_from_list(field_path, company)
            else:
                obj = self._resolve_path(field_path, company)
                if isinstance(obj, ExtractedValue):
                    evs = [obj]
        except (AttributeError, TypeError, IndexError):
            pass
        return evs

    def _collect_from_list(
        self,
        field_path: str,
        company: CompanyData,
    ) -> list[ExtractedValue[object]]:
        """Collect EVs from a list path (e.g., fiscal_years[-3:].net_worth)."""
        evs: list[ExtractedValue[object]] = []
        if "[*]." in field_path:
            parts = field_path.split("[*].")
            fiscal_years = company.financials.fiscal_years
        elif "[-3:]." in field_path:
            parts = field_path.split("[-3:].")
            fiscal_years = company.financials.fiscal_years[-3:]
        else:
            return evs
        field_name = parts[1]
        for fy in fiscal_years:
            obj = getattr(fy, field_name, None)
            if isinstance(obj, ExtractedValue):
                evs.append(obj)
        return evs

    def _resolve_path(self, field_path: str, company: CompanyData) -> object:
        """Resolve a dot-notation path to the value at that path."""
        obj: object = company
        for part in field_path.split("."):
            obj = getattr(obj, part)
        return obj

"""
backend/app/engine/decision_engine.py

Decision Engine — M4-001 through M4-007.

The DecisionEngine orchestrates the full evaluation pipeline and assembles
the final IPOReport. It is the top-level orchestrator of the domain layer.

Pipeline:
  1. RulesEngine evaluates all 16 rules → list[RuleResult]
  2. EvidenceMapper annotates results with source citations
  3. DecisionEngine determines IPOStatus from mandatory results
  4. GapPlanner generates GapAnalysisItem for failed mandatory rules
  5. ObservationGenerator produces free-form observations from patterns
  6. IPOReport is assembled from all components

ARCHITECTURAL CONSTRAINTS:
  - May import from: models/, rules/ (registry), engine/ (siblings)
  - MUST NOT import from: parser/, api/, services/
  - The DecisionEngine never contains rule logic — all rules live in BaseRule.

Design decisions:
  - Status determination is deterministic: one FAIL → NOT_ELIGIBLE,
    one INCONCLUSIVE and no FAIL → NEEDS_REVIEW, all PASS → ELIGIBLE.
  - The same CompanyData + RulesetVersion always produces the same status,
    gap analysis, and observations (report_id and evaluated_at may differ).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.engine.evidence_mapper import EvidenceMapper
from app.engine.gap_planner import GapPlanner
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import IPOStatus, RuleCategory, Verdict
from app.models.ipo_report import EligibilityProgress, GapAnalysisItem, IPOReport
from app.models.rule_result import RuleResult
from app.rules.registry import RuleRegistry


class DecisionEngine:
    """Orchestrates the full IPO eligibility evaluation pipeline.

    The DecisionEngine coordinates the Rules Engine, Evidence Mapper, Gap
    Planner, and report assembly into a single, callable pipeline. It is
    stateless: the same instance can evaluate multiple companies without
    any cleanup.

    Responsibilities:
      1. Run all rules via the RulesEngine.
      2. Annotate results with source citations via EvidenceMapper.
      3. Determine the overall IPOStatus from mandatory results.
      4. Generate GapAnalysisItem for failed mandatory rules.
      5. Generate free-form observations from pattern matching.
      6. Assemble and return a complete IPOReport.

    Example::

        registry = RuleRegistry()
        engine = DecisionEngine(registry)
        report = engine.evaluate(company)
        assert report.status in (IPOStatus.ELIGIBLE, IPOStatus.NOT_ELIGIBLE,
                                 IPOStatus.NEEDS_REVIEW)
    """

    def __init__(self, registry: RuleRegistry) -> None:
        """Initialise the Decision Engine with a pre-built rule registry.

        Args:
            registry: A fully initialised RuleRegistry. The engine holds
                a reference; it does not copy the registry.
        """
        self._rules_engine = RulesEngine(registry)
        self._evidence_mapper = EvidenceMapper()
        self._gap_planner = GapPlanner()

    def evaluate(self, company: CompanyData) -> IPOReport:
        """Run the full evaluation pipeline and return an IPOReport.

        This is the primary entry point for the Decision Engine. It runs
        all rules, annotates evidence, determines status, generates gap
        analysis, and assembles the final report.

        Args:
            company: The canonical company data. The only input to the engine.

        Returns:
            A complete, immutable IPOReport with all verdicts, gap analysis,
            observations, and source citations.
        """
        # Step 1: Evaluate all rules
        raw_results = self._rules_engine.evaluate_all(company)

        # Step 2: Annotate with source citations
        annotated_results = self._evidence_mapper.annotate(raw_results, company)

        # Step 3: Split into mandatory and advisory
        mandatory_results, advisory_results = self.classify_results(annotated_results)

        # Step 4: Determine overall status
        status = self.determine_status(mandatory_results)

        # Step 5: Compute progress counts
        mandatory_progress = self.compute_progress(mandatory_results)
        advisory_progress = self.compute_progress(advisory_results)

        # Step 6: Generate gap analysis for failed mandatory rules
        gap_analysis = self._gap_planner.generate(mandatory_results, company)

        # Step 7: Generate observations from patterns
        observations = self.generate_observations(company, mandatory_results, advisory_results)

        # Step 8: Assemble the report
        return self.assemble_report(
            company=company,
            status=status,
            mandatory_results=mandatory_results,
            advisory_results=advisory_results,
            mandatory_progress=mandatory_progress,
            advisory_progress=advisory_progress,
            gap_analysis=gap_analysis,
            observations=observations,
        )

    @staticmethod
    def classify_results(
        results: list[RuleResult],
    ) -> tuple[list[RuleResult], list[RuleResult]]:
        """Split results into mandatory and advisory lists.

        Args:
            results: All RuleResult objects in registry order.

        Returns:
            A tuple (mandatory_results, advisory_results) preserving order.
        """
        mandatory = [r for r in results if r.category == RuleCategory.MANDATORY]
        advisory = [r for r in results if r.category == RuleCategory.ADVISORY]
        return mandatory, advisory

    @staticmethod
    def determine_status(mandatory_results: list[RuleResult]) -> IPOStatus:
        """Determine the overall IPO eligibility status from mandatory results.

        The determination is strictly ordered:
          1. If ANY mandatory rule returned FAIL → NOT_ELIGIBLE.
          2. Else if ANY mandatory rule returned INCONCLUSIVE → NEEDS_REVIEW.
          3. Otherwise (all PASS) → ELIGIBLE.

        This ordering ensures that a definitive FAIL is never hidden by an
        INCONCLUSIVE verdict. NOT_ELIGIBLE takes precedence.

        Args:
            mandatory_results: All mandatory rule results.

        Returns:
            IPOStatus.NOT_ELIGIBLE, NEEDS_REVIEW, or ELIGIBLE.
        """
        verdicts = {r.verdict for r in mandatory_results}
        if Verdict.FAIL in verdicts:
            return IPOStatus.NOT_ELIGIBLE
        if Verdict.INCONCLUSIVE in verdicts:
            return IPOStatus.NEEDS_REVIEW
        return IPOStatus.ELIGIBLE

    @staticmethod
    def compute_progress(results: list[RuleResult]) -> EligibilityProgress:
        """Compute pass/fail/inconclusive counts for a set of results.

        Args:
            results: A list of RuleResult (all mandatory or all advisory).

        Returns:
            An EligibilityProgress with counts and pass percentage.
        """
        total = len(results)
        passed = sum(1 for r in results if r.verdict == Verdict.PASS)
        failed = sum(1 for r in results if r.verdict == Verdict.FAIL)
        inconclusive = sum(1 for r in results if r.verdict == Verdict.INCONCLUSIVE)
        failed_ids = [r.rule_id for r in results if r.verdict == Verdict.FAIL]

        pass_pct = (
            Decimal(str(passed)) / Decimal(str(total)) * Decimal("100")
            if total > 0
            else Decimal("0")
        ).quantize(Decimal("0.01"))

        return EligibilityProgress(
            total_rules=total,
            passed=passed,
            failed=failed,
            inconclusive=inconclusive,
            pass_percentage=pass_pct,
            failed_rule_ids=failed_ids,
        )

    @staticmethod
    def generate_observations(
        company: CompanyData,
        mandatory_results: list[RuleResult],
        advisory_results: list[RuleResult],
    ) -> list[str]:
        """Generate free-form observations from pattern matching.

        These are non-blocking informational notes based on patterns in the
        company's data — e.g., young company, declining revenue, heavy RPT
        concentration. They supplement the structured rule verdicts.

        Args:
            company: The canonical company data.
            mandatory_results: Mandatory rule results.
            advisory_results: Advisory rule results.

        Returns:
            A list of human-readable observation strings. May be empty.
        """
        observations: list[str] = []

        # Observation 1: Very young company (< 5 FYs)
        n_years = company.financials.years_of_operation
        if n_years < 5:
            observations.append(
                f"Company has {n_years} year(s) of operating history. "
                "Investors and SEBI typically look more favourably on companies with ≥ 5 years "
                "of audited track record."
            )

        # Observation 2: Declining revenue trend
        fys = company.financials.fiscal_years
        if len(fys) >= 3:
            recent_revenues = [
                fy.revenue.value
                for fy in fys[-3:]
                if fy.revenue.is_reliable()
            ]
            if len(recent_revenues) >= 3 and recent_revenues[-1] < recent_revenues[0]:
                observations.append(
                    f"Revenue has declined from {recent_revenues[0]:.2f} Cr to "
                    f"{recent_revenues[-1]:.2f} Cr over the last 3 fiscal years. "
                    "Declining revenue is a red flag that investment bankers and SEBI "
                    "will scrutinise."
                )

        # Observation 3: All mandatory rules passed — positive signal
        all_mandatory_pass = all(r.verdict == Verdict.PASS for r in mandatory_results)
        if all_mandatory_pass:
            observations.append(
                "All 11 mandatory SEBI ICDR eligibility requirements are satisfied. "
                "The company appears eligible for a mainboard IPO from a regulatory standpoint."
            )

        # Observation 4: Multiple advisory flags
        advisory_fails = [r for r in advisory_results if r.verdict == Verdict.FAIL]
        if len(advisory_fails) >= 3:
            failed_names = ", ".join(r.rule_id for r in advisory_fails)
            observations.append(
                f"{len(advisory_fails)} advisory governance issues detected: {failed_names}. "
                "Multiple governance weaknesses may affect investor confidence and SEBI "
                "review time."
            )

        # Observation 5: Criminal litigation
        if (
            company.litigation.has_criminal_cases.is_reliable()
            and company.litigation.has_criminal_cases.value
        ):
            observations.append(
                "Criminal litigation is pending against the company or its "
                "promoters/directors. This is a high-severity issue that typically "
                "requires resolution before IPO filing."
            )

        # Observation 6: Auditor tenure warning (> 5 years = independence risk)
        if (
            company.auditor.years_as_auditor.is_reliable()
            and company.auditor.years_as_auditor.value > 5
        ):
            observations.append(
                f"The statutory auditor has served for {company.auditor.years_as_auditor.value} "
                "consecutive years. Long auditor tenure (> 5 years) may raise "
                "independence concerns during IPO due diligence."
            )

        return observations

    @staticmethod
    def assemble_report(
        company: CompanyData,
        status: IPOStatus,
        mandatory_results: list[RuleResult],
        advisory_results: list[RuleResult],
        mandatory_progress: EligibilityProgress,
        advisory_progress: EligibilityProgress,
        gap_analysis: list[GapAnalysisItem],
        observations: list[str],
    ) -> IPOReport:
        """Assemble the final IPOReport from all pipeline components.

        Args:
            company: The canonical company data (for name and ruleset).
            status: The overall IPO eligibility status.
            mandatory_results: Ordered mandatory rule results.
            advisory_results: Ordered advisory rule results.
            mandatory_progress: Pass/fail counts for mandatory rules.
            advisory_progress: Pass/fail counts for advisory rules.
            gap_analysis: Gap items for failed mandatory rules.
            observations: Free-form observation strings.

        Returns:
            A complete, immutable IPOReport.
        """
        return IPOReport(
            report_id=uuid4(),
            company_name=company.identification.company_name,
            status=status,
            mandatory_progress=mandatory_progress,
            advisory_progress=advisory_progress,
            mandatory_results=mandatory_results,
            advisory_results=advisory_results,
            gap_analysis=gap_analysis,
            observations=observations,
            ruleset_version=company.ruleset_version,
            evaluated_at=datetime.now(tz=UTC),
        )

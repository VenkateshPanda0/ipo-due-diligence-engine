"""
backend/app/engine/decision_engine.py

Decision Engine — runs a ruleset against one CompanyData snapshot and assembles
an immutable IPOReport.

Case outcome precedence (mandatory results only; advisory never affects it):

  1. UNSUPPORTED_SCOPE      — declared route is not supported by the ruleset.
  2. SCREENING_FAILURE      — any mandatory FAIL (always from reliable evidence).
  3. AWAITING_HUMAN_REVIEW  — any mandatory REQUIRES_HUMAN_REVIEW.
  4. INSUFFICIENT_EVIDENCE  — any mandatory INCONCLUSIVE.
  5. NO_FAILURE_IDENTIFIED  — otherwise. NOT_APPLICABLE results are ignored.

A PASS that carries ``requires_human_review`` (e.g. reliance on a proviso, or an
SCRR tier taken from secondary sources) does not change the outcome but is listed
under unresolved issues.

ARCHITECTURAL CONSTRAINTS: may import from models/, rules/, engine/, regulatory/.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.engine.gap_planner import GapPlanner
from app.engine.rules_engine import RulesEngine
from app.models.company_data import CompanyData
from app.models.enums import RuleCategory, ScreeningOutcome, Verdict
from app.models.ipo_report import (
    ENGINE_VERSION,
    STANDARD_LIMITATIONS,
    EligibilityProgress,
    IPOReport,
)
from app.models.rule_result import RuleResult
from app.models.ruleset_version import RulesetVersion
from app.regulatory.registry import Ruleset
from app.rules.registry import RuleRegistry


def ruleset_version_model(ruleset: Ruleset) -> RulesetVersion:
    """Summarise a Ruleset as the RulesetVersion stored on reports."""
    instruments = sorted({spec.instrument for spec in ruleset.rules})
    return RulesetVersion(
        version=ruleset.version,
        effective_date=ruleset.effective_from,
        description=ruleset.description,
        regulations=instruments,
    )


def company_fingerprint(company: CompanyData) -> str:
    """SHA-256 of the canonical JSON of the evaluated input snapshot.

    The legacy ``ruleset_version`` label is excluded: it is not case data, and the
    applied ruleset is recorded separately on the report.
    """
    data = company.model_dump(mode="json", exclude={"ruleset_version"})
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DecisionEngine:
    """Orchestrates rule evaluation, outcome determination and report assembly."""

    def __init__(
        self, registry: RuleRegistry, *, regulatory_validation_confirmed: bool = False
    ) -> None:
        self._registry = registry
        self._rules_engine = RulesEngine(registry)
        self._gap_planner = GapPlanner()
        self._validation_confirmed = regulatory_validation_confirmed

    def evaluate(
        self,
        company: CompanyData,
        *,
        case_id: UUID | None = None,
        document_ids: list[str] | None = None,
        extraction_run_ids: list[str] | None = None,
    ) -> IPOReport:
        """Evaluate ``company`` and return a complete report."""
        results = self._rules_engine.evaluate_all(company)
        mandatory, advisory = self.classify_results(results)
        outcome = self.determine_outcome(company, mandatory)
        route = company.issue_details.listing_route
        observations = self.generate_observations(company, mandatory, advisory, outcome)
        limitations = list(STANDARD_LIMITATIONS)
        if self._validation_confirmed:
            limitations[1] = (
                "Regulatory validation is recorded as confirmed for this deployment; see the "
                "ruleset legal-review record for the rules covered."
            )
        return IPOReport(
            report_id=uuid4(),
            company_name=company.identification.company_name,
            status=outcome.legacy_status,
            outcome=outcome,
            listing_route=route,
            mandatory_progress=self.compute_progress(mandatory),
            advisory_progress=self.compute_progress(advisory),
            mandatory_results=mandatory,
            advisory_results=advisory,
            gap_analysis=self._gap_planner.generate(mandatory, company),
            observations=observations,
            ruleset_version=ruleset_version_model(self._registry.ruleset),
            evaluated_at=datetime.now(tz=UTC),
            engine_version=ENGINE_VERSION,
            case_id=case_id,
            input_sha256=company_fingerprint(company),
            document_ids=list(document_ids or []),
            extraction_run_ids=list(extraction_run_ids or []),
            unresolved_issues=self.unresolved_issues(company, results),
            limitations=limitations,
            regulatory_validation_confirmed=self._validation_confirmed,
        )

    @staticmethod
    def classify_results(results: list[RuleResult]) -> tuple[list[RuleResult], list[RuleResult]]:
        """Split into (mandatory, advisory), preserving order."""
        mandatory = [r for r in results if r.category == RuleCategory.MANDATORY]
        advisory = [r for r in results if r.category == RuleCategory.ADVISORY]
        return mandatory, advisory

    def determine_outcome(
        self, company: CompanyData, mandatory: list[RuleResult]
    ) -> ScreeningOutcome:
        """Apply the documented outcome precedence."""
        if company.issue_details.listing_route not in self._registry.ruleset.supported_routes:
            return ScreeningOutcome.UNSUPPORTED_SCOPE
        verdicts = {r.verdict for r in mandatory}
        if Verdict.FAIL in verdicts:
            return ScreeningOutcome.SCREENING_FAILURE
        if Verdict.REQUIRES_HUMAN_REVIEW in verdicts:
            return ScreeningOutcome.AWAITING_HUMAN_REVIEW
        if Verdict.INCONCLUSIVE in verdicts:
            return ScreeningOutcome.INSUFFICIENT_EVIDENCE
        return ScreeningOutcome.NO_FAILURE_IDENTIFIED

    @staticmethod
    def compute_progress(results: list[RuleResult]) -> EligibilityProgress:
        """Count verdicts. pass_percentage excludes NOT_APPLICABLE rules."""

        def count(v: Verdict) -> int:
            return sum(1 for r in results if r.verdict == v)

        passed = count(Verdict.PASS)
        applicable = len(results) - count(Verdict.NOT_APPLICABLE)
        pct = (
            (Decimal(passed) / Decimal(applicable) * Decimal(100)) if applicable else Decimal(0)
        ).quantize(Decimal("0.01"))
        return EligibilityProgress(
            total_rules=len(results),
            passed=passed,
            failed=count(Verdict.FAIL),
            inconclusive=count(Verdict.INCONCLUSIVE),
            requires_review=count(Verdict.REQUIRES_HUMAN_REVIEW),
            not_applicable=count(Verdict.NOT_APPLICABLE),
            pass_percentage=pct,
            failed_rule_ids=[r.rule_id for r in results if r.verdict == Verdict.FAIL],
        )

    def unresolved_issues(self, company: CompanyData, results: list[RuleResult]) -> list[str]:
        """List evidence gaps, review items and scope limitations."""
        issues: list[str] = []
        route = company.issue_details.listing_route
        if route not in self._registry.ruleset.supported_routes:
            issues.append(
                f"Listing route '{route.value}' is not supported by ruleset "
                f"{self._registry.version}."
            )
        for r in results:
            if r.verdict == Verdict.INCONCLUSIVE:
                issues.append(
                    f"{r.rule_id}: missing evidence — {', '.join(r.missing_inputs) or 'see rule'}"
                )
            elif r.requires_human_review:
                issues.append(
                    f"{r.rule_id}: review required — {'; '.join(r.review_reasons) or 'see rule'}"
                )
        unverified = sorted(
            r.rule_id
            for r in results
            if r.verification_status is not None
            and r.verification_status.value in ("unverified", "secondary_sources_only")
            and r.category == RuleCategory.MANDATORY
            and r.applicable
        )
        if unverified:
            issues.append(
                "Mandatory rules whose legal source is not verified against a primary text: "
                + ", ".join(unverified)
            )
        return issues

    @staticmethod
    def generate_observations(
        company: CompanyData,
        mandatory: list[RuleResult],
        advisory: list[RuleResult],
        outcome: ScreeningOutcome,
    ) -> list[str]:
        """Non-blocking factual observations."""
        obs: list[str] = []
        if outcome == ScreeningOutcome.NO_FAILURE_IDENTIFIED:
            obs.append(
                "No failure was identified among the supported mandatory screening checks on the "
                "evidence provided. This is not a legal determination of IPO eligibility."
            )
        if outcome == ScreeningOutcome.UNSUPPORTED_SCOPE:
            obs.append("The declared listing route is outside the supported screening scope.")
        reg6_1_failures = [
            r.rule_id
            for r in mandatory
            if r.verdict == Verdict.FAIL
            and r.rule_id
            in {
                "NTA_3CR",
                "MONETARY_ASSETS_50PCT",
                "AVG_OPERATING_PROFIT_15CR",
                "NET_WORTH_1CR",
                "ICDR_REG6_1D_NAME_CHANGE",
            }
        ]
        if reg6_1_failures:
            obs.append(
                "Reg 6(1) conditions failed (" + ", ".join(reg6_1_failures) + "). An issuer not "
                "satisfying Reg 6(1) may be eligible under Reg 6(2) (book-built issue with at "
                "least "
                "75% of the net offer allotted to QIBs); declare that route to screen it."
            )
        fys = company.financials.fiscal_years
        if len(fys) >= 3:
            revs = [fy.revenue for fy in fys[-3:]]
            if all(r is not None and r.is_reliable() for r in revs):
                values = [r.value for r in revs if r is not None]
                if values[-1] < values[0]:
                    obs.append(
                        f"Revenue declined from ₹{values[0]:,.2f} Cr to ₹{values[-1]:,.2f} Cr over "
                        "the last three reported periods."
                    )
        flagged = [r.rule_id for r in advisory if r.verdict == Verdict.FAIL]
        if flagged:
            obs.append("Advisory checks flagged: " + ", ".join(flagged) + ".")
        crim = company.litigation.has_criminal_cases
        if crim is not None and crim.is_reliable() and crim.value:
            obs.append(
                "Criminal litigation is reported as pending; this requires legal assessment."
            )
        return obs

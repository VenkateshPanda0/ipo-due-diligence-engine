"""
backend/app/models/ruleset_version.py

RulesetVersion model for reproducible reporting.

Every screening run is tagged with a RulesetVersion. Given the same
CompanyData and the same RulesetVersion, the engine must always produce
byte-identical output — this is the reproducibility guarantee.

RulesetVersions are bumped manually when regulations change. Historical
versions are retained so that past reports remain reproducible.

This module MUST NOT import from:
  - app.rules, app.intelligence, app.api, app.engine
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class RulesetVersion(BaseModel):
    """Pins the exact set of rules and thresholds used in an evaluation.

    RulesetVersion is a first-class domain concept. It tags every IPOReport
    so that the report can be reproduced at any future point by loading the
    same CompanyData and running against the same version.

    Versions follow semantic versioning (major.minor.patch). A version bump
    is required whenever any regulation threshold changes, a new rule is
    added, or an existing rule's logic is modified.

    Attributes:
        version: Semantic version string, e.g., "1.0.0".
        effective_date: Date when this ruleset became active.
        description: Human-readable summary of what regulations this
            version encodes.
        regulations: List of regulation sources this version covers,
            e.g., ["SEBI ICDR 2018", "LODR 2015", "Companies Act 2013"].

    Example:
        >>> from datetime import date
        >>> rv = RulesetVersion(
        ...     version="1.0.0",
        ...     effective_date=date(2026, 1, 1),
        ...     description="SEBI ICDR 2018, amended through 2025",
        ...     regulations=["SEBI ICDR 2018", "LODR 2015"],
        ... )
        >>> rv.version
        '1.0.0'
    """

    model_config = ConfigDict(frozen=True)

    version: str
    effective_date: date
    description: str
    regulations: list[str]

    def __str__(self) -> str:
        """Return the version string for logging and display.

        Returns:
            The semantic version string, e.g., "1.0.0".
        """
        return self.version


#: The default ruleset version used when no version is explicitly specified.
#: Encodes the implemented SEBI (ICDR), LODR, Companies Act, and exchange
#: listing subset. It is not a legal certification of complete regulatory
#: coverage.
DEFAULT_RULESET_VERSION = RulesetVersion(
    version="1.0.0",
    effective_date=date(2026, 1, 1),
    description=(
        "Implemented subset of SEBI (ICDR) Regulations, 2018, NSE/BSE listing "
        "requirements, LODR 2015, and Companies Act 2013; requires legal "
        "validation before production use"
    ),
    regulations=[
        "SEBI (ICDR) Regulations, 2018",
        "SEBI (LODR) Regulations, 2015",
        "Companies Act, 2013",
        "NSE Listing Requirements",
        "BSE Listing Requirements",
    ],
)

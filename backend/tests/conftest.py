"""
backend/tests/conftest.py

Shared pytest fixtures for the IPO Due Diligence Engine test suite.

Provides a ready-made `company` fixture for unit tests, shared factory
helpers, and a pre-built RuleRegistry fixture for engine/integration tests.
"""

from __future__ import annotations

import pytest

from app.models.company_data import CompanyData
from app.rules.registry import RuleRegistry
from tests.fixtures.company_data_factory import CompanyDataFactory


@pytest.fixture
def company() -> CompanyData:
    """Return a default eligible CompanyData instance.

    All fields have HIGH confidence and MANUAL extraction method.
    The company passes every mandatory and advisory rule.

    Returns:
        A fully constructed, immutable CompanyData.
    """
    return CompanyDataFactory.create()


@pytest.fixture
def registry() -> RuleRegistry:
    """Return a fully initialised RuleRegistry with all 16 rules.

    Returns:
        A RuleRegistry containing 11 mandatory and 5 advisory rules.
    """
    return RuleRegistry()

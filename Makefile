# Makefile for IPO Due Diligence Engine
# Targets: install, dev, test, lint, typecheck, coverage, clean, run

.PHONY: install dev test test-unit test-integration test-regression \
        lint format typecheck coverage clean run help

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

install:
	pip install -e ".[dev]"

dev: install
	pre-commit install

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test:
	pytest backend/tests/

test-unit:
	pytest backend/tests/unit/ -m unit

test-integration:
	pytest backend/tests/integration/ -m integration

test-regression:
	pytest backend/tests/regression/ -m regression

coverage:
	pytest backend/tests/ --cov=backend/app --cov-report=term-missing --cov-report=html

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:
	ruff check backend/

format:
	ruff format backend/

typecheck:
	mypy backend/app/

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

run:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name ".ruff_cache" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf dist/ build/ *.egg-info/ htmlcov/ .coverage

help:
	@echo "Available targets:"
	@echo "  install          Install production + dev dependencies"
	@echo "  dev              Install deps and set up pre-commit hooks"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-regression  Run regression (golden dataset) tests"
	@echo "  coverage         Run tests with coverage report"
	@echo "  lint             Run ruff linter"
	@echo "  format           Run ruff formatter"
	@echo "  typecheck        Run mypy strict type checking"
	@echo "  run              Start development server"
	@echo "  clean            Remove all generated artifacts"

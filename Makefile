# Makefile for IPO Due Diligence Engine
# Targets: install, dev, test, lint, typecheck, coverage, clean, run

.PHONY: install dev test test-unit test-integration test-regression test-frontend test-e2e benchmark \
        lint format typecheck coverage clean run help

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

install:
	pip install -e ".[dev]"
	cd frontend && npm ci

dev: install
	pre-commit install

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Backend tests run from backend/ so that `app` and `tests` import as packages.
test:
	cd backend && pytest -q tests/

test-unit:
	cd backend && pytest -q tests/unit/

test-integration:
	cd backend && pytest -q tests/integration/

test-regression:
	cd backend && pytest -q tests/regression/

test-frontend:
	cd frontend && npm run typecheck && npm test

test-e2e:
	cd frontend && npx playwright test

coverage:
	cd backend && pytest -q tests/ --cov=app --cov-report=term-missing --cov-report=html

benchmark:
	python scripts/benchmark_extraction.py --download --run

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
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

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

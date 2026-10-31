#!/bin/sh
# Format, lint, type-check and test. Exit status is non-zero if anything fails, so use it as
#   tools/gate.sh && git commit ...
# and never pipe it through tail/grep (that hides the status).
cd "$(dirname "$0")/.." || exit 1
uv run ruff format . >/dev/null 2>&1
uv run ruff check . >/tmp/rh-gate-lint.txt 2>&1 || { grep -v UV_NATIVE_TLS /tmp/rh-gate-lint.txt | head -30; echo "LINT FAILED"; exit 1; }
uv run mypy >/tmp/rh-gate-mypy.txt 2>&1 || { grep -v UV_NATIVE_TLS /tmp/rh-gate-mypy.txt | head -20; echo "MYPY FAILED"; exit 1; }
uv run pytest -q >/tmp/rh-gate-tests.txt 2>&1 || { tail -15 /tmp/rh-gate-tests.txt; echo "TESTS FAILED"; exit 1; }
echo "GATE OK"

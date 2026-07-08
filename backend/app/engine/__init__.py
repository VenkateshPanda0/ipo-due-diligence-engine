"""
backend/app/engine/__init__.py

Engine package — deterministic orchestration layer.

This package contains the rules engine, decision engine, evidence mapper,
and gap planner. All components are deterministic: given the same CompanyData
and the same ruleset, they always produce identical output.

ARCHITECTURAL CONSTRAINTS (ARCHITECTURE.md §4 Folder Responsibility Matrix):
  - engine/ imports from: models/, rules/
  - engine/ MUST NOT import from: parser/, api/
"""

"""
backend/app/rules/mandatory/__init__.py

Mandatory SEBI ICDR eligibility rules.

All 11 mandatory rules are implemented here. A FAIL on any mandatory rule
renders the company NOT_ELIGIBLE for a mainboard IPO. Rules operate only
on CompanyData and return RuleResult objects.
"""

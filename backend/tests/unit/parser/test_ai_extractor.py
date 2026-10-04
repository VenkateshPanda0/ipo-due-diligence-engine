from __future__ import annotations

import json

import pytest

from app.models.exceptions import ExtractionError
from app.parser.ai_extractor import AIExtractor
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_ai_extractor_does_not_trust_embedded_json_block() -> None:
    """Regression (D8): a document must not be able to inject its own CompanyData."""
    payload = json.dumps(CompanyDataFactory.create().model_dump(mode="json"))
    text = f"DRHP\nBEGIN_COMPANY_DATA_JSON\n{payload}\nEND_COMPANY_DATA_JSON"

    with pytest.raises(ExtractionError):
        AIExtractor().extract_company_data(text)


def test_ai_extractor_rejects_missing_json_block() -> None:
    with pytest.raises(ExtractionError):
        AIExtractor().extract_company_data("Annual Report without structured data")


def test_ai_extractor_extracts_company_data_from_local_labels_and_table() -> None:
    text = (
        """
Draft Red Herring Prospectus
Company Name: Acme Industries Pvt Ltd
CIN: L17110MH2000PLC019786
Industry: Manufacturing
Incorporation Date: 2000-04-01
Registered Office: Mumbai, Maharashtra
Years of Operation: 5
Promoter Name: Test Promoter
Promoter Holding: 75
Post Issue Promoter Holding: 75
Lock In Months: 18
Capex Issue: no
Total Directors: 6
Independent Directors: 3
Chair Executive: no
Chair Promoter: no
Audit Committee Members: 4
Audit Independent Members: 3
Audit Chair Independent: yes
Litigation Exposure: 0
Criminal Cases: no
Related Party Transaction Value: 2
Arm Length Certified: yes
Issue Size: 100
Post Issue Paid Up Capital: 15
Expected Market Cap: 800
Public Offer Percentage: 25
Issue Type: fresh
Auditor Name: Deloitte Haskins & Sells LLP
Auditor Qualifications: no
Modified Opinion: no
Years As Auditor: 3
"""
        "| FY | Revenue | Operating Profit | PAT | Net Worth | Net Tangible Assets | "
        "Monetary Assets | Total Assets | Total Liabilities | Paid Up Capital | "
        "Reserves and Surplus | EBITDA |\n"
        """
| FY2020 | 100 | 20 | 14 | 50 | 45 | 10 | 120 | 70 | 10 | 40 | 22 |
| FY2021 | 100 | 20 | 14 | 50 | 45 | 10 | 120 | 70 | 10 | 40 | 22 |
| FY2022 | 100 | 20 | 14 | 50 | 45 | 10 | 120 | 70 | 10 | 40 | 22 |
"""
    )

    company = AIExtractor().extract_company_data(text)

    assert company.identification.company_name == "Acme Industries Pvt Ltd"
    assert company.financials.fiscal_years[-1].net_worth.value == 50

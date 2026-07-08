from __future__ import annotations

import json

import pytest

from app.models.exceptions import UnsupportedDocumentError
from app.services.extraction_service import ExtractionService
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_extraction_service_builds_company_data_from_document_bytes() -> None:
    payload = json.dumps(CompanyDataFactory.create().model_dump(mode="json"))
    content = (
        "Annual Report\n"
        "BEGIN_COMPANY_DATA_JSON\n"
        f"{payload}\n"
        "END_COMPANY_DATA_JSON"
    ).encode()

    company = ExtractionService().extract_company_data("annual_report.pdf", content)

    assert company.identification.company_name == "Acme Industries Pvt Ltd"


def test_extraction_service_rejects_unknown_document() -> None:
    with pytest.raises(UnsupportedDocumentError):
        ExtractionService().extract_company_data("unknown.pdf", b"not enough")

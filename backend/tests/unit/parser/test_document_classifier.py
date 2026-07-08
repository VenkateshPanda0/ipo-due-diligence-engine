from __future__ import annotations

from app.parser.document_classifier import DocumentClassifier, DocumentType


def test_document_classifier_identifies_supported_documents() -> None:
    classifier = DocumentClassifier()

    assert classifier.classify("Draft Red Herring Prospectus") == DocumentType.DRHP
    assert classifier.classify("Annual Report and Directors' Report") == DocumentType.ANNUAL_REPORT
    assert (
        classifier.classify("Balance Sheet and Profit and Loss statement")
        == DocumentType.FINANCIAL_STATEMENT
    )
    assert classifier.classify("random file") == DocumentType.UNKNOWN

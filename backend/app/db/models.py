"""ORM models.

Append-only tables (``case_data_versions``, ``human_review_events``,
``audit_events``, ``review_item_events``) are protected by database triggers
created in the initial migration: UPDATE and DELETE raise an error.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class CaseRow(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    listing_route: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class CaseDataVersionRow(Base):
    __tablename__ = "case_data_versions"
    __table_args__ = (UniqueConstraint("case_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # type: ignore[type-arg]
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(String(36))
    extraction_run_id: Mapped[str | None] = mapped_column(String(36))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("case_id", "sha256"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    doc_type: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(60))
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # type: ignore[type-arg]
    quality: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # type: ignore[type-arg]
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pipeline_version: Mapped[str | None] = mapped_column(String(20))
    uploaded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ExtractionRunRow(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # type: ignore[type-arg]
    environment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # type: ignore[type-arg]
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # type: ignore[type-arg]
    pages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # type: ignore[type-arg]
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FieldResultRow(Base):
    __tablename__ = "field_results"
    __table_args__ = (Index("ix_field_results_run_field", "run_id", "field_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False
    )
    field_path: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    selected: Mapped[dict | None] = mapped_column(JSON)  # type: ignore[type-arg]
    candidates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # type: ignore[type-arg]
    reason: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)


class ReviewItemRow(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="SET NULL")
    )
    field_path: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    field_status: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    proposed: Mapped[dict | None] = mapped_column(JSON)  # type: ignore[type-arg]
    candidates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # type: ignore[type-arg]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewItemEventRow(Base):
    __tablename__ = "review_item_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("review_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    original_value: Mapped[dict | None] = mapped_column(JSON)  # type: ignore[type-arg]
    new_value: Mapped[dict | None] = mapped_column(JSON)  # type: ignore[type-arg]
    data_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ReportRow(Base):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), index=True
    )
    data_version: Mapped[int | None] = mapped_column(Integer)
    ruleset_version: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(40), index=True)
    legacy_status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class HumanReviewRow(Base):
    __tablename__ = "human_reviews"

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("reports.report_id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    machine_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class HumanReviewEventRow(Base):
    __tablename__ = "human_review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("human_reviews.review_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(200))
    decision: Mapped[str | None] = mapped_column(String(40))
    rationale: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # type: ignore[type-arg]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # type: ignore[type-arg]


APPEND_ONLY_TABLES = (
    "case_data_versions",
    "human_review_events",
    "audit_events",
    "review_item_events",
)

"""
Document upload, processing lifecycle and extraction merge.

Lifecycle (document.status):

    uploaded ──► extracting ──► completed
        │            │      └─► awaiting_review ──► completed (all items resolved)
        │            └────────► failed ──► extracting (retry)
        └─────────────────────► cancelled

Validation happens synchronously at upload: a file that fails validation is
rejected and never stored. Uploads are idempotent per case: the same bytes
(SHA-256) return the existing document instead of being processed twice.

Merge policy when extraction completes:
  * a field with no value, or a value that came from a previous extraction,
    receives the new extracted value;
  * a value entered or confirmed by a human is never overwritten — if the
    extraction disagrees, a review item records the conflict;
  * every NEEDS_VERIFICATION / CONFLICTING / unit-unknown field opens a review item.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.config import Settings
from app.db.base import Database
from app.db.models import (
    CaseRow,
    DocumentRow,
    ExtractionRunRow,
    FieldResultRow,
    ReviewItemEventRow,
    ReviewItemRow,
)
from app.db.repositories import audit, latest_version
from app.intelligence import PIPELINE_VERSION
from app.intelligence.ingest import validate_pdf
from app.intelligence.pipeline import PipelineConfig, PipelineResult, run_pipeline
from app.models.enums import FieldStatus
from app.models.exceptions import DocumentRejectedError, InvalidStateError, NotFoundError
from app.models.field_paths import get_value, set_value_in_place
from app.services.cases import CaseService, CaseStatus, ReviewItemStatus, is_human_value
from app.services.file_store import FileStore

logger = logging.getLogger(__name__)

_ALLOWED: dict[str, set[str]] = {
    "uploaded": {"extracting", "failed", "cancelled"},
    "extracting": {"completed", "awaiting_review", "failed", "cancelled"},
    "awaiting_review": {"completed", "extracting"},
    "completed": {"extracting"},
    "failed": {"extracting", "cancelled"},
    "cancelled": {"extracting"},
}
_REVIEW_STATUSES = {
    FieldStatus.EXTRACTED_NEEDS_VERIFICATION.value,
    FieldStatus.CONFLICTING_CANDIDATES.value,
}


def _transition(row: DocumentRow, new: str) -> None:
    if new not in _ALLOWED.get(row.status, set()):
        raise InvalidStateError(
            "document", row.status, f"Cannot move document from {row.status} to {new}."
        )
    row.status = new
    row.updated_at = datetime.now(tz=UTC)


class RateLimiter:
    """Sliding one-minute window per key (in-process)."""

    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True


class DocumentService:
    """Upload, process, retry and inspect documents."""

    def __init__(
        self, db: Database, store: FileStore, settings: Settings, *, inline: bool = False
    ) -> None:
        self._db = db
        self._store = store
        self._settings = settings
        self._inline = inline
        self._executor = (
            None
            if inline
            else ThreadPoolExecutor(
                max_workers=settings.worker_threads, thread_name_prefix="doc-worker"
            )
        )
        self.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # -- queries ----------------------------------------------------------------

    @staticmethod
    def _out(row: DocumentRow, stored: bool) -> dict[str, Any]:
        return {
            "id": row.id,
            "case_id": row.case_id,
            "sha256": row.sha256,
            "filename": row.original_filename,
            "size_bytes": row.size_bytes,
            "page_count": row.page_count,
            "doc_type": row.doc_type,
            "status": row.status,
            "stage": row.stage,
            "progress": row.progress,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "warnings": row.warnings,
            "quality": row.quality,
            "attempts": row.attempts,
            "pipeline_version": row.pipeline_version,
            "uploaded_by": row.uploaded_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "content_retained": stored,
        }

    def get(self, document_id: str) -> dict[str, Any]:
        with self._db.session() as s:
            row = s.get(DocumentRow, document_id)
            if row is None:
                raise NotFoundError("document", document_id)
            return self._out(row, self._store.exists(row.sha256))

    def list_documents(
        self, case_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        with self._db.session() as s:
            stmt = select(DocumentRow)
            if case_id:
                stmt = stmt.where(DocumentRow.case_id == case_id)
            if status:
                stmt = stmt.where(DocumentRow.status == status)
            rows = s.execute(stmt.order_by(DocumentRow.created_at.desc())).scalars().all()
            return [self._out(r, self._store.exists(r.sha256)) for r in rows]

    def content(self, document_id: str) -> bytes:
        doc = self.get(document_id)
        data = self._store.get(doc["sha256"])
        if data is None:
            raise InvalidStateError(
                "document", doc["status"], "Document content is no longer retained."
            )
        return data

    def extraction(self, document_id: str) -> dict[str, Any]:
        """Latest extraction run with per-field outcomes and candidates."""
        with self._db.session() as s:
            if s.get(DocumentRow, document_id) is None:
                raise NotFoundError("document", document_id)
            run = s.execute(
                select(ExtractionRunRow)
                .where(ExtractionRunRow.document_id == document_id)
                .order_by(ExtractionRunRow.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return {"document_id": document_id, "run": None, "fields": []}
            fields = (
                s.execute(
                    select(FieldResultRow)
                    .where(FieldResultRow.run_id == run.id)
                    .order_by(FieldResultRow.field_path)
                )
                .scalars()
                .all()
            )
            return {
                "document_id": document_id,
                "run": {
                    "id": run.id,
                    "pipeline_version": run.pipeline_version,
                    "status": run.status,
                    "config": run.config,
                    "environment": run.environment,
                    "summary": run.summary,
                    "pages": run.pages,
                    "error_message": run.error_message,
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                },
                "fields": [
                    {
                        "field_path": f.field_path,
                        "status": f.status,
                        "selected": f.selected,
                        "candidates": f.candidates,
                        "reason": f.reason,
                        "score": f.score,
                    }
                    for f in fields
                ],
            }

    # -- upload & processing -------------------------------------------------------

    def upload(
        self, case_id: str, filename: str | None, content: bytes, *, actor: str
    ) -> dict[str, Any]:
        info = validate_pdf(
            content,
            filename,
            max_bytes=self._settings.max_upload_size_bytes,
            max_pages=self._settings.max_pdf_pages,
        )
        with self._db.session() as s:
            case = s.get(CaseRow, case_id)
            if case is None:
                raise NotFoundError("case", case_id)
            if case.status == CaseStatus.ARCHIVED.value:
                raise InvalidStateError(
                    "case", case.status, "Archived cases do not accept documents."
                )
            existing = s.execute(
                select(DocumentRow).where(
                    DocumentRow.case_id == case_id, DocumentRow.sha256 == info.sha256
                )
            ).scalar_one_or_none()
            if existing is not None:
                return {
                    **self._out(existing, self._store.exists(existing.sha256)),
                    "duplicate": True,
                }
            stored = self._store.put(info.sha256, content)
            doc_id = str(uuid4())
            s.add(
                DocumentRow(
                    id=doc_id,
                    case_id=case_id,
                    sha256=info.sha256,
                    original_filename=info.display_name,
                    stored_name=stored,
                    size_bytes=info.size_bytes,
                    page_count=info.page_count,
                    status="uploaded",
                    stage="queued",
                    progress=0,
                    warnings=list(info.warnings),
                    quality={"pdf_version": info.pdf_version, "repaired": info.repaired},
                    uploaded_by=actor,
                )
            )
            case.status = CaseStatus.PROCESSING.value
            audit(
                s,
                actor=actor,
                action="document.uploaded",
                entity_type="document",
                entity_id=doc_id,
                case_id=case_id,
                details={"sha256": info.sha256, "pages": info.page_count, "bytes": info.size_bytes},
            )
        self._submit(doc_id)
        return {**self.get(doc_id), "duplicate": False}

    def retry(self, document_id: str, *, actor: str) -> dict[str, Any]:
        with self._db.session() as s:
            row = s.get(DocumentRow, document_id)
            if row is None:
                raise NotFoundError("document", document_id)
            if row.status in ("uploaded", "extracting"):
                raise InvalidStateError(
                    "document", row.status, "Document is already queued or processing."
                )
            if not self._store.exists(row.sha256):
                raise InvalidStateError(
                    "document", row.status, "Document content is no longer retained."
                )
            row.status, row.stage, row.progress, row.error_code, row.error_message = (
                "uploaded",
                "queued",
                0,
                None,
                None,
            )
            audit(
                s,
                actor=actor,
                action="document.retry",
                entity_type="document",
                entity_id=document_id,
                case_id=row.case_id,
            )
        self._submit(document_id)
        return self.get(document_id)

    def delete_content(self, document_id: str, *, actor: str) -> dict[str, Any]:
        """Delete the stored file (retention); metadata, hash and audit trail remain."""
        with self._db.session() as s:
            row = s.get(DocumentRow, document_id)
            if row is None:
                raise NotFoundError("document", document_id)
            if row.status in ("uploaded", "extracting"):
                raise InvalidStateError(
                    "document", row.status, "Cannot delete content while processing."
                )
            shared = s.execute(
                select(DocumentRow).where(
                    DocumentRow.sha256 == row.sha256, DocumentRow.id != row.id
                )
            ).first()
            if shared is None:
                self._store.delete(row.sha256)
            audit(
                s,
                actor=actor,
                action="document.content_deleted",
                entity_type="document",
                entity_id=document_id,
                case_id=row.case_id,
            )
        return self.get(document_id)

    def purge_expired(self) -> int:
        """Delete stored files older than the retention period (or all, if retention is off).

        Files are content-addressed and may be shared by several documents (the same
        PDF uploaded to different cases), so a file is deleted only when every
        document referencing it has expired and none is still being processed.
        """
        cutoff = datetime.now(tz=UTC) - timedelta(days=self._settings.retention_days)
        purged = 0
        with self._db.session() as s:
            rows = s.execute(select(DocumentRow)).scalars().all()
            by_sha: dict[str, list[DocumentRow]] = defaultdict(list)
            for row in rows:
                by_sha[row.sha256].append(row)

            def expired(row: DocumentRow) -> bool:
                if row.status in ("uploaded", "extracting"):
                    return False
                created = (
                    row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
                )
                return not self._settings.retain_documents or created < cutoff

            for sha, docs in by_sha.items():
                if not all(expired(d) for d in docs) or not self._store.delete(sha):
                    continue
                for row in docs:
                    purged += 1
                    audit(
                        s,
                        actor="system",
                        action="document.content_purged",
                        entity_type="document",
                        entity_id=row.id,
                        case_id=row.case_id,
                    )
        return purged

    def recover_interrupted(self) -> int:
        """Mark documents left in a processing state by a crash/restart as failed (retryable)."""
        with self._db.session() as s:
            rows = (
                s.execute(
                    select(DocumentRow).where(DocumentRow.status.in_(("uploaded", "extracting")))
                )
                .scalars()
                .all()
            )
            for row in rows:
                row.status, row.stage = "failed", "interrupted"
                row.error_code = "INTERRUPTED"
                row.error_message = "Processing was interrupted by a restart. Retry the document."
                audit(
                    s,
                    actor="system",
                    action="document.interrupted",
                    entity_type="document",
                    entity_id=row.id,
                    case_id=row.case_id,
                )
            return len(rows)

    def _submit(self, document_id: str) -> None:
        if self._executor is None:
            self.process(document_id)
        else:
            self._executor.submit(self.process, document_id)

    def _progress(self, document_id: str) -> Any:
        last = {"t": 0.0}

        def update(stage: str, pct: int) -> None:
            now = time.monotonic()
            if now - last["t"] < 0.5 and pct < 100:
                return
            last["t"] = now
            with self._db.session() as s:
                row = s.get(DocumentRow, document_id)
                if row is not None:
                    row.stage, row.progress = stage, max(0, min(100, pct))

        return update

    def process(self, document_id: str) -> None:
        """Run the extraction pipeline for one document (worker thread or inline)."""
        with self._db.session() as s:
            row = s.get(DocumentRow, document_id)
            if row is None or row.status != "uploaded":
                return
            _transition(row, "extracting")
            row.attempts += 1
            row.stage = "starting"
            case = s.get(CaseRow, row.case_id)
            assert case is not None
            company_name, filename, sha = case.company_name, row.original_filename, row.sha256
        run_id = str(uuid4())
        config = PipelineConfig(
            self._settings.ocr_enabled,
            self._settings.max_ocr_pages,
            self._settings.ocr_dpi,
            self._settings.processing_timeout_s,
        )
        try:
            content = self._store.get(sha)
            if content is None:
                raise DocumentRejectedError(
                    "missing_content", "Stored document content is missing."
                )
            result = run_pipeline(
                content,
                filename=filename,
                document_id=sha,
                company_name=company_name,
                config=config,
                progress=self._progress(document_id),
            )
        except Exception as exc:
            logger.exception("document_processing_failed", extra={"document_id": document_id})
            with self._db.session() as s:
                row = s.get(DocumentRow, document_id)
                assert row is not None
                _transition(row, "failed")
                row.stage = "failed"
                row.error_code = getattr(exc, "error_code", "PROCESSING_FAILED")
                row.error_message = (
                    exc.message
                    if hasattr(exc, "message")
                    else "Processing failed; see server logs with the document ID."
                )
                s.add(
                    ExtractionRunRow(
                        id=run_id,
                        document_id=document_id,
                        pipeline_version=PIPELINE_VERSION,
                        config=config.as_dict(),
                        status="failed",
                        error_message=row.error_message,
                        finished_at=datetime.now(tz=UTC),
                    )
                )
                audit(
                    s,
                    actor="system",
                    action="document.failed",
                    entity_type="document",
                    entity_id=document_id,
                    case_id=row.case_id,
                    details={"error_code": row.error_code},
                )
                case = s.get(CaseRow, row.case_id)
                if case is not None:
                    s.flush()
                    CaseService._refresh_status(s, case)
            return
        self._persist(document_id, run_id, result)

    def _persist(self, document_id: str, run_id: str, result: PipelineResult) -> None:
        with self._db.session() as s:
            row = s.get(DocumentRow, document_id)
            assert row is not None
            case = s.get(CaseRow, row.case_id)
            assert case is not None
            s.add(
                ExtractionRunRow(
                    id=run_id,
                    document_id=document_id,
                    pipeline_version=result.pipeline_version,
                    config=result.config,
                    environment=result.environment,
                    status="completed",
                    summary={
                        "metrics": result.metrics,
                        "warnings": result.warnings,
                        "doc_type": result.doc_type,
                        "tables_found": result.tables_found,
                        "suggestions": result.suggestions,
                        "unreadable_pages": result.unreadable_pages,
                    },
                    pages=result.pages,
                    finished_at=datetime.now(tz=UTC),
                )
            )
            s.flush()
            for o in result.outcomes:
                s.add(
                    FieldResultRow(
                        run_id=run_id,
                        field_path=o.field_path,
                        status=o.status.value,
                        selected=o.selected,
                        candidates=o.candidates,
                        reason=o.reason,
                        score=o.score,
                    )
                )
            # Work on a private copy: the stored version row is append-only.
            payload = copy.deepcopy(latest_version(s, case.id).payload)  # type: ignore[union-attr]
            self._supersede_open_items(s, document_id, run_id)
            opened = 0
            applied: list[str] = []
            for o in result.outcomes:
                current = get_value(payload, o.field_path)
                needs_review = o.status.value in _REVIEW_STATUSES or (
                    o.selected is None and o.status == FieldStatus.EXTRACTED_NEEDS_VERIFICATION
                )
                if o.selected is not None:
                    if is_human_value(current):
                        if current is not None and str(current.get("value")) != str(
                            o.selected.get("value")
                        ):
                            needs_review = True
                    else:
                        set_value_in_place(payload, o.field_path, o.selected)
                        applied.append(o.field_path)
                if needs_review:
                    opened += 1
                    reason = o.reason
                    if o.selected is not None and is_human_value(current):
                        reason = (
                            f"Extracted value {o.selected.get('value')} differs from the "
                            "human-entered value "
                            f"{current.get('value') if current else None}. {o.reason}"
                        )
                    s.add(
                        ReviewItemRow(
                            id=str(uuid4()),
                            case_id=case.id,
                            document_id=document_id,
                            run_id=run_id,
                            field_path=o.field_path,
                            reason=reason[:2000],
                            field_status=o.status.value,
                            status=ReviewItemStatus.OPEN.value,
                            proposed=o.selected,
                            candidates=o.candidates[:8],
                        )
                    )
            issue = payload.setdefault("issue_details", {})
            for key in ("issue_type", "is_book_built"):
                sug = result.suggestions.get(key)
                if sug and issue.get(key) is None:
                    issue[key] = sug["value"]
                    applied.append(f"issue_details.{key} (suggested)")
            if applied:
                CaseService._new_version(
                    s,
                    case,
                    payload,
                    source="extraction",
                    actor="system",
                    reason=f"extraction from {row.original_filename}",
                    document_id=document_id,
                    run_id=run_id,
                )
            row.doc_type = result.doc_type
            row.pipeline_version = result.pipeline_version
            row.warnings = sorted(set(row.warnings) | set(result.warnings))[:50]
            row.quality = {
                **row.quality,
                "metrics": result.metrics,
                "unreadable_pages": result.unreadable_pages[:50],
            }
            _transition(row, "awaiting_review" if opened else "completed")
            row.stage, row.progress = "done", 100
            audit(
                s,
                actor="system",
                action="document.extracted",
                entity_type="document",
                entity_id=document_id,
                case_id=case.id,
                details={
                    "run_id": run_id,
                    "fields_applied": len(applied),
                    "review_items": opened,
                    "pipeline_version": result.pipeline_version,
                },
            )
            s.flush()
            CaseService._refresh_status(s, case)

    @staticmethod
    def _supersede_open_items(s: Any, document_id: str, run_id: str) -> None:
        """Retire this document's unresolved items from earlier runs (re-extraction)."""
        stale = (
            s.execute(
                select(ReviewItemRow).where(
                    ReviewItemRow.document_id == document_id,
                    ReviewItemRow.status.in_(
                        (
                            ReviewItemStatus.OPEN.value,
                            ReviewItemStatus.MORE_EVIDENCE_REQUESTED.value,
                        )
                    ),
                )
            )
            .scalars()
            .all()
        )
        for item in stale:
            item.status = ReviewItemStatus.SUPERSEDED.value
            item.resolved_at = datetime.now(tz=UTC)
            s.add(
                ReviewItemEventRow(
                    item_id=item.id,
                    action="superseded",
                    actor="system",
                    reason=f"Replaced by extraction run {run_id}.",
                )
            )

    def mark_reviewed_documents(self, case_id: str) -> None:
        """Move documents to completed once none of their review items remain open."""
        with self._db.session() as s:
            docs = (
                s.execute(
                    select(DocumentRow).where(
                        DocumentRow.case_id == case_id, DocumentRow.status == "awaiting_review"
                    )
                )
                .scalars()
                .all()
            )
            for d in docs:
                open_items = s.execute(
                    select(ReviewItemRow.id).where(
                        ReviewItemRow.document_id == d.id,
                        ReviewItemRow.status == ReviewItemStatus.OPEN.value,
                    )
                ).first()
                if open_items is None:
                    _transition(d, "completed")

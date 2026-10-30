"""Public, filing-scoped recovery state from the durable job and its actual result."""
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models import Filing, Summary, SummaryJob
from app.services.provenance_service import source_safe_business_overview
from app.services.summary_placeholders import is_summary_ready
from app.utils.datetimes import ensure_utc, utcnow


def durable_progress_answer(db: Session, filing_id: int) -> dict | None:
    """Use one request session; a retained older summary cannot complete an active refresh."""
    job = db.query(SummaryJob).filter_by(filing_id=filing_id).first()
    if job is None:
        return None
    now = utcnow()
    answer = {
        "stage": job.stage, "status": job.status, "job_id": job.id,
        "generation": job.generation,
        "elapsedSeconds": max(0, (now - ensure_utc(job.created_at)).total_seconds()),
    }
    if job.status in {"complete", "partial"}:
        summary = db.query(Summary).filter_by(id=job.summary_id, filing_id=filing_id).first()
        filing = db.query(Filing).options(joinedload(Filing.content_cache)).filter_by(id=filing_id).first()
        raw = summary.raw_summary if summary and isinstance(summary.raw_summary, dict) else {}
        if summary and filing and is_summary_ready(source_safe_business_overview(summary, filing), raw.get("writer_error")):
            answer.update(stage="completed" if job.status == "complete" else "partial", summary_id=summary.id)
        else:
            answer.update(stage="error", status="failed", code="summary_result_unavailable")
    elif job.status == "failed":
        answer.update(stage="error", code=job.error_code)
    elif job.status == "queued" and job.last_dispatched_at is None:
        # A committed outbox intent is not evidence that Cloud Tasks accepted it.
        answer.update(stage="pending", status="dispatch_pending")
    if job.status in {"retry_wait", "failed"}:
        answer["retry_after_seconds"] = max(0, (ensure_utc(job.next_attempt_at) - now).total_seconds())
    return answer

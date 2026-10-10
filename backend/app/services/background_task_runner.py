"""Await existing business services while the task HTTP request owns its CPU allocation."""
from __future__ import annotations

import asyncio

from app.database import SessionLocal
from app.models import Company
from app.services import facts_service, filing_history_service, filing_scan_service
from app.services.durable_tasks import CompanyTask, FilingsTask, TaskEnvelope
from app.services.edgar.compat import sec_edgar_service


async def run_background_task(envelope: TaskEnvelope) -> None:
    if envelope.kind == "probe":
        if envelope.payload:
            raise ValueError("Probe tasks contain no business payload")
        return  # verify delivery/authentication without executing a business job
    if envelope.kind == "internal_job":
        from app.services.internal_task_runner import run_internal_task
        await run_internal_task(envelope.payload)
        return
    if envelope.kind == "filings":
        task = FilingsTask.model_validate(envelope.payload)
        with SessionLocal() as db:
            company = db.get(Company, task.company_id)
            if company is None:
                return  # deletion after enqueue makes the obsolete task a successful no-op
            cik = company.cik
        rows = await asyncio.wait_for(
            sec_edgar_service.get_filings(cik, task.filing_types), timeout=20.0,
        )
        with SessionLocal() as db:
            company = db.get(Company, task.company_id)
            if company is not None:
                filing_scan_service.upsert_filings(db, company, rows)
        return
    task = CompanyTask.model_validate(envelope.payload)
    if envelope.kind == "history":
        await filing_history_service.backfill_company_by_id(
            task.company_id, session_factory=SessionLocal, require_complete=True,
        )
    else:
        result = await facts_service.ingest_companyfacts_by_id(
            task.company_id, session_factory=SessionLocal,
        )
        if result.get("error") or (result.get("waited") and not result.get("synced")):
            raise RuntimeError("Companyfacts sync did not finish; retry the task")

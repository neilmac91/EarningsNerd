"""Admission stages: the filing snapshot, in-flight dedup, cache validity, the usage gate, the slot.

``load_filing`` reads the filing and any existing summary in one worker-owned session and serves
an existing summary straight away. ``join_or_lead`` is the A3 in-flight registry: join a running
generation and serve its persisted result, or claim leadership. ``admit`` copies the filing
attributes onto the run, decides whether the 24-hour content cache is valid, runs the usage /
fair-use gate for an authenticated caller and acquires the per-process generation slot.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, AsyncIterator, Optional

from sqlalchemy.orm import joinedload

from app import database
from app.models import Filing, Summary
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


async def load_filing(run: GenerationRun) -> AsyncIterator[dict]:
    """Snapshot the filing (+ company + content cache) and any existing summary; serve the latter."""
    filing_id = run.filing_id
    request_evidence = run.request_evidence

    # DB OP: Query filing and check for existing summary
    def get_filing_and_summary_sync():
        with database.SessionLocal() as session:
            filing = session.query(Filing).options(
                joinedload(Filing.content_cache),
                joinedload(Filing.company)
            ).filter(Filing.id == filing_id).first()
            summary = session.query(Summary).filter(Summary.filing_id == filing_id).first()
            company = filing.company if filing else None
            cache = filing.content_cache if filing else None
            filing_fields = {
                "company_name": company.name if company else "Unknown company",
                "company_cik": company.cik if company else None,
                "company_sic": company.sic if company else None,
                "document_url": filing.document_url,
                "filing_type": filing.filing_type,
                "accession_number": filing.accession_number,
                "filing_date": filing.filing_date,
                "report_period": filing.period_end_date,
                "cache_excerpt": cache.critical_excerpt if cache else None,
                "cache_updated_at": cache.updated_at if cache else None,
                "cache_created_at": cache.created_at if cache else None,
            } if filing else None
            summary_fields = None
            if summary:
                overview = pipeline.source_safe_business_overview(summary, filing)
                raw = summary.raw_summary if isinstance(summary.raw_summary, dict) else {}
                summary_fields = {
                    "business_overview": overview, "id": summary.id,
                    "ready": pipeline.is_summary_ready(overview, raw.get("writer_error")),
                }
            return filing_fields, summary_fields

    run.filing_fields, summary_fields = await run.run_sync_db(get_filing_and_summary_sync)

    if not run.filing_fields:
        if request_evidence is not None:
            request_evidence.reason = "filing_not_found"
        logger.warning(f"[stream:{filing_id}] Filing not found during stream generation.")
        yield {'type': 'error', 'message': 'Filing not found'}
        return

    # A run admitted to replace an unready row serves the row once another run has made it ready.
    if summary_fields and (not run.force_regenerate or (run.replace_unready_only and summary_fields["ready"])):
        if request_evidence is not None:
            request_evidence.delivery_path = "pipeline_cache"
        logger.info(f"[stream:{filing_id}] Existing summary found. Returning it.")
        yield {
            'type': 'complete',
            'summary': summary_fields["business_overview"],
            'summary_id': summary_fields["id"],
        }
        return


async def join_or_lead(run: GenerationRun) -> AsyncIterator[dict]:
    """A3 in-flight dedup: join the leader generating this filing and serve its result, or lead."""
    filing_id = run.filing_id
    request_evidence = run.request_evidence
    replace_unready_only = run.replace_unready_only

    # A3: a follower must recheck ownership after every join/read. Failed leaders
    # can wake several followers; only one may atomically claim the empty slot.
    def get_persisted_summary_fields():
        with database.SessionLocal() as s:
            summ = s.query(Summary).filter(Summary.filing_id == filing_id).first()
            persisted_filing = s.query(Filing).options(
                joinedload(Filing.content_cache)
            ).filter(Filing.id == filing_id).first()
            if not summ:
                return None
            overview = pipeline.source_safe_business_overview(summ, persisted_filing)
            raw = summ.raw_summary if isinstance(summ.raw_summary, dict) else {}
            # A run admitted to replace an unready row counts that row as absent: a leader that
            # failed left it in place, so this run claims the generation instead of serving it.
            if replace_unready_only and not pipeline.is_summary_ready(overview, raw.get("writer_error")):
                return None
            return {"business_overview": overview, "id": summ.id}

    waited = 0.0
    joined_generation = False
    while True:
        existing_generation = pipeline._inflight_generations.get(filing_id)
        if existing_generation is None:
            # No await between this read and claim; another coroutine cannot interleave.
            run.inflight_event = pipeline._claim_inflight(filing_id)
            if joined_generation:
                # A previous empty snapshot may return after a replacement committed
                # and released. Hold this new claim during a fresh read so another
                # replacement cannot finish between our absence check and admission.
                summary_fields = await run.run_sync_db(get_persisted_summary_fields)
                if summary_fields:
                    if request_evidence is not None:
                        request_evidence.delivery_path = "coalesced"
                    yield {'type': 'complete', 'summary': summary_fields["business_overview"], 'summary_id': summary_fields["id"]}
                    return
            break
        joined_generation = True
        if request_evidence is not None:
            request_evidence.delivery_path = "coalesced"
        logger.info(f"[stream:{filing_id}] Joining in-flight generation (dedup).")
        yield {'type': 'progress', 'stage': 'queued', 'message': 'Another request is already generating this analysis — joining it...', 'percent': 3, 'elapsed_seconds': int(pipeline.time.time() - run.pipeline_started_at)}
        while not existing_generation.is_set() and waited < pipeline.INFLIGHT_WAIT_CAP_SECONDS:
            try:
                await asyncio.wait_for(existing_generation.wait(), timeout=pipeline.settings.STREAM_HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                waited += pipeline.settings.STREAM_HEARTBEAT_INTERVAL
                yield {'type': 'progress', 'stage': 'summarizing', 'message': 'Finishing the shared analysis...', 'percent': min(50 + int(waited), 90), 'elapsed_seconds': int(pipeline.time.time() - run.pipeline_started_at)}

        # Re-read on a fresh session (the leader committed on its own) and serve it.
        summary_fields = await run.run_sync_db(get_persisted_summary_fields)
        if summary_fields:
            logger.info(f"[stream:{filing_id}] Served result from in-flight leader (dedup hit).")
            yield {'type': 'complete', 'summary': summary_fields["business_overview"], 'summary_id': summary_fields["id"]}
            return
        if waited >= pipeline.INFLIGHT_WAIT_CAP_SECONDS:
            # A follower's deadline grants no ownership of a still-running leader.
            # Use the existing timeout handling; release only lets go of our own claim.
            raise TimeoutError("In-flight summary wait budget exhausted")
        # The old leader failed, or a replacement claimed during the DB read. Loop
        # through the atomic registry check instead of overwriting that replacement.
        logger.info(f"[stream:{filing_id}] No shared result yet; rechecking generation ownership.")


async def admit(run: GenerationRun) -> AsyncIterator[dict]:
    """Filing attributes, 24-hour cache validity, the usage/fair-use gate and the generation slot."""
    filing_id, user_id = run.filing_id, run.user_id
    request_evidence = run.request_evidence

    # Cache company data and filing attributes from the fetched filing
    run.company_name = run.filing_fields["company_name"]
    run.company_cik = run.filing_fields["company_cik"]
    run.company_sic = run.filing_fields["company_sic"]
    run.filing_document_url = run.filing_fields["document_url"]
    run.filing_type = run.filing_fields["filing_type"]
    run.filing_accession_number = run.filing_fields["accession_number"]

    # Check the plain cached-content snapshot (no ORM reads after session closure).
    cached_excerpt = run.filing_fields["cache_excerpt"]
    run.cache_is_valid = False
    run.excerpt_from_cache = None

    if cached_excerpt:
        # Check age (valid if < 24 hours)
        last_updated = run.filing_fields["cache_updated_at"] or run.filing_fields["cache_created_at"]
        if not last_updated:
            # Should not happen given database constraints, but safe fallback
            last_updated = datetime.datetime.now(datetime.timezone.utc)
        elif last_updated.tzinfo is None:
            # SQLite (and some drivers) return naive datetimes; assume UTC so the
            # subtraction below doesn't raise "can't subtract offset-naive and
            # offset-aware datetimes" and crash the cached-content path.
            last_updated = last_updated.replace(tzinfo=datetime.timezone.utc)

        age = datetime.datetime.now(datetime.timezone.utc) - last_updated
        if age < timedelta(hours=24):
            run.cache_is_valid = True
            run.excerpt_from_cache = cached_excerpt
            logger.info(f"[stream:{filing_id}] Using cached content (age: {age})")

    # Check usage limits for authenticated user
    if run.current_user:
        current_user = run.current_user

        def check_usage_sync() -> tuple[bool, int, Optional[int], bool, Optional[str]]:
            with database.SessionLocal() as usage_session:
                return pipeline._check_usage_and_plan(current_user, usage_session)

        can_generate, current_count, limit, user_is_unlimited, run.usage_reservation_token = await run.run_sync_db(check_usage_sync)
        if not can_generate:
            # A Pro user is billing-unlimited, so a block here means the INVISIBLE fair-use
            # ceiling (PRO_SUMMARY_MONTHLY_CAP) tripped — degrade with a generic message,
            # never an upsell, and skip the paywall funnel event (a Pro user isn't paywalled).
            if request_evidence is not None:
                request_evidence.reason = "fair_use" if user_is_unlimited else "monthly_quota"
            if user_is_unlimited:
                logger.warning(
                    f"[stream:{filing_id}] Pro user {user_id} hit summary fair-use ceiling ({limit})."
                )
                yield {
                    "type": "error",
                    "message": (
                        "We've temporarily paused new summary generation on your account due "
                        "to unusually high recent volume. Please try again later or contact support."
                    ),
                }
                return
            logger.warning(f"[stream:{filing_id}] User {user_id} exceeded monthly summary limit ({limit}).")
            # Demand/pricing signal: record when a free user hits the wall.
            run.emit_funnel(
                run.telemetry_distinct_id,
                pipeline.EVENT_PAYWALL_HIT,
                entry_point=run.telemetry_entry_point,
                limit=limit,
                summaries_used=current_count,
            )
            message = (
                "You've reached your monthly limit of "
                f"{limit} summaries. Upgrade to Pro for unlimited summaries."
            )
            yield {"type": "error", "message": message}
            return
        logger.info(f"[stream:{filing_id}] Usage limit check passed for user {user_id}. Current count: {current_count}/{limit}")
    else:
        # current_user=None is only reachable from the internal drains now (cron
        # pregenerate / admin refresh) — the user-facing route requires an account.
        logger.info(f"[stream:{filing_id}] Internal caller (no user) — per-user quota not applicable.")

    if request_evidence is not None:
        request_evidence.delivery_path = "generation"

    # Bound concurrent generations per process (protects the single vCPU). Acquired here —
    # AFTER the usage/fair-use gate so rejected/abusive requests never occupy a slot, and only
    # on the leader path (dedup waiters returned above) so it can't deadlock a leader against
    # its waiters. Released in ``GenerationRun.release``. A long queue wait counts against the
    # pipeline timeout, which is the intended back-pressure. A follower that exhausts its wait
    # budget exits without stealing ownership; no follower holds a generation slot.
    run.generation_semaphore = pipeline._get_generation_semaphore()
    await run.generation_semaphore.acquire()
    run.generation_slot_held = True

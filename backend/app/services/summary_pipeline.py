"""Transport-agnostic summary-generation pipeline.

This module owns the end-to-end summary pipeline that was previously inlined as the
``stream_summary()`` generator inside ``app/routers/summaries.py``. It yields plain
``dict`` events (``{"type": "progress"|"chunk"|"partial"|"complete"|"error", ...}``) so
the SSE endpoint can format them for the wire while the business logic lives here.

Phase 1 (M7) goal: extract the logic with **zero behaviour change** to the SSE contract.
The yielded dicts are the payloads formatted by the router. Background/cron callers drain
this same generator; database operations own short sessions inside their worker threads.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from dataclasses import dataclass, replace
from typing import AsyncIterator, Optional

from datetime import timedelta  # noqa: F401  (inline stages until extraction)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError  # noqa: F401  (inline stages until extraction)
from sqlalchemy.orm import joinedload  # noqa: F401  (inline stages until extraction)

from app import database
from app.config import settings
from app.models import Filing, Summary, User, Subscription  # noqa: F401  (inline stages until extraction)
from app.schemas import attach_normalized_facts
from app.services.ai.normalize import _section_has_content
from app.services.metric_delta_service import (
    EXACT_CONTEXT_KEY,
    EXACT_CONTEXT_VERSION,
    bind_exact_xbrl_deltas,
)
from app.services.summary_request_evidence import SummaryRequestEvidence
from app.services.posthog_client import EVENT_GENERATION_STARTED
from app.services.subscription_service import check_usage_limit, reserve_summary_use
from app.services.entitlements import get_entitlements
from app.services.provenance_service import (
    RISK_PROJECTION_KEY,
    RISK_SOURCE_CONTEXT_KEY,
    RISK_SOURCE_CONTEXT_VERSION,
    project_risk_list,
    replace_business_overview_risks,
)
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from app.services.summary_schema import TRACKED_SECTIONS_V2

# --- Patch seams for the stage modules ---------------------------------------------------------
# ``stream_filing_summary`` is a stage map over ``app/services/summary_stages``. Those modules reach
# every collaborator below as ``summary_pipeline.<name>`` AT CALL TIME, so the tests' patches on THIS
# module keep taking effect after the split (``patch.object(summary_pipeline, "record_progress", …)``,
# ``monkeypatch.setattr(pipeline, "run_in_threadpool", …)``, the ``asyncio`` proxy, ``time`` for a
# fake clock …). Nothing in this module calls most of them any more; they are kept here on purpose.
# Gate: tests/unit/test_summary_stages_seams.py (every ``pipeline.<name>`` a stage uses must exist here).
import time  # noqa: F401
# Keep the existing dispatch seam for lifecycle tests while tracking actual worker futures.
from app.services.request_work import RequestWork, run_owned_sync as run_in_threadpool  # noqa: F401
from app.services.ai.provider_requests import provider_start_signal  # noqa: F401
from app.services.content_cache import upsert_content_cache  # noqa: F401
from app.services.edgar.compat import sec_edgar_service, xbrl_service  # noqa: F401
from app.services.edgar.sixk_classifier import classify_sixk_text  # noqa: F401
from app.services.edgar.sixk_extractor import get_sixk_text  # noqa: F401
from app.services.edgar.statement_context import acquire_statement_context  # noqa: F401
from app.services.fallback_summary import generate_xbrl_summary  # noqa: F401
from app.services.openai_service import openai_service  # noqa: F401
from app.services.posthog_client import (  # noqa: F401
    EVENT_GENERATION_FAILED,
    EVENT_GENERATION_SUCCEEDED,
    EVENT_GENERATION_TIMED_OUT,
    EVENT_PAYWALL_HIT,
    capture_funnel_event,
)
from app.services.provenance_service import source_safe_business_overview  # noqa: F401
from app.services.subscription_service import (  # noqa: F401
    convert_reservation,
    get_current_month,
    increment_user_usage,
    refund_summary_use,
    release_reservation,
)
from app.services.summary_generation_service import (  # noqa: F401
    assess_quality,
    get_or_cache_excerpt,
    quality_tier_rank,
    record_progress,
)
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION  # noqa: F401
# Module objects only (never ``from … import <name>``): the stage modules import this module for the
# seams above, so either import order must work — see the package docstring.
from app.services.summary_stages import (
    admission, enrichment, failure, fetch, generation_run,
)

logger = logging.getLogger(__name__)

# A3: process-local registry of in-flight summary generations, keyed by filing_id. When a request
# would generate a filing another request is already generating, it waits for that one and serves the
# persisted result — collapsing a concurrent "thundering herd" on a newly-filed popular report into a
# single generation within this process. API instances and jobs each have their own registry;
# this does not prevent duplicate provider work across processes while Redis stays off.
_inflight_generations: dict[int, asyncio.Event] = {}
INFLIGHT_WAIT_CAP_SECONDS = 110.0  # just under PIPELINE_TIMEOUT_SECONDS (120s)


def _finalized_section_coverage(
    sections_info: dict, previous_snapshot: object,
) -> dict:
    """Align Risks coverage with the finalized source projection.

    Producers own the non-Risks coverage booleans because they know which placeholder rules they
    applied. This shared persistence/progress boundary preserves those values, recounts Risks from
    its finalized source-bound list, and then rebuilds the canonical aggregate fields.
    """
    prior_per_section = (
        previous_snapshot.get("per_section")
        if isinstance(previous_snapshot, dict)
        else None
    )
    # Aggregate-only snapshots predate the canonical per-section contract. Their non-Risks
    # contributions cannot be reconstructed from compatibility columns without changing historical
    # quality semantics. Current primary and timeout producers both provide per_section, so retain
    # this legacy shape unchanged rather than guessing.
    if isinstance(previous_snapshot, dict) and not isinstance(prior_per_section, dict):
        return dict(previous_snapshot)
    coverage_map = {
        section: (
            bool(prior_per_section.get(section))
            if isinstance(prior_per_section, dict)
            else _section_has_content(sections_info.get(section))
        )
        for section in TRACKED_SECTIONS_V2
    }
    # Risks are the section this finalizer projects. Recount it from the finalized source-bound
    # list even when an earlier producer supplied a complete non-risk coverage map.
    coverage_map["risks"] = _section_has_content(sections_info.get("risks"))
    covered = [section for section, has_content in coverage_map.items() if has_content]
    missing = [section for section, has_content in coverage_map.items() if not has_content]
    total_count = len(coverage_map)
    covered_count = len(covered)
    prior_not_applicable = (
        previous_snapshot.get("not_applicable", [])
        if isinstance(previous_snapshot, dict)
        else []
    )
    not_applicable = [
        section for section in prior_not_applicable
        if section in coverage_map and not coverage_map[section]
    ]
    return {
        "per_section": coverage_map,
        "covered": covered,
        "missing": missing,
        "covered_count": covered_count,
        "total_count": total_count,
        "coverage_ratio": (covered_count / total_count) if total_count else None,
        "not_applicable": not_applicable,
    }


def _finalize_summary_projection(
    summary_payload: dict,
    xbrl_metrics: Optional[dict],
    summary_status: str,
    source_text: str = "",
    filing_document_url: Optional[str] = None,
) -> tuple[str, dict, dict, Optional[dict]]:
    """Build the one persisted/streamed projection after any generator has returned.

    The provider normally arrives with exact deltas already bound.  The timeout fallback does not,
    so this shared boundary repeats the idempotent binding before persistence and stamps ownership
    only after every metric row has passed through it.  Existing generated markdown is preserved;
    cached reads and PDF/CSV exports consume the corrected structured projection.
    """
    markdown = summary_payload.get("business_overview") or ""
    raw_summary = summary_payload.get("raw_summary") or {}
    sections_info = (raw_summary.get("sections") or {}) or {}

    financial_section = sections_info.get("results_that_matter")
    normalized_financial_section = attach_normalized_facts(financial_section, xbrl_metrics)
    has_metric_table = (
        isinstance(normalized_financial_section, dict)
        and isinstance(normalized_financial_section.get("table"), list)
    )
    if has_metric_table:
        normalized_financial_section = bind_exact_xbrl_deltas(
            normalized_financial_section, xbrl_metrics
        )
        sections_info["results_that_matter"] = normalized_financial_section

    # Risks compose at this same shared post-generator boundary. Reserved producer metadata and the
    # nonselected alias are discarded before the candidate list is matched to this generation's
    # filing source; only code then stamps renderer ownership.
    sections_info.pop(RISK_PROJECTION_KEY, None)
    sections_info.pop("risk_factors", None)
    raw_summary.pop(RISK_SOURCE_CONTEXT_KEY, None)
    summary_payload.pop("_risk_source_candidate_count", None)
    private_candidates = summary_payload.pop("_risk_source_candidates", None)
    private_source = summary_payload.pop("_risk_source_grounding", None)
    risk_candidates = (
        private_candidates if isinstance(private_candidates, list)
        else summary_payload.get("risk_factors") or []
    )
    risk_section, risk_projection = project_risk_list(
        risk_candidates,
        sources=(
            [private_source]
            if isinstance(private_source, str) and private_source.strip()
            else [source_text] if isinstance(source_text, str) and source_text.strip() else []
        ),
        base_url=filing_document_url,
    )
    sections_info["risks"] = risk_section
    sections_info[RISK_PROJECTION_KEY] = risk_projection
    raw_summary["sections"] = sections_info
    raw_summary["section_coverage"] = _finalized_section_coverage(
        sections_info, raw_summary.get("section_coverage")
    )
    raw_summary["status"] = summary_status
    raw_summary["schema_version"] = SUMMARY_SCHEMA_VERSION

    if has_metric_table:
        raw_summary[EXACT_CONTEXT_KEY] = EXACT_CONTEXT_VERSION
    raw_summary[RISK_SOURCE_CONTEXT_KEY] = RISK_SOURCE_CONTEXT_VERSION

    markdown = replace_business_overview_risks(markdown, raw_summary)
    summary_payload["business_overview"] = markdown
    summary_payload["raw_summary"] = raw_summary
    return markdown, raw_summary, sections_info, normalized_financial_section


@dataclass(frozen=True)
class _GenerationSubscription:
    status: Optional[str]
    trial_end: Optional[datetime.datetime]


@dataclass(frozen=True)
class GenerationUserSnapshot:
    id: int
    is_pro: bool
    subscription: Optional[_GenerationSubscription]
    subscription_unloaded: bool = False


def snapshot_generation_user(user: User, user_id: int) -> GenerationUserSnapshot:
    """Copy identity inputs without triggering ORM loads on the request thread.

    Already supplied subscription state stays authoritative for this request. An
    unloaded relationship (or expired subscription fields) is resolved separately,
    after the request session closes. This records inputs, not entitlement decisions.
    """
    state = sa_inspect(user, raiseerr=False)
    if state is None:
        # Standalone identities are supported by internal callers and locked anchors.
        is_pro = bool(getattr(user, "is_pro", False))
        subscription = getattr(user, "subscription", None)
        unloaded = False
    else:
        is_pro = bool(state.dict.get("is_pro", False))
        subscription = state.dict.get("subscription")
        unloaded = "subscription" not in state.dict and state.identity is not None

    copied_subscription = None
    if subscription is not None:
        sub_state = sa_inspect(subscription, raiseerr=False)
        if sub_state is not None:
            unloaded = sub_state.identity is not None and not {"status", "trial_end"}.issubset(sub_state.dict)
            if not unloaded:
                copied_subscription = _GenerationSubscription(
                    sub_state.dict.get("status"), sub_state.dict.get("trial_end")
                )
        else:
            copied_subscription = _GenerationSubscription(
                getattr(subscription, "status", None), getattr(subscription, "trial_end", None)
            )
    return GenerationUserSnapshot(user_id, is_pro, copied_subscription, unloaded)


def load_generation_user(snapshot: GenerationUserSnapshot) -> GenerationUserSnapshot:
    """Resolve only missing subscription inputs in a fresh worker-owned transaction."""
    if not snapshot.subscription_unloaded:
        return snapshot
    with database.SessionLocal() as session:
        row = session.query(Subscription.status, Subscription.trial_end).filter(
            Subscription.user_id == snapshot.id
        ).first()
        subscription = _GenerationSubscription(row.status, row.trial_end) if row else None
        return replace(snapshot, subscription=subscription, subscription_unloaded=False)


def _claim_inflight(filing_id: int) -> asyncio.Event:
    """Register this request as the leader generating ``filing_id``; returns the event to release."""
    event = asyncio.Event()
    _inflight_generations[filing_id] = event
    return event


def _release_inflight(filing_id: int, event: asyncio.Event) -> None:
    """Release leadership (only if we still own the slot) and wake any waiters."""
    if _inflight_generations.get(filing_id) is event:
        _inflight_generations.pop(filing_id, None)
    event.set()


def _check_usage_and_plan(user, db) -> tuple[bool, int, Optional[int], bool, Optional[str]]:
    """One threadpool round-trip for the usage gate + the Pro/Free discriminator.

    Runs synchronously (call via ``run_sync_db``): ``check_usage_limit`` and the entitlements
    resolution may both lazy-load ``user.subscription`` — sync DB I/O that must stay off the event
    loop. Resolving both here avoids a second thread hop on the block path and keeps a single
    source for "is this user billing-unlimited". Looks up ``check_usage_limit`` at call time so
    test patches of the module global still apply; a request the read admits is then reserved
    under the serialized ``reserve_summary_use`` decision (E07b), which may still block it.
    The fifth element is the reservation token (None when nothing was reserved).
    """
    can_generate, current_count, limit = check_usage_limit(user, db)
    is_unlimited = get_entitlements(user).has_unlimited_summaries
    if not can_generate:
        return can_generate, current_count, limit, is_unlimited, None
    can_generate, current_count, limit, token = reserve_summary_use(user, db)
    return can_generate, current_count, limit, is_unlimited, token


# Bounds concurrent full generations per process to protect the single vCPU (see
# settings.MAX_CONCURRENT_GENERATIONS). Lazily constructed AND keyed to the running event loop:
# asyncio primitives bind to a loop on first contended await, so a cached semaphore from a previous
# loop (pytest-asyncio creates one per test; a restarted loop in prod) would raise "bound to a
# different event loop". Acquired ONLY on the generation (leader) path — dedup waiters return
# before claiming a slot — so it can never deadlock a leader against its own waiters.
_generation_semaphore: Optional[asyncio.Semaphore] = None
_generation_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_generation_semaphore() -> asyncio.Semaphore:
    global _generation_semaphore, _generation_semaphore_loop
    loop = asyncio.get_running_loop()  # only called from async context
    if _generation_semaphore is None or _generation_semaphore_loop is not loop:
        # <= 0 disables the ceiling (unbounded), mirroring PRO_SUMMARY_MONTHLY_CAP=0. Using a large
        # count rather than skipping acquire keeps the acquire/release bookkeeping uniform.
        limit = settings.MAX_CONCURRENT_GENERATIONS
        _generation_semaphore = asyncio.Semaphore(limit if limit > 0 else 2**31)
        _generation_semaphore_loop = loop
    return _generation_semaphore


# Pipeline outcome timeout. This is a *backstop* against a genuine hang/runaway — it sits
# deliberately above the sum of the per-step budgets (≈15s fetch + 18s enrichment + 75s AI
# fallback ≈ 108s) so the per-step timeouts remain the primary controls and the AI fallback
# always gets to produce a (partial) result rather than being pre-empted into a timeout error.
# The whole pipeline body runs inside `asyncio.timeout(PIPELINE_TIMEOUT_SECONDS)`.
# Final cleanup may exceed this deadline while a synchronous worker finishes; cancelling its
# asyncio waiter cannot kill its thread, and releasing ownership early would abandon that work.
PIPELINE_TIMEOUT_SECONDS = 120

# Timeout for XBRL/excerpt enrichment. XBRL fetch starts concurrently with the filing
# document fetch, so this is the *additional* budget we wait at the join point. The XBRL
# service's own internal timeout is 15s (EDGAR_DEFAULT_TIMEOUT_SECONDS); an 8s ceiling here
# silently truncated it on large issuers, producing hollow financials.
CONTEXT_ENRICHMENT_TIMEOUT_SECONDS = 18.0


def to_sse(event: dict) -> str:
    """Format a pipeline event dict as an SSE ``data:`` frame."""
    return f"data: {json.dumps(event)}\n\n"


TERMINAL_EVENT_TYPES = frozenset({"complete", "partial", "error"})


def _stage_sequence():
    """The stage map, in pipeline order.

    Built per call rather than at import: the stage modules import this module for their patch
    seams, so their attributes are not guaranteed to exist while this module is still initializing.
    """
    return (
        admission.load_filing,
        admission.join_or_lead,
        admission.admit,
        fetch.fetch_document,
        enrichment.parse_and_enrich,
    )



async def stream_filing_summary(
    *,
    filing_id: int,
    current_user: Optional[User | GenerationUserSnapshot],
    user_id: Optional[int],
    telemetry_distinct_id: str,
    telemetry_entry_point: Optional[str],
    telemetry_ctx: dict,
    emit_funnel_telemetry: bool = True,
    force_regenerate: bool = False,
    request_evidence: SummaryRequestEvidence | None = None,
) -> AsyncIterator[dict]:
    """Run the summary pipeline for ``filing_id``, yielding event dicts.

    Caller is responsible for HTTP concerns (rate limiting, auth — user-facing generation is
    account-required at the router boundary, the cached/existing
    summary short-circuit) and for capturing the telemetry context before invoking this — the
    router releases its session before streaming. Each DB unit here owns its session
    inside the worker; no ORM query result survives into an admission or provider wait.

    The body is the stage map in ``_stage_sequence`` (``app/services/summary_stages``), driven over
    one shared ``GenerationRun``; a stage's terminal event ends the pipeline. The timeout, the two
    failure handlers and the cleanup in ``finally`` are unchanged in order and ownership.
    """
    run = generation_run.GenerationRun(
        filing_id=filing_id,
        current_user=current_user,
        user_id=user_id,
        telemetry_distinct_id=telemetry_distinct_id,
        telemetry_entry_point=telemetry_entry_point,
        telemetry_ctx=telemetry_ctx,
        emit_funnel_telemetry=emit_funnel_telemetry,
        force_regenerate=force_regenerate,
        request_evidence=request_evidence,
    )
    run.emit_funnel(
        telemetry_distinct_id,
        EVENT_GENERATION_STARTED,
        entry_point=telemetry_entry_point,
        **telemetry_ctx,
    )

    try:
        async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
            logger.info(f"[stream:{filing_id}] Stream generator started (timeout: {PIPELINE_TIMEOUT_SECONDS}s)")
            yield {'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...', 'percent': 0}

            for stage in _stage_sequence():
                events = stage(run)
                try:
                    async for event in events:
                        yield event
                        if event["type"] in TERMINAL_EVENT_TYPES:
                            return
                finally:
                    # Close the stage deterministically: a stage left suspended at a yield after a
                    # disconnect would otherwise be finalized later by the event loop's GC hook.
                    await events.aclose()

            # --- generation.generate (inline until its extraction commit) ---
            filing_id = run.filing_id

            # A5: when STREAM_SECTION_REVEAL is on, stream the extraction and push progressive section
            # previews onto a queue that the heartbeat loop drains below. The callback can't yield from
            # this generator, so the queue decouples them. Off by default → behaviour unchanged.
            preview_queue: Optional[asyncio.Queue] = (
                asyncio.Queue() if settings.STREAM_SECTION_REVEAL else None
            )
            summary_stream_cb = None
            if preview_queue is not None:
                async def summary_stream_cb(preview_md: str) -> None:
                    preview_queue.put_nowait(preview_md)

            # Now run AI summarization (with excerpt/XBRL if available)
            # Wrap in task to enable heartbeat loop while waiting
            statement_source = None
            report_period = run.filing_fields.get("report_period")
            if run.filing_text and report_period is not None:
                with run.worker_owner.activate():
                    statement_source = await run_in_threadpool(
                        acquire_statement_context, run.filing_text, accession=run.filing_accession_number,
                        document_url=run.filing_document_url, form=run.filing_type,
                        report_period=report_period.date().isoformat(),
                    )
            if run.is_six_k:
                # W3-8b: deterministic pre-classification of the final 6-K grounding selects the prompt
                # variant and is recorded on the stored summary for audit. Placed after every grounding
                # branch (fresh exhibit fetch, primary-document fallback, or a valid content cache whose
                # text arrives as the excerpt) so a cached or regenerated 6-K is classified too.
                sixk = classify_sixk_text(run.filing_text or run.excerpt)
                run.sixk_class, run.sixk_class_audit = sixk.sixk_class, sixk.as_audit()
            if run.request_evidence is not None:
                run.request_evidence.summary_service_invoked = True

            # Metering point: see ``GenerationRun.begin_charge`` — the held admission lease becomes a
            # counted unit when the dispatcher signals that the provider request is issued.
            run.provider_started = asyncio.Event()

            with provider_start_signal(run.on_provider_start), run.worker_owner.activate():
                run.summary_task = asyncio.create_task(openai_service.summarize_filing(
                    run.filing_text,
                    run.company_name,
                    run.filing_type,
                    xbrl_metrics=run.xbrl_metrics,
                    filing_excerpt=run.excerpt,
                    stream_cb=summary_stream_cb,
                    **({"statement_source": statement_source} if statement_source else {}),
                    **({"sixk_class": run.sixk_class, "sixk_class_audit": run.sixk_class_audit} if run.sixk_class else {}),
                ))
            run.provider_started_waiter = asyncio.ensure_future(run.provider_started.wait())

            SUMMARIZE_MESSAGES = [
                "Analyzing financial highlights...",
                "Cross-referencing with XBRL data...",
                "Extracting key metrics from MD&A...",
                "Identifying significant risk factors...",
                "Synthesizing investment insights...",
                "Reviewing guidance and outlook...",
            ]
            summarize_heartbeat_index = 0
            run.summary_payload = None
            provider_fallback = False  # the payload is the deterministic XBRL fallback, not a provider result

            # Build fallback kwargs once to avoid duplication (DRY principle)
            fallback_kwargs = {
                "xbrl_data": run.xbrl_metrics,
                "company_name": run.company_name,
                "filing_date": run.filing_fields["filing_date"].isoformat() if run.filing_fields["filing_date"] else "Unknown",
                "filing_text": run.filing_text,
                "filing_type": run.filing_type,
                "filing_excerpt": run.excerpt,
            }

            while not run.summary_task.done():
                if run.provider_started.is_set():
                    await run.charge_lease()  # the provider request is issued: count the unit now
                awaited = [run.summary_task] if run.provider_started_waiter.done() else [run.summary_task, run.provider_started_waiter]
                done, pending = await asyncio.wait(
                    awaited,
                    timeout=settings.STREAM_HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )

                if run.summary_task in done:
                    break
                if run.provider_started_waiter in done:
                    continue  # charge at the top of the loop before the next heartbeat wait

                # Check for AI Timeout (60s)
                current_time = time.time()
                time_in_stage = current_time - run.stage_started_at

                if time_in_stage > 75.0:
                    logger.warning(f"[stream:{filing_id}] AI summarization timed out after {time_in_stage:.1f}s. Switching to fallback.")
                    run.summary_task.cancel()
                    await asyncio.gather(run.summary_task, return_exceptions=True)
                    # Use fallback with full filing context for meaningful partial results
                    run.summary_payload = generate_xbrl_summary(**fallback_kwargs)
                    provider_fallback = True
                    # Break loop manually since task is cancelled/ignored
                    break

                heartbeat_message = SUMMARIZE_MESSAGES[summarize_heartbeat_index % len(SUMMARIZE_MESSAGES)]
                elapsed_secs = int(time.time() - run.pipeline_started_at)
                # Estimate progress during summarization: start at 50%, increase by 2% per heartbeat, cap at 90%
                current_percent = min(50 + (summarize_heartbeat_index * 2), 90)
                # A5: if progressive previews have arrived, emit the latest full render (coalesced) as a
                # 'preview' event — real content the client can reveal early — instead of a generic
                # heartbeat. Falls through to the heartbeat when no preview is pending (or feature off).
                latest_preview = None
                if preview_queue is not None:
                    while not preview_queue.empty():
                        latest_preview = preview_queue.get_nowait()
                if latest_preview:
                    yield {'type': 'preview', 'stage': 'summarizing', 'markdown': latest_preview, 'heartbeat_count': summarize_heartbeat_index, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
                else:
                    yield {'type': 'progress', 'stage': 'summarizing', 'message': heartbeat_message, 'heartbeat_count': summarize_heartbeat_index, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
                summarize_heartbeat_index += 1

            if not run.summary_payload:
                try:
                    run.summary_payload = await run.summary_task
                except TimeoutError:
                    # The service now owns the exact AI deadline, independent of heartbeat timing.
                    run.summary_payload = generate_xbrl_summary(**fallback_kwargs)
                    provider_fallback = True
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    # Looked like we already handled fallback, but ensure payload is set
                    if not run.summary_payload:
                        run.summary_payload = generate_xbrl_summary(**fallback_kwargs)
                        provider_fallback = True
            run.mark_stage("generate_summary")

            run.summary_status = run.summary_payload.get("status", "complete")
            if run.provider_started.is_set() or (run.summary_status != "error" and not provider_fallback):
                # The signal may have fired just before the task finished; a result without the
                # signal (a stand-in service) still ran a provider, so it is counted on completion.
                # A timeout fallback without the signal ran no provider at all (the deadline passed
                # during local parsing or admission), so it is served uncounted.
                await run.charge_lease()
            if run.summary_status == "error":
                error_message = run.summary_payload.get("message", "Error generating summary")
                await run.refund_charge("provider returned an error payload")
                # Persist the error state so the /progress endpoint reports a retryable error
                # immediately, instead of leaving "summarizing" to age out via the stale check.
                try:
                    await run.run_sync_db(run.record_progress_sync, filing_id, "error", error=error_message[:200])
                except Exception as db_err:
                    logger.error(f"[stream:{filing_id}] Failed to record AI error progress: {db_err}", exc_info=True)
                yield {'type': 'error', 'message': error_message}
                return

            # --- finalize.finalize (inline until its extraction commit) ---
            filing_id, user_id, force_regenerate = run.filing_id, run.user_id, run.force_regenerate

            # The application-prepared degraded source is private and will be popped by the shared
            # finalizer. Retain it separately so the cache owner can preserve the same decoded-text
            # view for later API/export projection when no critical excerpt exists.
            risk_source_for_cache = run.summary_payload.get("_risk_source_grounding")
            markdown, raw_summary, sections_info, normalized_financial_section = (
                _finalize_summary_projection(
                    run.summary_payload,
                    run.xbrl_metrics,
                    run.summary_status,
                    source_text=run.excerpt or run.filing_text,
                    filing_document_url=run.filing_document_url,
                )
            )

            section_coverage = (
                raw_summary.get("section_coverage")
                if isinstance(raw_summary, dict)
                else None
            )
            if section_coverage:
                await run.run_sync_db(
                    run.record_progress_sync,
                    filing_id,
                    "summarizing",
                    section_coverage=section_coverage,
                )

            risk_section = sections_info.get("risks") or []
            # Legacy compat columns on the Summary row (management_discussion / key_changes) still get
            # the v2-mapped prose (earnings_quality / forward_signals, re-pointed in summarize_filing).
            management_section = run.summary_payload.get("management_discussion")
            guidance_section = run.summary_payload.get("key_changes")

            # The legacy MD&A/guidance wrapper injection is retired under v2: the v2 taxonomy already
            # carries earnings_quality + forward_signals, and the web reads the render_sections output
            # (rendered_sections), not these keys. Injecting management_discussion_insights /
            # guidance_outlook here would only decorate every v2 row with phantom v1 nodes.

            # S4: deterministic quality verdict (always attached as metadata for the UI badge).
            # sic feeds the bank-aware revenue-grounding rule (P0-2) as the flag-independent
            # FI signal alongside component presence.
            # ``excerpt or filing_text``: when excerpt extraction failed (cache miss + section-parse
            # timeout), ``summarize_filing`` still generated from ``filing_text``'s parsed sample — so the
            # gate must ground against the same text, else every filing-copied figure false-flags on
            # exactly the degraded population. The two are complementary (filing_text is emptied only when
            # the excerpt is in use), and ``untraceable_figures`` returns [] if BOTH are empty.
            quality = assess_quality(
                run.summary_payload, run.xbrl_metrics, sic=run.company_sic, excerpt=run.excerpt or "",
                trace_excerpt=run.excerpt or run.filing_text
            )
            raw_summary["quality"] = quality
            untraceable = quality.get("figures_untraceable") or []
            if untraceable:
                # T3.2 advisory-phase measurement channel. The gate ships flag-off, so untraceable dollar
                # figures do NOT tier the summary "partial" — this greppable counter (count first, for a
                # log-based metric threshold) is the only push signal for the flag-flip decision and,
                # post-T5, the regression alarm for derived-aggregate reintroduction.
                logger.info(
                    "figure_trace_untraceable count=%d flag=%s filing_id=%s sic=%s figures=%s",
                    len(untraceable),
                    settings.AI_FIGURE_TRACE_GATE,
                    filing_id,
                    run.company_sic or "",
                    "|".join(untraceable),
                )
            if quality.get("tier") == "partial":
                # P0-2 detection: greppable counter of partial verdicts by reason + SIC. A
                # bank-heavy spike after any prompt change is the recurrence signal for the
                # bank-blind-grounding incident class.
                logger.info(
                    "summary_quality_partial filing_id=%s cik=%s sic=%s reasons=%s",
                    filing_id,
                    run.company_cik,
                    run.company_sic or "",
                    "|".join(quality.get("reasons") or []),
                )
            if quality.get("machine_sections_only"):
                # T5.3 detection (#621 staff review): full-tier verdict where machine-authored
                # XBRL sections alone crossed the 4/9 bar — zero model-authored sections covered.
                # A spike after a prompt/model change means generation collapse is being masked
                # by deterministic content (and, under AI_QUALITY_GATE, still charged); the
                # verdict is honest, but the class is watched, not assumed.
                logger.info(
                    "summary_quality_full_machine_only filing_id=%s cik=%s sic=%s covered=%s/%s",
                    filing_id,
                    run.company_cik,
                    run.company_sic or "",
                    quality.get("covered_count"),
                    quality.get("total_count"),
                )
            attribution_audit = (raw_summary or {}).get("attribution_audit") or {}
            if attribution_audit.get("unverified"):
                # #805 path step 4 measurement channel (count-first): causal clauses the filing does
                # not state, emitted flag on OR off; dropped counts only when the gate is armed.
                verification = attribution_audit.get("verification") or {}
                logger.info(
                    "attribution_unverified count=%d checked=%d dropped=%d decider=%s decided=%d "
                    "verify_error=%s flag=%s filing_id=%s sic=%s slots=%s",
                    len(attribution_audit["unverified"]),
                    attribution_audit.get("checked", 0),
                    len(attribution_audit.get("dropped") or []),
                    attribution_audit.get("decider", "none"),
                    verification.get("decided", 0),
                    verification.get("error") or "",
                    settings.AI_ATTRIBUTION_GATE,
                    filing_id,
                    run.company_sic or "",
                    "|".join(str(u.get("slot") or "?") for u in attribution_audit["unverified"]),
                )
            unit_audit = (raw_summary or {}).get("table_cell_unit_audit") or {}
            if unit_audit.get("restored_count") or unit_audit.get("unresolved_count"):
                # Declared table-cell scale owner (source_units) measurement channel, count-first:
                # bare model dollar figures whose declared scale was restored, and those left
                # untouched with the abstention reason. Totals are exact even when the audit's
                # detail lists are capped. Unresolved figures stay visible as written.
                logger.info(
                    "table_cell_units restored=%d unresolved=%d filing_id=%s sic=%s reasons=%s",
                    int(unit_audit.get("restored_count") or 0),
                    int(unit_audit.get("unresolved_count") or 0),
                    filing_id,
                    run.company_sic or "",
                    "|".join(sorted({str(u.get("reason") or "?") for u in unit_audit.get("unresolved") or []})),
                )
            quote_audit = (raw_summary or {}).get("forward_quote_audit") or {}
            if quote_audit.get("unverified"):
                # T5.4 measurement channel (count-first, the figure-trace convention): §5 quotes
                # that failed the verbatim check, emitted flag on OR off. near_miss (rapidfuzz
                # ≥92 on normalized text) = lightly-paraphrased population → prompt tuning;
                # the remainder = fabrication-class → the arming signal for the drop gate.
                unverified = quote_audit["unverified"]
                logger.info(
                    "forward_quote_unverified count=%d near_miss=%d dropped=%d flag=%s "
                    "filing_id=%s sic=%s speakers=%s",
                    len(unverified),
                    quote_audit.get("near_miss", 0),
                    len(quote_audit.get("dropped") or []),
                    settings.AI_FORWARD_QUOTE_GATE,
                    filing_id,
                    run.company_sic or "",
                    "|".join(str(u.get("speaker") or "?") for u in unverified),
                )
            snap_audit = (raw_summary or {}).get("evidence_snap_audit") or {}
            if snap_audit.get("checked"):
                # Evidence auto-snap measurement channel (post-#631, count-first convention):
                # exact = verified as emitted; would_snap = a confident counterpart exists but
                # the flag is unarmed (the entries carry original + candidate — THE arming
                # forensics); snapped = armed repairs (become read-time Verified badges); left =
                # no confident counterpart, text kept (read-time enrichment suppresses it).
                logger.info(
                    "evidence_snap checked=%d exact=%d would_snap=%d snapped=%d left=%d "
                    "flag=%s filing_id=%s",
                    snap_audit.get("checked", 0),
                    snap_audit.get("exact", 0),
                    len(snap_audit.get("would_snap") or []),
                    len(snap_audit.get("snapped") or []),
                    len(snap_audit.get("left") or []),
                    settings.AI_EVIDENCE_SNAP,
                    filing_id,
                )

            # S4 quality gate: the summary is ALWAYS persisted, so the streamed result doesn't
            # vanish when the client refetches and isn't regenerated from scratch on revisit. When
            # a result is assessed "partial", the user is not charged for it (they weren't served a
            # full result): the unit counted at provider start is refunded, and a caller without a
            # lease skips the completion-time count. The UI surfaces it honestly via the quality
            # badge + one-click Regenerate.
            count_usage = not (settings.AI_QUALITY_GATE and quality["tier"] == "partial")
            if not count_usage:
                logger.info(
                    f"[stream:{filing_id}] Quality gate: tier=partial, not charging usage "
                    f"(reasons: {quality['reasons']})"
                )
                await run.refund_charge("partial verdict")

            # DB OP: Persist summary
            def save_summary_sync():
                with database.SessionLocal() as session:
                    filing_for_cache = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()

                    if force_regenerate:
                        # Admin refresh-stale: UPDATE the existing row IN PLACE (preserve summaries.id so
                        # the saved_summaries FK/bookmark survives and UNIQUE(filing_id) holds) instead of
                        # delete+insert, guarded by a keep-better gate.
                        existing = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                        if existing is not None:
                            stored_tier = ((existing.raw_summary or {}).get("quality") or {}).get("tier")
                            new_tier = (quality or {}).get("tier")
                            if quality_tier_rank(new_tier) < quality_tier_rank(stored_tier):
                                # Never let a refresh downgrade a stored higher tier (a 75s AI-timeout
                                # XBRL fallback comes back "partial"; keep the stored "full").
                                logger.info(
                                    "[stream:%s] refresh keep-better: keeping stored tier=%s over new tier=%s",
                                    filing_id, stored_tier, new_tier,
                                )
                                return existing.id
                            existing.business_overview = markdown
                            existing.financial_highlights = normalized_financial_section
                            existing.risk_factors = risk_section
                            existing.management_discussion = management_section
                            existing.key_changes = guidance_section
                            # Reassign a NEW dict so SQLAlchemy marks the JSON column dirty and emits UPDATE.
                            existing.raw_summary = raw_summary
                            existing.schema_version = SUMMARY_SCHEMA_VERSION
                            existing.prompt_version = SUMMARY_PROMPT_VERSION
                            if filing_for_cache:
                                upsert_content_cache(
                                    session, filing_id, filing_for_cache.content_cache,
                                    excerpt=run.excerpt, sections_payload=sections_info,
                                    risk_source_text=(
                                        risk_source_for_cache
                                        if isinstance(risk_source_for_cache, str)
                                        else None
                                    ),
                                    replace_risk_source=True,
                                )
                            session.commit()
                            return existing.id
                        # force on a filing with no stored summary yet: fall through to a normal INSERT.

                    summary = Summary(
                        filing_id=filing_id,
                        business_overview=markdown,
                        financial_highlights=normalized_financial_section,
                        risk_factors=risk_section,
                        management_discussion=management_section,
                        key_changes=guidance_section,
                        raw_summary=raw_summary,
                        schema_version=SUMMARY_SCHEMA_VERSION,
                        prompt_version=SUMMARY_PROMPT_VERSION,
                    )
                    session.add(summary)

                    if filing_for_cache:
                        upsert_content_cache(
                            session,
                            filing_id,
                            filing_for_cache.content_cache,
                            excerpt=run.excerpt,
                            sections_payload=sections_info,
                            risk_source_text=(
                                risk_source_for_cache
                                if (
                                    isinstance(risk_source_for_cache, str)
                                    and (force_regenerate or not run.excerpt)
                                )
                                else None
                            ),
                            replace_risk_source=force_regenerate,
                        )

                    try:
                        session.commit()
                        return summary.id
                    except IntegrityError:
                        # A concurrent writer (cron / another instance) persisted this filing's summary
                        # first — filing_id is UNIQUE. Serve the winner's row instead of erroring the
                        # user's stream (S1 decision #3).
                        session.rollback()
                        existing = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                        if existing is None:
                            raise
                        return existing.id

            saved_summary_id = await run.run_sync_db(save_summary_sync)

            run.mark_stage("persist_summary")

            if run.charged_month is not None:
                # The unit counted at provider start is settled by the persisted summary: no later
                # failure refunds it.
                run.charged_month = None
                run.charge_future = None  # nothing left to settle: the unit is owed
            elif user_id and count_usage and run.usage_reservation_token is None:
                # No lease was held (background drain, uncapped Pro): the historical
                # completion-time count, full results only. A lease still held here was left
                # uncharged on purpose (an unsignalled timeout fallback); `release` releases it.
                def track_usage_sync():
                    with database.SessionLocal() as session:
                        user = session.query(User).filter(User.id == user_id).first()
                        if user:
                            increment_user_usage(user.id, get_current_month(), session)

                await run.run_sync_db(track_usage_sync)
                run.mark_stage("usage_tracking")

            # DB OP: Record complete
            await run.run_sync_db(run.record_progress_sync, filing_id, "completed")

            run.summary_status = run.summary_payload.get("status", "complete")
            summary_message = run.summary_payload.get("message")

            # A persisted result with status "error" means only fallback content was
            # produced — count it as a failure in the funnel, not a success.
            run.emit_funnel(
                run.telemetry_distinct_id,
                EVENT_GENERATION_SUCCEEDED if run.summary_status != "error" else EVENT_GENERATION_FAILED,
                duration_ms=run.elapsed_ms(),
                result_type=run.summary_status,
                quality_verdict=quality.get("tier"),
                figures_untraceable_count=len(quality.get("figures_untraceable") or []),
                entry_point=run.telemetry_entry_point,
                **run.telemetry_ctx,
            )

            yield {'type': 'chunk', 'content': markdown}

            if run.summary_status == "partial":
                yield {'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': saved_summary_id}
            elif run.summary_status == "error":
                yield {'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': saved_summary_id}
            else:
                yield {'type': 'complete', 'summary_id': saved_summary_id, 'percent': 100}
    except TimeoutError:
        yield await failure.timed_out(run)
    except Exception as e:
        # CancelledError/GeneratorExit (client disconnect) are BaseExceptions and skip this handler:
        # the unit counted at provider start is refunded only for a failure the client did not cause.
        yield await failure.failed(run, e)
    finally:
        await run.release()

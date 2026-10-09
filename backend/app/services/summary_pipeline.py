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

from sqlalchemy import inspect as sa_inspect

from app import database
from app.config import settings
from app.models import User, Subscription
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
    admission, enrichment, failure, fetch, finalize, generation, generation_run,
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
        generation.generate,
        finalize.finalize,
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
    except TimeoutError:
        yield await failure.timed_out(run)
    except Exception as e:
        # CancelledError/GeneratorExit (client disconnect) are BaseExceptions and skip this handler:
        # the unit counted at provider start is refunded only for a failure the client did not cause.
        yield await failure.failed(run, e)
    finally:
        await run.release()

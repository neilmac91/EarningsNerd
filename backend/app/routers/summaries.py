from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from sqlalchemy.orm import Session, joinedload
from typing import Annotated, Optional
from contextlib import aclosing
from collections.abc import AsyncGenerator
from uuid import UUID
import asyncio
import json

import anyio
from pydantic import BaseModel, Field, field_validator
import logging
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from starlette.requests import ClientDisconnect
from starlette.types import Receive, Scope, Send
from app.services.posthog_client import capture_copilot_inference

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import (
    Filing,
    Summary,
    User,
    SummaryGenerationProgress,
)
from app.routers.auth import get_current_user, get_current_user_optional
from app.dependencies import copilot_taste_exhausted_detail, require_copilot_or_taste
from app.services.entitlements import get_entitlements, is_pro_user
from app.services.export_service import export_service
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.subscription_service import (
    LIFETIME_SCOPE,
    check_qa_limit,
    convert_reservation,
    get_current_month,
    increment_user_copilot_free_taste,
    increment_user_qa,
    refund_copilot_free_taste,
    refund_qa_use,
    release_reservation,
    reserve_qa_taste_use,
    reserve_qa_use,
)
from app.services.copilot_service import PROVIDER_STARTED_STAGE, answer_filing_question, snapshot_filing
from app.services.ai.provider_requests import provider_start_signal
from app.services.summary_generation_service import (
    mark_stale_progress_as_error,
    progress_as_dict,
)
from app.services.summary_request_evidence import SummaryRequestEvidence
from app.services.summary_pipeline import (
    stream_filing_summary, to_sse, snapshot_generation_user, load_generation_user,
)
from app.services.provenance_service import enrich_summary_provenance, source_safe_business_overview
from app.services.change_report_service import build_change_report

router = APIRouter()
logger = logging.getLogger(__name__)
# Both burst limiters are keyed on the account alone (``include_client_ip=False``): keying on
# (IP, user) would let one account presenting several client IPs multiply its allowance.
SUMMARY_LIMITER = RateLimiter(limit=5, window_seconds=60)
# Copilot Q&A is cheaper per call than a summary but still hits the model — allow a higher
# burst than summaries while still throttling abuse (per user, sliding window).
ASK_LIMITER = RateLimiter(limit=10, window_seconds=60)


class SummaryStreamResponse(StreamingResponse):
    """Close the owned iterator even when disconnect occurs during ASGI send."""

    def __init__(self, content: AsyncGenerator[str, None], evidence: SummaryRequestEvidence) -> None:
        self.evidence = evidence
        self.owned_stream = evidence.wrap_stream(content)
        super().__init__(
            self.owned_stream, media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except (asyncio.CancelledError, ClientDisconnect, OSError):
            self.evidence.finish("cancelled")
            raise
        except Exception:
            self.evidence.finish("error")
            raise
        finally:
            # Starlette can return on disconnect while our iterator is suspended at yield,
            # or fail response.start before ever entering it. Closing an unstarted generator
            # does not run its finally, so the response also owns unfinished observations.
            with anyio.CancelScope(shield=True):
                try:
                    await self.owned_stream.aclose()
                finally:
                    self.evidence.finish("cancelled")


class AskRequest(BaseModel):
    """Body for the "Ask this Filing" Copilot endpoint."""
    question: str = Field(..., min_length=1, max_length=2000)
    history: Optional[list[dict]] = None

    @field_validator("history")
    @classmethod
    def _bound_history(cls, v: Optional[list[dict]]) -> Optional[list[dict]]:
        """Cap history size so a malicious client can't stuff the prompt.

        ``question`` is already length-bounded, but ``history`` is free-form: without this a single
        multi-MB turn (or a huge array) would be accepted and fed toward the model context. We keep
        only the most recent ``COPILOT_HISTORY_MAX_ITEMS`` turns and truncate each turn's ``content``
        to ``COPILOT_HISTORY_ITEM_CHAR_CAP`` chars. (The generator also re-truncates as defense in
        depth; see ``copilot_service._build_messages``.)
        """
        if not v:
            return v
        cap = settings.COPILOT_HISTORY_ITEM_CHAR_CAP
        trimmed = v[-settings.COPILOT_HISTORY_MAX_ITEMS:]
        out: list[dict] = []
        for turn in trimmed:
            if isinstance(turn, dict):
                content = turn.get("content")
                if isinstance(content, str) and len(content) > cap:
                    turn = {**turn, "content": content[:cap]}
            out.append(turn)
        return out

class SummaryResponse(BaseModel):
    id: int
    filing_id: int
    business_overview: Optional[str]
    financial_highlights: Optional[dict]
    risk_factors: Optional[list]
    management_discussion: Optional[str]
    key_changes: Optional[str]
    raw_summary: Optional[dict]
    # The structured Section/Block projection the web renders (T2.3). Same model feeds PDF/CSV.
    rendered_sections: Optional[list] = None
    # Version stamps: NULL on legacy/pre-stamp rows (treated as stale by the refresh path).
    schema_version: Optional[int] = None
    prompt_version: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/filing/{filing_id}/progress")
async def get_summary_progress(
    filing_id: int,
    db: Session = Depends(get_db)
):
    """Get progress status for summary generation"""
    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        # Summary exists, return completed status
        return {
            "stage": "completed",
            "elapsedSeconds": 0
        }

    progress = (
        db.query(SummaryGenerationProgress)
        .filter(SummaryGenerationProgress.filing_id == filing_id)
        .first()
    )
    if progress:
        # Surface orphaned/stalled generations as a retryable error instead of an
        # eternal "generating" state if the background task died without finishing.
        if mark_stale_progress_as_error(progress):
            db.commit()
        return progress_as_dict(progress)

    return {"stage": "pending", "elapsedSeconds": 0}

@router.post("/filing/{filing_id}/generate-stream")
async def generate_summary_stream(
    filing_id: int,
    request: Request,
    force: bool = False,
    entry_point: Optional[str] = None,
    ph_id: Optional[str] = None,
    analytics_consent: bool = False,
    logical_request_id: Optional[UUID] = None,
    client_attempt: Annotated[Optional[int], Query(ge=1, le=2)] = None,
    transport_attempt: Annotated[Optional[int], Query(ge=1, le=2)] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response (account required).

    Anonymous callers get 401 here at the router boundary; the free-tier monthly
    quota is then enforced inside the pipeline (``check_usage_limit``). Cached
    summaries stay publicly readable via ``GET /filing/{id}`` — only fresh
    generation requires an account.

    Args:
        force: If True, delete existing summary and regenerate from scratch.
               Use this for "Regenerate Analysis" functionality.
        entry_point: Where the visitor entered the funnel (forwarded by the
                     frontend for activation analytics, e.g. "homepage").
        ph_id: Legacy client hint, accepted for compatibility but never used as account identity.
        analytics_consent: Explicit client declaration; absent/false suppresses request/funnel events.
        logical_request_id: Client action label shared across automatic retries.
        client_attempt: Client outer attempt (untrusted correlation hint).
        transport_attempt: Handshake attempt, including an auth-refresh replay (untrusted).
    """
    evidence = SummaryRequestEvidence(
        consent=analytics_consent, account_id=current_user.id, filing_id=filing_id,
        logical_request_id=logical_request_id, client_attempt=client_attempt,
        transport_attempt=transport_attempt, entry_point=entry_point,
    )
    evidence.start()
    try:
        client_host = request.client.host if request.client else "unknown"
        logger.info(f"[stream:{filing_id}] Incoming stream request from {current_user.id} (IP: {client_host}, force={force})")

        enforce_rate_limit(
            request,
            SUMMARY_LIMITER,
            f"summary:{current_user.id}",
            error_detail="Too many summary requests. Please try again shortly.",
            include_client_ip=False,
        )

        # Eagerly load content_cache and company relationship to avoid detached session issues
        filing = db.query(Filing).options(
            joinedload(Filing.content_cache),
            joinedload(Filing.company)
        ).filter(Filing.id == filing_id).first()

        if not filing:
            raise HTTPException(status_code=404, detail="Filing not found")

        # Check if summary already exists
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        if summary:
            if force:
                # Force regeneration triggers a fresh, paid LLM run, so it's Pro-only (Free 403; anyone
                # unauthenticated already got 401 at the endpoint) — otherwise it's a denial-of-wallet /
                # "wipe a popular filing for everyone" vector. Resolved via the entitlements SSoT (not
                # the is_pro mirror) so a lagging mirror can't wrongly grant/deny it. NB this gate sits
                # inside `if summary`: when no summary exists yet, force is a harmless no-op, so a
                # failed-generation retry stays open to Free users.
                if not is_pro_user(current_user):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Regenerating an analysis is a Pro feature.",
                    )
                # Regenerate IN PLACE (force_regenerate below): the pipeline's save step UPDATEs the
                # existing summary row rather than delete+insert, so the summaries.id — and any
                # saved_summaries bookmark FK'd to it — survives (T1.4). Deleting the row here would
                # both destroy the bookmark and raise an FK violation on any bookmarked summary in
                # Postgres. Keep-better applies: a fresh run that comes back below the stored tier keeps
                # the stored summary. We still clear XBRL + progress so regeneration re-fetches fresh data.
                logger.info(f"[stream:{filing_id}] Force regeneration requested - refreshing in place")

                if filing.xbrl_data is not None:
                    filing.xbrl_data = None
                    logger.info(f"[stream:{filing_id}] Cleared XBRL data for regeneration")

                # Clear progress record
                progress = db.query(SummaryGenerationProgress).filter(
                    SummaryGenerationProgress.filing_id == filing_id
                ).first()
                if progress:
                    db.delete(progress)

                db.commit()
            else:
                # Capture the response before closing the dependency's read transaction.
                payload = {
                    'type': 'complete',
                    'summary': source_safe_business_overview(summary, filing),
                    'summary_id': summary.id,
                }
                db.close()

                evidence.delivery_path = "router_cache"

                async def existing_summary():
                    evidence.observe_terminal(payload)
                    yield f"data: {json.dumps(payload)}\n\n"
                return SummaryStreamResponse(existing_summary(), evidence)

        user_id = current_user.id
        logger.info(f"[stream:{filing_id}] Starting summary stream for user {user_id}")

        # Only the authenticated account owns server event identity. Client ph_id is not authority.
        telemetry_distinct_id = str(current_user.id)
        telemetry_entry_point = (entry_point or "")[:64] or None
        telemetry_ctx = {
            "filing_id": filing_id,
            "filing_type": filing.filing_type,
            "ticker": filing.company.ticker if filing.company else None,
            "user_type": "authenticated",
            "forced": force,
            "account_id_at_event": str(current_user.id),
            "identity_evidence": "server_authenticated",
            "analytics_consent_at_event": True,
            "request_id": evidence.properties["request_id"],
        }

        # Copy loaded identity inputs without lazy SQL, then release the request connection.
        # Resolve missing subscription inputs in a separate worker-owned transaction; neither
        # the request session nor any ORM object crosses into that worker or the stream.
        generation_user = snapshot_generation_user(current_user, user_id)
        db.close()
        generation_user = await run_in_threadpool(load_generation_user, generation_user)

        async def event_stream():
            evidence.delivery_path = "pipeline"
            async with aclosing(stream_filing_summary(
                filing_id=filing_id,
                current_user=generation_user,
                user_id=user_id,
                telemetry_distinct_id=telemetry_distinct_id,
                telemetry_entry_point=telemetry_entry_point,
                telemetry_ctx=telemetry_ctx,
                emit_funnel_telemetry=analytics_consent,
                force_regenerate=force,
                request_evidence=evidence,
            )) as events:
                async for event in events:
                    evidence.observe_terminal(event)
                    yield to_sse(event)

        return SummaryStreamResponse(event_stream(), evidence)
    except HTTPException as exc:
        evidence.reason = f"http_{exc.status_code}"
        evidence.finish("rejected")
        raise
    except asyncio.CancelledError:
        evidence.finish("cancelled")
        raise
    except Exception:
        evidence.reason = "route_error"
        evidence.finish("error")
        raise


def _meter_qa_best_effort(user_id: int, is_free_taste: bool = False, token: Optional[str] = None) -> Optional[str]:
    """Meter one Copilot question in a fresh DB session (best-effort) as its provider stream starts.

    Free users (``is_free_taste``) decrement their lifetime free-taste allowance; Pro users
    increment the monthly fair-use ``qa_count``. The admission lease (``token``) is converted in
    the same commit, so a unit is never both held and counted. Called from inside the SSE
    generator, which runs after the request's DB session may already be gone (see
    ``snapshot_filing``), so it opens its own short-lived session. A metering failure must never
    break the answer stream, so errors are swallowed (and logged). Returns the scope the unit was
    counted in (the admitted month, or ``LIFETIME_SCOPE`` for free taste) so a provider-side
    failure can refund it, or ``None`` when nothing was counted (the caller releases the lease).
    """
    db = SessionLocal()
    try:
        if is_free_taste:
            convert_reservation(token, db)  # lifetime scope: the returned scope is not a month
            increment_user_copilot_free_taste(user_id, db)
            return LIFETIME_SCOPE
        month = convert_reservation(token, db) or get_current_month()
        increment_user_qa(user_id, month, db)
        return month
    except Exception:  # noqa: BLE001 — metering must not break the answer stream
        logger.warning("Failed to meter Copilot QA for user %s", user_id, exc_info=True)
        return None
    finally:
        db.close()


def _refund_qa_best_effort(user_id: int, is_free_taste: bool, scope: str) -> None:
    """Give back the unit ``_meter_qa_best_effort`` counted in ``scope`` (fresh session; best-effort).
    Only for a provider-side failure after the stream started — never for a client disconnect."""
    db = SessionLocal()
    try:
        if is_free_taste:
            refund_copilot_free_taste(user_id, db)
        else:
            refund_qa_use(user_id, scope, db)
    except Exception:  # noqa: BLE001 — never mask the stream outcome
        logger.warning("Could not refund a Copilot unit for user %s", user_id, exc_info=True)
    finally:
        db.close()


def _release_reservation_best_effort(token: Optional[str]) -> None:
    """Give an admission lease back (fresh session; the lease expires on its own if this fails)."""
    if not token:
        return
    db = SessionLocal()
    try:
        release_reservation(token, db)
    except Exception:  # noqa: BLE001 — never mask the stream outcome
        logger.warning("Could not release a Copilot admission reservation", exc_info=True)
    finally:
        db.close()


def _emit_copilot_cost_best_effort(
    user_id: int, filing_id: int, ticker, event: dict, is_free_taste: bool = False
) -> None:
    """Emit a Copilot answer's token usage + estimated inference cost to PostHog (roadmap 2.1).

    Keyed on ``str(user_id)`` — the same id the frontend identifies on — so it joins the person's
    journey without a separate alias. Use the wrapper's recorded call-cost total; unknown totals
    stay unknown. An absent accounting payload is a no-op and telemetry failures are swallowed.
    """
    try:
        usage = event.get("usage") or {}
        if not usage:
            return
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        cache_hit_tokens = usage.get("cache_hit_tokens")
        cache_miss_tokens = usage.get("cache_miss_tokens")
        capture_copilot_inference(
            distinct_id=str(user_id),
            model=usage.get("model"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens"),
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cost_usd=usage.get("estimated_cost_usd"),
            filing_id=filing_id,
            ticker=ticker,
            kind=event.get("kind"),
            grounded=event.get("grounded"),
            is_free_taste=is_free_taste,
            misplaced_fact_markers=event.get("misplaced_fact_markers"),
            figure_count=event.get("figure_count"),
            uncited_figures=event.get("uncited_figures"),
        )
    except Exception:  # noqa: BLE001 — telemetry must not break the answer stream
        logger.warning("Failed to emit Copilot cost telemetry for user %s", user_id, exc_info=True)


@router.post("/filing/{filing_id}/ask-stream")
async def ask_filing_stream(
    filing_id: int,
    body: AskRequest,
    request: Request,
    current_user: User = Depends(require_copilot_or_taste),
    db: Session = Depends(get_db),
):
    """Grounded single-filing Q&A with a streaming (SSE) response.

    Open to Pro (full "copilot" entitlement) and to Free users within their lifetime free-taste
    allowance (roadmap 2.2); the dependency 403s a Free user once the taste is spent. The model
    answers using only this filing's cached content; the server verifies each cited excerpt against
    the filing text (reusing the Trace-to-Source provenance helpers) before publishing a completed
    answer with source-match labels and ``#:~:text=`` deep links. Known failed referenced evidence
    yields an error without draft prose. Excluded from the timeout middleware by the ``*stream*``
    name rule. Metering: Pro counts against the monthly fair-use cap; Free decrements the lifetime
    free-taste counter — both when the provider stream starts, refunded on a provider-side failure
    and never on a client disconnect (see ``event_stream``).
    """
    enforce_rate_limit(
        request,
        ASK_LIMITER,
        f"ask:{current_user.id}",
        error_detail="Too many questions. Please try again shortly.",
        include_client_ip=False,
    )

    filing = db.query(Filing).options(
        joinedload(Filing.content_cache),
        joinedload(Filing.company),
    ).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Snapshot the filing into detached plain objects up front. The SSE generator below runs after
    # this request's session may be gone, so it must never touch the ORM (mirrors
    # generate_summary_stream's eager value capture). Done before the admission below commits,
    # so nothing is re-selected from expired instances while a lease is already held.
    filing_ctx = snapshot_filing(filing)
    user_id = current_user.id

    # Free users reach here on their lifetime free-taste allowance (gated upstream by
    # require_copilot_or_taste); they meter the lifetime counter, not the monthly cap. The monthly
    # fair-use cap is a Pro-only protection against runaway volume.
    is_free_taste = not get_entitlements(current_user).copilot
    if is_free_taste:
        # The gate above is a plain read; concurrent questions could all pass it. The serialized
        # admission holds one unit of the LIFETIME allowance under a lease until the answer
        # completes (converted) or fails (released).
        admitted, _used, allowance, token = reserve_qa_taste_use(current_user, db)
        if not admitted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=copilot_taste_exhausted_detail(allowance))
    else:
        allowed, count, cap = check_qa_limit(current_user, db)
        if allowed:
            allowed, count, cap, token = reserve_qa_use(current_user, db)  # serialized decision
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've reached this month's fair-use limit of {cap} Copilot questions. "
                    "It resets at the start of next month."
                ),
            )
    held = {"token": token}  # the admission lease, until converted by metering or released

    async def event_stream():
        # Metering point: the unit is counted when the provider request is ISSUED. The request
        # dispatcher fires the provider-start signal immediately before the first provider call,
        # and that signal starts the metering write right here, in this task, before the prose
        # holdback or a tool round can delay the first chunk. The ``progress`` event with stage
        # ``PROVIDER_STARTED_STAGE`` (or a terminal event) starts it too, for a stand-in service
        # that never signals. Neither the ``reading`` progress that precedes the model call nor
        # completion meters. The provider bill accrues from the request, so a client disconnect
        # after that point keeps the unit (the cancellation path never refunds; ``finally`` settles
        # the write the signal started); a disconnect or failure before it leaves the lease held,
        # and ``finally`` releases it. A provider-side failure after the start (an ``error`` event,
        # or the generator raising) refunds it: the client cannot induce either, and no answer prose
        # was delivered.
        charge: dict[str, Optional[asyncio.Future]] = {"future": None}  # the in-flight metering write
        metered = False  # the metering write's outcome has been adopted (once)
        charged: Optional[str] = None  # scope the unit was counted in, until settled by `complete` or refunded

        def begin_charge() -> None:
            """Start the metering write (at most once). Offloaded to a worker thread (fresh
            SessionLocal) so it never blocks the event loop mid-stream; it cannot be cancelled, so
            it is kept as a future that ``settle_charge`` adopts whatever happens to this task."""
            if charge["future"] is None and held["token"] is not None:
                charge["future"] = asyncio.ensure_future(
                    run_in_threadpool(_meter_qa_best_effort, user_id, is_free_taste, held["token"])
                )

        async def settle_charge(*, in_finally: bool) -> None:
            """Adopt what the metering write committed: the scope it counted in (the lease is then
            converted) or None (a metering failure leaves the lease held for release)."""
            nonlocal metered, charged
            future = charge["future"]
            if future is None or metered:
                return
            if in_finally:
                if not future.done():
                    await asyncio.wait({future})
            else:
                await asyncio.shield(future)  # a cancellation here abandons the await, not the write
            if future.cancelled() or future.exception() is not None:
                return
            metered = True
            charged = future.result()
            if charged is not None:
                held["token"] = None

        try:
            with provider_start_signal(begin_charge):  # armed in this task: the service runs here
                async for event in answer_filing_question(
                    filing=filing_ctx,
                    question=body.question,
                    history=body.history,
                ):
                    kind = event.get("type")
                    provider_started = (
                        (kind == "progress" and event.get("stage") == PROVIDER_STARTED_STAGE)
                        or kind in ("complete", "not_disclosed")
                    )
                    if not metered and (provider_started or charge["future"] is not None):
                        begin_charge()
                        await settle_charge(in_finally=False)
                    if kind == "complete":
                        charged = None  # settled: the answer was served
                        # Per-answer inference-cost telemetry (roadmap 2.1) — token usage rides the
                        # complete event; cost is estimated here. Non-blocking + best-effort.
                        _emit_copilot_cost_best_effort(
                            user_id,
                            filing_id,
                            getattr(getattr(filing_ctx, "company", None), "ticker", None),
                            event,
                            is_free_taste,
                        )
                    elif kind == "error" and charged is not None:
                        await run_in_threadpool(_refund_qa_best_effort, user_id, is_free_taste, charged)
                        charged = None
                    yield to_sse(event)
        except Exception:
            # An escaping ordinary failure may precede the first post-signal event. Adopt the
            # pending charge before refunding it; cancellation must not interrupt that settlement.
            # CancelledError is a BaseException and skips this handler: disconnects stay charged.
            with anyio.CancelScope(shield=True):
                await settle_charge(in_finally=True)
                if charged is not None:
                    await run_in_threadpool(_refund_qa_best_effort, user_id, is_free_taste, charged)
                    charged = None
            raise
        finally:
            # On a client disconnect Starlette cancels this task (ASGI < 2.4, which uvicorn speaks),
            # so everything here runs shielded. First adopt a metering write the signal started
            # that the loop never reached (the request was issued: the unit is owed, no lease is
            # left to release). A lease still held after that was never converted (error before the
            # provider started, metering failure, disconnect before the request): give the unit back
            # now rather than after the lease TTL.
            with anyio.CancelScope(shield=True):
                await settle_charge(in_finally=True)
                if held["token"] is not None:
                    await run_in_threadpool(_release_reservation_best_effort, held["token"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for Cloud Run/nginx
        }
    )

@router.get("/filing/{filing_id}", response_model=SummaryResponse)
async def get_summary(filing_id: int, db: Session = Depends(get_db)):
    """Get summary for a filing.

    Risk factors are enriched with Trace-to-Source provenance (a deep link to the original SEC
    filing plus an honest verified/cited label) at serialization time, so every existing summary
    gains provenance without a migration or regeneration.
    """
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()

    if not summary:
        # Return empty summary instead of 404 to allow frontend to trigger generation
        return {
            "id": 0,
            "filing_id": filing_id,
            "business_overview": None,
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "raw_summary": None
        }

    # Load the filing (with its cached content) to verify excerpts and build EDGAR deep links.
    filing = (
        db.query(Filing)
        .options(joinedload(Filing.content_cache))
        .filter(Filing.id == filing_id)
        .first()
    )

    # SEC-verified XBRL values, used to mark financial metrics as "verified". Best-effort: any
    # extraction issue must never break the summary response.
    xbrl_standardized = None
    if filing is not None and getattr(filing, "xbrl_data", None):
        try:
            from app.services.edgar.compat import xbrl_service
            xbrl_standardized = xbrl_service.extract_standardized_metrics(filing.xbrl_data)
        except Exception:
            logger.warning(
                f"[summary:{filing_id}] XBRL standardization for provenance failed; continuing",
                exc_info=True,
            )

    return enrich_summary_provenance(summary, filing, xbrl_standardized)

@router.get("/filing/{filing_id}/what-changed")
async def get_what_changed(filing_id: int, db: Session = Depends(get_db)):
    """Deterministic period-over-period change report for a filing vs its prior same-form filing.

    Reports financial-metric deltas, new/resolved risk factors, and management's key-changes
    narrative. DB-only, no LLM — cheap to serve. Returns ``has_changes: false`` when there's no
    prior filing to compare against.
    """
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return build_change_report(db, filing)


@router.get("/filing/{filing_id}/export/pdf")
async def export_summary_pdf(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary as PDF (Pro feature)"""

    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Gate on the centralised entitlement (Subscription-derived, is_pro mirror as fallback).
    if not get_entitlements(current_user).can_export:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PDF export is a Pro feature. Upgrade to Pro to access this feature."
        )

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    filing = db.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    try:
        pdf_bytes = await export_service.export_pdf(summary, filing)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.pdf"'
            }
        )
    except Exception as e:
        logger.error(f"PDF export failed for filing {filing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate PDF. Please try again later."
        )

@router.get("/filing/{filing_id}/export/csv")
async def export_summary_csv(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary financial metrics as CSV (Pro feature)"""

    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Gate on the centralised entitlement (Subscription-derived, is_pro mirror as fallback).
    if not get_entitlements(current_user).can_export:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSV export is a Pro feature. Upgrade to Pro to access this feature."
        )

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    filing = db.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    try:
        csv_content = export_service.generate_csv(summary, filing)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.csv"'
            }
        )
    except Exception as e:
        logger.error(f"CSV export failed for filing {filing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate CSV. Please try again later."
        )

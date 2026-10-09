"""Shared state and helpers for one ``stream_filing_summary`` run.

The orchestrator in ``app/services/summary_pipeline.py`` creates one ``GenerationRun`` per
generation and hands it to every stage in this package. The dataclass fields are the generator's
former local variables; the methods are its former closures (``run_sync_db``, ``settle_charge``,
``refund_charge``, ``begin_charge``, ``charge_lease`` …) and its ``finally`` block (``release``),
moved verbatim apart from the ``self.`` prefix.

Every collaborator is reached through the pipeline module at call time (``pipeline.<name>``) so the
module-level patch seams the tests rely on keep working; see the package docstring.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

import anyio

from app import database
from app.models import User
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.request_work import RequestWork
    from app.services.summary_pipeline import GenerationUserSnapshot
    from app.services.summary_request_evidence import SummaryRequestEvidence

logger = logging.getLogger(pipeline.__name__)


@dataclass
class GenerationRun:
    """One generation's state, shared by the orchestrator and its stages."""

    # The orchestrator's keyword arguments.
    filing_id: int
    current_user: Optional[User | GenerationUserSnapshot]
    user_id: Optional[int]
    telemetry_distinct_id: str
    telemetry_entry_point: Optional[str]
    telemetry_ctx: dict
    emit_funnel_telemetry: bool = True
    force_regenerate: bool = False
    request_evidence: SummaryRequestEvidence | None = None

    # Timing: ``mark_stage`` closes the current stage and ``release`` logs the breakdown.
    pipeline_started_at: float = field(init=False)
    stage_started_at: float = field(init=False)
    stage_timings: List[tuple[str, float]] = field(init=False, default_factory=list)

    # A3: set when this request becomes the generation leader; released in ``release``.
    inflight_event: Optional[asyncio.Event] = None
    generation_semaphore: Optional[asyncio.Semaphore] = None
    generation_slot_held: bool = False
    usage_reservation_token: Optional[str] = None
    # The month the admission lease was counted in when the provider task started; None once the
    # unit is settled (summary persisted) or refunded, so a refund can happen at most once.
    charged_month: Optional[str] = None
    # The in-flight charge write. The thread-pool write cannot be cancelled: when the pipeline
    # deadline (or a disconnect) cancels the coroutine awaiting it, the worker still finishes and
    # commits, and the assignment after the await never runs. The write is awaited through
    # `asyncio.shield`, so this future still resolves with the committed month, and the refund and
    # release paths settle it before deciding what was actually counted.
    charge_future: Optional[asyncio.Future] = None
    summary_task: Optional[asyncio.Task] = None
    provider_started_waiter: Optional[asyncio.Future] = None
    xbrl_task: Optional[asyncio.Task] = None
    sections_task: Optional[asyncio.Task] = None
    fetch_task: Optional[asyncio.Task] = None
    excerpt_task: Optional[asyncio.Task] = None
    worker_owner: RequestWork = field(init=False)
    # Set by the generation stage at the instant the provider request is issued (see the metering
    # point there); ``on_provider_start`` fires inside the provider task.
    provider_started: Optional[asyncio.Event] = None

    # The filing snapshot (admission) and what the stages derive from it.
    filing_fields: Optional[dict] = None
    company_name: Optional[str] = None
    company_cik: Optional[str] = None
    company_sic: Optional[str] = None
    filing_document_url: Optional[str] = None
    filing_type: Optional[str] = None
    filing_accession_number: Optional[str] = None
    cache_is_valid: bool = False
    excerpt_from_cache: Optional[str] = None
    is_six_k: bool = False
    sixk_class: Optional[str] = None
    sixk_class_audit: Optional[dict] = None
    filing_text: str = ""
    excerpt: Optional[str] = None
    xbrl_metrics: Optional[dict] = None
    summary_payload: Optional[dict] = None
    summary_status: Optional[str] = None

    def __post_init__(self) -> None:
        self.pipeline_started_at = pipeline.time.time()
        self.stage_started_at = self.pipeline_started_at
        self.worker_owner = pipeline.RequestWork(enabled=pipeline.settings.DURABLE_TASKS_ENABLED)

    def emit_funnel(self, *args, **kwargs):
        # Suppressed when the background/cron path drains this generator headless — a precompute
        # run must emit ZERO funnel events (S1, T2 pin). The user-facing SSE path leaves it on.
        if self.emit_funnel_telemetry:
            pipeline.capture_funnel_event(*args, **kwargs)

    def elapsed_ms(self) -> int:
        return int((pipeline.time.time() - self.pipeline_started_at) * 1000)

    def mark_stage(self, stage_name: str):
        now = pipeline.time.time()
        duration = now - self.stage_started_at
        self.stage_timings.append((stage_name, duration))
        self.stage_started_at = now

    async def run_sync_db(self, func, *args, **kwargs):
        """Run a complete, session-owning DB unit in the thread pool."""
        with self.worker_owner.activate():
            return await pipeline.run_in_threadpool(func, *args, **kwargs)

    async def settle_charge(self) -> None:
        """Wait for an in-flight charge write and adopt what it committed. Needed when the await
        on that write was cancelled (pipeline timeout, disconnect) before it could record the month."""
        if self.charge_future is None:
            return
        if not self.charge_future.done():
            await asyncio.wait({self.charge_future})
        if self.charged_month is None and not self.charge_future.cancelled() and self.charge_future.exception() is None:
            month = self.charge_future.result()
            if month is not None:
                self.charged_month = month
                self.usage_reservation_token = None  # the convert deleted it in the same commit

    async def refund_charge(self, reason: str) -> None:
        """Give the unit counted at provider start back (at most once). Called only from the
        provider-failure, timeout and partial-verdict paths — never from cancellation (client
        disconnect)."""
        await self.settle_charge()
        if self.charged_month is None:
            return
        month, self.charged_month = self.charged_month, None
        self.charge_future = None  # refunded: a later settle must not adopt this write again
        filing_id, user_id = self.filing_id, self.user_id

        def refund_sync() -> None:
            with database.SessionLocal() as session:
                pipeline.refund_summary_use(user_id, month, session)

        try:
            await self.run_sync_db(refund_sync)
            logger.info(f"[stream:{filing_id}] Refunded the usage unit counted at provider start ({reason})")
        except Exception as refund_error:  # the unit stays counted; never mask the outcome
            logger.warning(f"[stream:{filing_id}] Could not refund usage unit ({reason}): {refund_error}")

    def record_progress_sync(self, *args, **kwargs) -> None:
        # record_progress refreshes its returned row after committing. Close that read
        # transaction here too; the stream only needs the durable write, not the ORM row.
        with database.SessionLocal() as progress_session:
            pipeline.record_progress(progress_session, *args, **kwargs)

    # Metering point: a held admission lease becomes a counted unit when the provider request
    # is ISSUED — the `provider_start_signal` the request dispatcher fires immediately before
    # the first provider call — not after persistence, and not at task creation (the
    # task parses the filing locally first). The provider bill accrues from that moment and
    # section previews may stream before the complete event, so a client that disconnects
    # after it has consumed the unit; the pipeline's cancellation path (CancelledError /
    # GeneratorExit) deliberately never refunds it. A disconnect or failure BEFORE the signal
    # leaves the lease held, and `release` releases it. The unit is refunded only for outcomes
    # the client cannot induce: a provider-side failure (the task raises, returns an error
    # payload or the pipeline times out) and, under AI_QUALITY_GATE, a partial verdict — so an
    # honest partial still costs nothing. A result that arrives without the signal (a stand-in
    # service) is counted on completion. Callers without a lease (the background drain with
    # current_user=None, and uncapped Pro) keep the completion-time count in the finalize stage.

    def begin_charge(self) -> None:
        """Start the lease-to-unit write (at most once). Called from the dispatcher's start
        signal, inside the provider task, at the instant the request is issued: the write
        exists before this generator can be cancelled, so a disconnect in the gap between the
        signal and the heartbeat loop's next turn still finds it in `release`."""
        if self.usage_reservation_token is None or self.charged_month is not None or self.charge_future is not None:
            return
        token_to_convert = self.usage_reservation_token
        user_id = self.user_id

        def charge_usage_sync() -> Optional[str]:
            with database.SessionLocal() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user is None:
                    return None  # no account row: nothing to count (the lease is released in `release`)
                # Convert the reservation: its delete rides in the increment's commit, so the
                # unit is counted exactly once and never both held and counted, in the month
                # whose quota admitted it (a lease can straddle a rollover).
                month = pipeline.convert_reservation(token_to_convert, session) or pipeline.get_current_month()
                pipeline.increment_user_usage(user.id, month, session)
                return month

        self.charge_future = asyncio.ensure_future(self.run_sync_db(charge_usage_sync))

    async def charge_lease(self) -> None:
        """Convert the held lease into one counted unit (at most once; the lease is cleared)."""
        if self.charged_month is not None:
            return
        self.begin_charge()  # no-op when the signal already started the write
        if self.charge_future is None:
            return  # no lease to convert
        # Shielded: a cancellation here (deadline, disconnect) abandons this await, not the
        # write, and `settle_charge` later reads what the write committed.
        self.charged_month = await asyncio.shield(self.charge_future)
        if self.charged_month is not None:
            self.usage_reservation_token = None

    def on_provider_start(self) -> None:
        self.begin_charge()
        self.provider_started.set()

    async def release(self) -> None:
        """The orchestrator's ``finally``: stop owned work, settle the lease, give the slot back.

        Runs on completion, error, timeout, AND GeneratorExit (client disconnect) — never leaks a
        slot. Entered without an intervening await, so the shield below is in place before the
        first suspension point.
        """
        filing_id = self.filing_id
        # On a client disconnect Starlette cancels this task (ASGI < 2.4, which uvicorn speaks)
        # and re-delivers the cancellation at every await until the generator exits, so an
        # unshielded cleanup would abort at its first await and skip every release below.
        with anyio.CancelScope(shield=True):
            # This generator owns the provider task: disconnect/timeout must close its stream
            # before releasing the slot, with no background retry left running.
            if self.summary_task is not None:
                if not self.summary_task.done():
                    self.summary_task.cancel()
                await asyncio.gather(self.summary_task, return_exceptions=True)
            if self.provider_started_waiter is not None and not self.provider_started_waiter.done():
                self.provider_started_waiter.cancel()
            # Document failures and disconnects can exit before these siblings reach their normal
            # join points. Cancel and drain every request-owned coroutine before releasing its
            # generation slot; none may continue as post-response enrichment.
            owned_siblings = [
                task for task in (self.xbrl_task, self.sections_task, self.fetch_task, self.excerpt_task, self.provider_started_waiter)
                if task is not None
            ]
            for task in owned_siblings:
                if not task.done():
                    task.cancel()
            if owned_siblings:
                await asyncio.gather(*owned_siblings, return_exceptions=True)
            # A reservation still held here was never converted (failure or disconnect before the
            # provider call started, or no account row to count against): give the quota unit back
            # now. A unit counted at provider start is NOT touched here — see the metering point.
            await self.settle_charge()  # a charge committed under a cancelled await has no lease to release
            if self.usage_reservation_token is not None:
                token_to_release = self.usage_reservation_token
                self.usage_reservation_token = None

                def release_reservation_sync() -> None:
                    with database.SessionLocal() as session:
                        pipeline.release_reservation(token_to_release, session)

                try:
                    await self.run_sync_db(release_reservation_sync)
                except Exception as release_error:  # the lease expires on its own; never mask the outcome
                    logger.warning(f"[stream:{filing_id}] Could not release usage reservation: {release_error}")
            # Coroutine cancellation does not terminate its running SQL/Edgar worker. Join the
            # actual concurrent futures after quota settlement, while ownership is still held.
            await self.worker_owner.drain()
        # Release the generation slot first (only if actually acquired), then in-flight leadership,
        # so a queued generation can start as soon as this one is done.
        if self.generation_slot_held and self.generation_semaphore is not None:
            self.generation_semaphore.release()
        # A3: release in-flight leadership so any waiters proceed and serve the persisted result.
        # Runs on completion, error, timeout, AND GeneratorExit (client disconnect) — never leaks a slot.
        if self.inflight_event is not None:
            pipeline._release_inflight(filing_id, self.inflight_event)

        total_elapsed = pipeline.time.time() - self.pipeline_started_at
        breakdown = ", ".join(f"{stage}:{duration:.2f}s" for stage, duration in self.stage_timings)
        if breakdown:
            logger.info(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s ({breakdown})")
        else:
            logger.info(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s")

"""Terminal failure handlers: the orchestrator's ``except TimeoutError`` and ``except Exception`` bodies.

Each refunds a unit counted at provider start (never on cancellation, which skips both handlers),
emits the funnel event, records the error progress in a fresh worker-owned transaction (starting the
row's clock when the error is a leader's first write, ``GenerationRun.error_starts_clock``) and
returns the one terminal error event for the orchestrator to yield.
"""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import httpx

from app import database
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


def _source_failure_details(error: Exception) -> tuple[pipeline.ErrorCode, int | None, str, int | None]:
    """Read bounded exception metadata, including old generic Edgar wrappers during rollout.

    Never parse exception prose or expose URLs/response bodies. The transport owns classification;
    HTTPX's status is retained here for older workers whose outer EdgarError was unclassified.
    """
    status = None
    retry_after = None
    exception_class = type(error).__name__
    limited = False
    seen: set[int] = set()
    current: BaseException | None = error
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        exception_class = type(current).__name__
        delay = None
        if isinstance(current, pipeline.EdgarError):
            candidate_status = current.context.get("status_code")
            if type(candidate_status) is int and 100 <= candidate_status <= 599:
                status = candidate_status
            delay = current.context.get("retry_after_seconds")
        if isinstance(current, pipeline.EdgarRateLimitError):
            limited = True
            delay = delay if delay is not None else current.retry_after
        if isinstance(current, pipeline.CircuitOpenError):
            # A half-open probe denial has no timestamp: use the breaker's own
            # configured recovery period rather than retrying immediately.
            delay = (current.time_until_recovery if current.time_until_recovery is not None
                     else pipeline.edgar_circuit_breaker.config.recovery_timeout)
        if isinstance(current, httpx.HTTPStatusError):
            status = current.response.status_code
            delay = pipeline.SECRateLimiter._retry_after_seconds(current)
        if isinstance(delay, (int, float)) and not isinstance(delay, bool) and math.isfinite(delay) and delay > 0:
            retry_after = max(retry_after or 0, math.ceil(delay))
        limited = limited or status == 429
        current = current.cause if isinstance(current, pipeline.EdgarError) and current.cause else current.__cause__
    code = pipeline.ErrorCode.SEC_RATE_LIMITED if limited else pipeline.ErrorCode.FILING_SOURCE_UNAVAILABLE
    return code, status, exception_class, retry_after


def _source_retryable(error: Exception, status: int | None) -> bool:
    """Closed transient policy. Access denial/parse defects must not become retry storms."""
    if status is not None:
        return status in {404, 408, 429, 500, 502, 503, 504}
    seen: set[int] = set()
    current: BaseException | None = error
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        if isinstance(current, (pipeline.EdgarNetworkError, pipeline.FilingNotFoundError, pipeline.CircuitOpenError,
                                httpx.TransportError, TimeoutError)):
            return True
        current = current.cause if isinstance(current, pipeline.EdgarError) and current.cause else current.__cause__
    return False


async def source_failed(run: GenerationRun, error: Exception) -> dict:
    """Persist the terminal source failure; return additive metadata for its existing error frame."""
    code, status, exception_class, retry_after = _source_failure_details(error)
    evidence = run.request_evidence
    request_id = evidence.properties["request_id"] if evidence is not None else None
    if evidence is not None:
        evidence.reason = code.value
    logger.error(
        "[stream:%s] Source fetch failed code=%s upstream_status=%s exception_class=%s request_id=%s",
        run.filing_id, code.value, status, exception_class, request_id,
    )
    run.emit_funnel(
        run.telemetry_distinct_id, pipeline.EVENT_GENERATION_FAILED,
        duration_ms=run.elapsed_ms(), result_type="error", entry_point=run.telemetry_entry_point,
        error=code.value, **run.telemetry_ctx,
    )

    def record_source_error() -> None:
        with database.SessionLocal() as session:
            pipeline.record_progress(
                session, run.filing_id, "error", error=code.value,
                starts_run=run.error_starts_clock(),
            )

    try:
        await run.run_sync_db(record_source_error)
    except Exception as persistence_error:
        logger.error(
            "[stream:%s] Source failure progress write failed exception_class=%s request_id=%s",
            run.filing_id, type(persistence_error).__name__, request_id,
        )
    fields = {"code": code.value, "retryable": _source_retryable(error, status)}
    if request_id is not None:
        fields["request_id"] = request_id
    if retry_after is not None:
        fields["retry_after_seconds"] = retry_after
    return fields


async def timed_out(run: GenerationRun) -> dict:
    """Pipeline hard timeout reached (the backstop deadline, or an exhausted follower budget)."""
    filing_id = run.filing_id
    if run.request_evidence is not None:
        run.request_evidence.reason = "pipeline_timeout"
    # Pipeline hard timeout reached
    logger.warning(f"[stream:{filing_id}] Pipeline timeout after {pipeline.PIPELINE_TIMEOUT_SECONDS}s")
    await run.refund_charge("pipeline timeout")
    run.emit_funnel(
        run.telemetry_distinct_id,
        pipeline.EVENT_GENERATION_TIMED_OUT,
        duration_ms=run.elapsed_ms(),
        result_type="timeout",
        entry_point=run.telemetry_entry_point,
        **run.telemetry_ctx,
    )

    # Each worker owns its session through cleanup, even if cancellation interrupts
    # its caller. Error reporting uses another short worker-owned transaction.
    starts_run = run.error_starts_clock()

    def record_timeout_progress():
        with database.SessionLocal() as err_session:
            pipeline.record_progress(err_session, filing_id, "error", error="Pipeline timeout", starts_run=starts_run)
    try:
        await run.run_sync_db(record_timeout_progress)
    except Exception as e:
        logger.error(f"[stream:{filing_id}] Failed to record pipeline timeout error: {e}", exc_info=True)
    return {'type': 'error', 'message': 'The summary timed out before it finished. Try again.',
            **({'retryable': True} if run.durable_lease is not None else {})}


async def failed(run: GenerationRun, e: Exception) -> dict:
    """Any other failure. CancelledError/GeneratorExit (client disconnect) never reach this handler:
    the unit counted at provider start is refunded only for a failure the client did not cause."""
    filing_id = run.filing_id
    logger.error(f"[stream:{filing_id}] Error in streaming summary: {str(e)}", exc_info=True)
    error_msg = str(e)
    await run.refund_charge("pipeline failure")
    run.emit_funnel(
        run.telemetry_distinct_id,
        pipeline.EVENT_GENERATION_FAILED,
        duration_ms=run.elapsed_ms(),
        result_type="error",
        entry_point=run.telemetry_entry_point,
        error=error_msg[:200],
        **run.telemetry_ctx,
    )

    # A failed worker closes its own transaction; error reporting owns another one.
    starts_run = run.error_starts_clock()

    def record_stream_error_progress():
        with database.SessionLocal() as err_session:
            pipeline.record_progress(err_session, filing_id, "error", error=error_msg[:200], starts_run=starts_run)
    try:
        await run.run_sync_db(record_stream_error_progress)
    except Exception as e:
        logger.error(f"[stream:{filing_id}] Failed to record streaming error: {e}", exc_info=True)

    if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
        error_message = error_msg[:200]
    else:
        error_message = "We could not generate this summary. Try again shortly."

    return {'type': 'error', 'message': error_message}

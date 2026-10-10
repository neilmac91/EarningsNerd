"""Terminal failure handlers: the orchestrator's ``except TimeoutError`` and ``except Exception`` bodies.

Each refunds a unit counted at provider start (never on cancellation, which skips both handlers),
emits the funnel event, records the error progress in a fresh worker-owned transaction and returns
the one terminal error event for the orchestrator to yield.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app import database
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


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
    def record_timeout_progress():
        with database.SessionLocal() as err_session:
            pipeline.record_progress(err_session, filing_id, "error", error="Pipeline timeout")
    try:
        await run.run_sync_db(record_timeout_progress)
    except Exception as e:
        logger.error(f"[stream:{filing_id}] Failed to record pipeline timeout error: {e}", exc_info=True)
    return {'type': 'error', 'message': 'Summary generation timed out. Please try again.'}


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
    def record_stream_error_progress():
        with database.SessionLocal() as err_session:
            pipeline.record_progress(err_session, filing_id, "error", error=error_msg[:200])
    try:
        await run.run_sync_db(record_stream_error_progress)
    except Exception as e:
        logger.error(f"[stream:{filing_id}] Failed to record streaming error: {e}", exc_info=True)

    if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
        error_message = error_msg[:200]
    else:
        error_message = "Unable to retrieve this filing at the moment — please try again shortly."

    return {'type': 'error', 'message': error_message}

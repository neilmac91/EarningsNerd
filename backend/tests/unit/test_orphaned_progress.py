"""Tests for orphaned/stalled summary-generation progress handling (roadmap Q7).

Covers:
- mark_stale_progress_as_error: stuck non-terminal rows are flipped to a retryable error.
- run_generation_guarded: a crashing fire-and-forget background task always records a
  terminal 'error' state instead of leaving the row stuck forever.
"""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import SummaryGenerationProgress
from app.services import summary_generation_service as svc
from app.services.summary_generation_service import (
    STALE_PROGRESS_SECONDS,
    mark_stale_progress_as_error,
    run_generation_guarded,
    _utcnow,
)


def _progress(stage: str, age_seconds: float) -> SummaryGenerationProgress:
    ts = _utcnow() - timedelta(seconds=age_seconds)
    return SummaryGenerationProgress(
        filing_id=1,
        stage=stage,
        started_at=ts,
        updated_at=ts,
        elapsed_seconds=age_seconds,
    )


def test_stale_non_terminal_row_is_flipped_to_error():
    progress = _progress("fetching", STALE_PROGRESS_SECONDS + 60)
    changed = mark_stale_progress_as_error(progress)
    assert changed is True
    assert progress.stage == "error"
    assert "retry" in (progress.error or "").lower()


def test_recent_non_terminal_row_is_left_alone():
    progress = _progress("analyzing", 5)
    changed = mark_stale_progress_as_error(progress)
    assert changed is False
    assert progress.stage == "analyzing"


@pytest.mark.parametrize("terminal_stage", ["completed", "error", "partial"])
def test_terminal_rows_are_never_touched(terminal_stage):
    progress = _progress(terminal_stage, STALE_PROGRESS_SECONDS + 600)
    assert mark_stale_progress_as_error(progress) is False
    assert progress.stage == terminal_stage


@pytest.mark.asyncio
async def test_guarded_wrapper_records_error_on_crash():
    """If the background task crashes in its setup phase, the wrapper must record 'error'."""
    recorded = {}

    def fake_record_progress(db, filing_id, stage, *, error=None, **kwargs):
        recorded["stage"] = stage
        recorded["error"] = error

    fake_session = MagicMock()
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    with patch.object(svc, "generate_summary_background", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(svc, "record_progress", side_effect=fake_record_progress), \
         patch.object(svc, "SessionLocal", return_value=fake_session):
        # Should NOT raise — the wrapper swallows and records.
        await run_generation_guarded(filing_id=1, user_id=None)

    assert recorded["stage"] == "error"
    assert "boom" in (recorded["error"] or "")


@pytest.mark.asyncio
async def test_guarded_wrapper_is_transparent_on_success():
    """A successful background task must not trigger any error recording."""
    with patch.object(svc, "generate_summary_background", new=AsyncMock(return_value=None)), \
         patch.object(svc, "record_progress") as mock_record:
        await run_generation_guarded(filing_id=1, user_id=None)
    mock_record.assert_not_called()

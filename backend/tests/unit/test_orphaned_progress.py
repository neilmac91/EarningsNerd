"""Tests for orphaned/stalled summary-generation progress handling (roadmap Q7).

Covers mark_stale_progress_as_error: a stuck non-terminal progress row is flipped to a
retryable 'error' state, while recent and terminal rows are left untouched.
"""
from datetime import timedelta

import pytest

from app.models import SummaryGenerationProgress
from app.services.summary_generation_service import (
    STALE_PROGRESS_SECONDS,
    mark_stale_progress_as_error,
)
from app.utils.datetimes import utcnow


def _progress(stage: str, age_seconds: float) -> SummaryGenerationProgress:
    ts = utcnow() - timedelta(seconds=age_seconds)
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

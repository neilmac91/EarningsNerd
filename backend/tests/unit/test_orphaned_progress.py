"""Orphaned or stalled summary-generation progress (roadmap Q7, E215).

Fire-and-forget background generation can die without writing a terminal stage. The progress poll,
``summary_generation_service.progress_poll_answer`` (``GET /api/summaries/filing/{id}/progress``), marks a
row whose stage is not terminal and whose last write is older than ``STALE_PROGRESS_SECONDS`` a retryable
error, so the reader is not left waiting on a run that will not finish. ``progress_is_stalled`` checks the
row the poll read, and ``mark_stale_progress_as_error`` marks it in one UPDATE by filing on the same
criteria.

Before E215 the poll flipped the row it had read in memory and committed. A clear landing between the read
and the commit (an admin reset, say) left that UPDATE matching no row, and the poll answered 500
(``StaleDataError``); a write landing there (a new run's first, or the run's own last) was overwritten with
the stall's error; and a clear landing after the commit, before the answer read the row the commit had
expired, answered 500 too (``ObjectDeletedError``). Each race here runs the other write, committed in a
session of its own, just before the poll's UPDATE or, for the last, just before its first read after it.
The service's clock is pinned, so a row's age is exact, and a seeded row starts 600 s before its last write,
so a check of the start instead of the last write shows. Beside each case's filing is a neighbour with a summary
and a stalled row, each first in its table, so a mark or a read that loses its filing's filter shows too.
``tests/integration/test_summary_progress_transactions.py`` runs the first two races, and a write or a clear
that holds the row while the mark waits, on PostgreSQL.
"""
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, SessionLocal
from app.models import Company, Filing, Summary, SummaryGenerationProgress
from app.services import summary_generation_service
from app.services.summary_generation_service import (
    STALE_PROGRESS_SECONDS,
    STALLED_ERROR,
    mark_stale_progress_as_error,
    progress_is_stalled,
    progress_poll_answer,
)

# The poll's one write: the stale mark's UPDATE.
MARK = re.compile(r"\s*UPDATE summary_generation_progress\b")
# A read of the progress table: the poll's, or the ORM's refresh of an expired row.
READ = re.compile(r"\s*SELECT\b.*\bFROM summary_generation_progress\b", re.DOTALL)
# The service's clock in every case, pinned so a row's age is exact.
NOW = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)
STALLED = STALE_PROGRESS_SECONDS + 3600


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setattr(summary_generation_service, "utcnow", lambda: NOW)


def _progress(stage: str, age_seconds: float, filing_id: int = 1) -> SummaryGenerationProgress:
    last_write = NOW - timedelta(seconds=age_seconds)
    return SummaryGenerationProgress(filing_id=filing_id, stage=stage, started_at=last_write - timedelta(seconds=600),
                                     updated_at=last_write, elapsed_seconds=600.0)


def test_a_non_terminal_row_past_the_cutoff_is_stalled():
    assert progress_is_stalled(_progress("fetching", STALE_PROGRESS_SECONDS + 1)) is True


def test_a_row_written_within_the_cutoff_is_not_stalled():
    # Its start is past the cutoff, its last write is not.
    assert progress_is_stalled(_progress("analyzing", STALE_PROGRESS_SECONDS)) is False


@pytest.mark.parametrize("terminal_stage", ["completed", "error", "partial"])
def test_a_terminal_row_is_never_stalled(terminal_stage):
    assert progress_is_stalled(_progress(terminal_stage, STALLED)) is False


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _session(engine):
    """A session with production's settings (``SessionLocal``'s) on this case's engine."""
    return sessionmaker(**{**SessionLocal.kw, "bind": engine})()


def _filing(company_id: int, number: int) -> Filing:
    return Filing(company_id=company_id, accession_number=f"0000000215-26-00000{number}", filing_type="10-K",
                  filing_date=NOW, sec_url=f"https://example.test/filing-{number}/",
                  document_url=f"https://example.test/filing-{number}.htm")


# Another filing's progress row in every case: stalled too, and never touched by this filing's poll or mark.
NEIGHBOUR = {"stage": "analyzing", "error": None}


@pytest.fixture
def neighbour_id(engine) -> int:
    """Another filing, with a summary and a stalled progress row, made before this case's filing so that each comes
    first in its table: a mark or a read that loses its filing's filter reaches them."""
    with _session(engine) as db:
        company = Company(cik="0000000215", ticker="STLL", name="Stalled Progress")
        db.add(company)
        db.flush()
        neighbour = _filing(company.id, 0)
        db.add(neighbour)
        db.flush()
        db.add(Summary(filing_id=neighbour.id))
        db.add(_progress(NEIGHBOUR["stage"], STALLED, neighbour.id))
        db.commit()
        return neighbour.id


@pytest.fixture
def filing_id(engine, neighbour_id) -> int:
    with _session(engine) as db:
        filing = _filing(db.query(Company).one().id, 1)
        db.add(filing)
        db.commit()
        return filing.id


def _seed(engine, filing_id, *, stage, age_seconds):
    with _session(engine) as db:
        db.add(_progress(stage, age_seconds, filing_id))
        db.commit()


def _row(engine, filing_id):
    with _session(engine) as db:
        row = db.get(SummaryGenerationProgress, filing_id)
        return None if row is None else {"stage": row.stage, "error": row.error}


def _poll(engine, filing_id):
    with _session(engine) as db:
        return progress_poll_answer(db, filing_id)


@contextmanager
def _statements(engine):
    """Yield the statements the engine runs inside the block."""
    ran: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        ran.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield ran
    finally:
        event.remove(engine, "before_cursor_execute", before)


@contextmanager
def _just_before_the_mark(engine, other_write):
    """Run ``other_write`` once, committed in a session of its own, just before the mark's UPDATE; yields the
    statements it ran before, so a case can check that it ran."""
    ran: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if not ran and MARK.match(statement):
            ran.append(statement)
            with _session(engine) as other:
                other_write(other)
                other.commit()

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield ran
    finally:
        event.remove(engine, "before_cursor_execute", before)


@contextmanager
def _just_after_the_mark(engine, other_write):
    """Run ``other_write`` once, committed in a session of its own, just before the first read of the progress table
    after the mark's UPDATE (the poll's re-read; before E215, the refresh of the row the commit expired); yields the
    statements it ran before, so a case can check that it ran."""
    marked: list[str] = []
    ran: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if MARK.match(statement):
            marked.append(statement)
        elif marked and not ran and READ.match(statement):
            ran.append(statement)
            with _session(engine) as other:
                other_write(other)
                other.commit()

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield ran
    finally:
        event.remove(engine, "before_cursor_execute", before)


def _clear(other, filing_id):
    other.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id).delete(synchronize_session=False)


def test_the_poll_marks_a_stalled_row_and_answers_the_error(engine, filing_id, neighbour_id):
    _seed(engine, filing_id, stage="analyzing", age_seconds=STALLED)
    answer = _poll(engine, filing_id)
    assert (answer["stage"], answer["error"]) == ("error", STALLED_ERROR)
    assert _row(engine, filing_id) == {"stage": "error", "error": STALLED_ERROR}
    assert _row(engine, neighbour_id) == NEIGHBOUR


def test_the_poll_answers_a_live_row_without_writing(engine, filing_id):
    _seed(engine, filing_id, stage="analyzing", age_seconds=5)
    with _statements(engine) as ran:
        answer = _poll(engine, filing_id)
    assert (answer["stage"], answer["error"]) == ("analyzing", None)
    assert not [statement for statement in ran if MARK.match(statement)]


@pytest.mark.parametrize("stage", ["analyzing", "completed", "error", "partial"])
@pytest.mark.parametrize("age_seconds", [STALE_PROGRESS_SECONDS, STALE_PROGRESS_SECONDS + 1])
def test_the_mark_matches_the_rows_the_check_calls_stalled(engine, filing_id, neighbour_id, stage, age_seconds):
    """The UPDATE's criteria are the check's, at the cutoff and on each terminal stage, and its filing's row is the
    only one it marks."""
    _seed(engine, filing_id, stage=stage, age_seconds=age_seconds)
    stalled = progress_is_stalled(_progress(stage, age_seconds))
    with _session(engine) as db:
        assert mark_stale_progress_as_error(db, filing_id) is stalled
        db.commit()
    assert _row(engine, filing_id)["stage"] == ("error" if stalled else stage)
    assert _row(engine, neighbour_id) == NEIGHBOUR


def test_a_clear_just_before_the_mark_answers_pending(engine, filing_id, neighbour_id):
    _seed(engine, filing_id, stage="analyzing", age_seconds=STALLED)
    with _just_before_the_mark(engine, lambda other: _clear(other, filing_id)) as ran:
        answer = _poll(engine, filing_id)
    assert ran, "the clear did not run before the mark"
    assert answer == {"stage": "pending", "elapsedSeconds": 0}
    assert _row(engine, filing_id) is None
    assert _row(engine, neighbour_id) == NEIGHBOUR


def test_a_clear_just_after_the_marks_commit_answers_pending(engine, filing_id, neighbour_id):
    """Before E215 the answer read the row the commit had expired, and a clear in between raised
    ``ObjectDeletedError``: the poll answered 500."""
    _seed(engine, filing_id, stage="analyzing", age_seconds=STALLED)
    with _just_after_the_mark(engine, lambda other: _clear(other, filing_id)) as ran:
        answer = _poll(engine, filing_id)
    assert ran, "the clear did not run after the mark"
    assert answer == {"stage": "pending", "elapsedSeconds": 0}
    assert _row(engine, filing_id) is None
    assert _row(engine, neighbour_id) == NEIGHBOUR


@pytest.mark.parametrize(("stage", "error", "starts_run"), [
    ("fetching", None, True),  # a new run's first write
    ("error", "Pipeline timeout", False),  # the run's own last write
])
def test_a_write_just_before_the_mark_is_kept_and_answered(engine, filing_id, neighbour_id, stage, error,
                                                           starts_run):
    _seed(engine, filing_id, stage="analyzing", age_seconds=STALLED)

    def write(other):
        summary_generation_service.record_progress(other, filing_id, stage, error=error, starts_run=starts_run)

    with _just_before_the_mark(engine, write) as ran:
        answer = _poll(engine, filing_id)
    assert ran, "the write did not run before the mark"
    assert (answer["stage"], answer["error"]) == (stage, error)
    assert _row(engine, filing_id) == {"stage": stage, "error": error}
    assert _row(engine, neighbour_id) == NEIGHBOUR

"""E214 and E215 on PostgreSQL: another transaction's write of a filing's progress row cannot fail a run's progress
write or the progress poll, nor have the poll overwrite it.

E214: ``summary_generation_service.record_progress`` writes the row in one
``INSERT … ON CONFLICT (filing_id) DO UPDATE``.

- A clear committed just before the write: the write inserts a fresh row. Before E214 the write's UPDATE matched no
  row, and SQLAlchemy raised ``StaleDataError``.
- An insert committed just before the write: the write updates that row and keeps its ``started_at``. Before E214
  the write's INSERT collided on the filing's key, ``IntegrityError``.
- A clear holding the row, uncommitted, as the write runs: the write waits for it, then inserts a fresh row after its
  commit, or updates the row after its rollback. Before E214 the write read the row, its UPDATE waited, and after the
  commit it matched no row.
- Three writers of a filing that has no row, each held at its write until all three reach it: each succeeds, and the
  filing has one row. Before E214 two of the three INSERTs collided.

A seeded row's last write comes 10 s after its start, so a count from the last write, not from the start, shows.

E216: a run's first write (``starts_run``, the pipeline's fetch stage) restarts the clock on a row an earlier run left;
before E216 it kept that row's ``started_at``.

E215: the progress poll (``progress_poll_answer``) marks a stalled row, one whose stage is not terminal and whose last
write is older than ``STALE_PROGRESS_SECONDS``, a retryable error in one UPDATE by filing on those criteria, and reads
the row after it.

- A clear committed just before the mark: the poll answers "pending". Before E215 the poll flipped the row it had read
  in memory, its commit's UPDATE matched no row, and SQLAlchemy raised ``StaleDataError`` (a 500).
- A run's write committed just before the mark: the row keeps it, and the poll answers it. Before E215 the stall's
  error overwrote it.
- A run's write, or a clear, holding the row uncommitted as the mark runs: the mark waits for it; after its commit the
  mark matches nothing, and the poll answers the write, or "pending" after the clear; after its rollback it marks
  the row. Before E215 the mark's UPDATE matched the row by its key: after a write's commit it overwrote the
  write, and after a clear's it matched no row.

``tests/unit/test_progress_write_is_one_upsert.py`` holds the write's columns, and E214's first two races, on SQLite;
``tests/unit/test_orphaned_progress.py`` holds the mark's criteria, E215's first two races and a clear just after
the mark's commit, on SQLite.
PROGRESS_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI ("Verify summary progress concurrency on
PostgreSQL"); each case owns a disposable schema, and without the variable they skip.
"""
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import Company, Filing, Summary, SummaryGenerationProgress
from app.services import summary_generation_service

# The statement that writes the progress table: the UPDATE or INSERT before E214, or the upsert's INSERT.
WRITE = re.compile(r"\s*(?:INSERT INTO|UPDATE) summary_generation_progress\b")
# The service's clock in every case, pinned so an elapsed time is exact.
NOW = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setattr(summary_generation_service, "utcnow", lambda: NOW)


@pytest.fixture
def postgres_engine():
    url = os.environ.get("PROGRESS_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PROGRESS_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "The summary progress gate requires PostgreSQL"
    schema = f"summary_progress_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(
            engine, tables=[Company.__table__, Filing.__table__, Summary.__table__, SummaryGenerationProgress.__table__])
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine or
    connection (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


@pytest.fixture
def filing_id(postgres_engine) -> int:
    with _session(postgres_engine) as db:
        company = Company(cik="0000000214", ticker="PRGW", name="Progress Writer")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000214-26-000001", filing_type="10-K",
                        filing_date=NOW, sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.commit()
        return filing.id


def _seed(engine, filing_id, *, age_seconds):
    started_at = NOW - timedelta(seconds=age_seconds)
    with _session(engine) as db:
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage="fetching", started_at=started_at,
                                         updated_at=started_at + timedelta(seconds=10), elapsed_seconds=10.0))
        db.commit()
    return started_at


def _rows(engine, filing_id):
    with _session(engine) as db:
        return [{"stage": row.stage, "started_at": row.started_at, "elapsed_seconds": row.elapsed_seconds}
                for row in db.query(SummaryGenerationProgress).filter_by(filing_id=filing_id)]


def _write(engine, filing_id, stage):
    with _session(engine) as db:
        summary_generation_service.record_progress(db, filing_id, stage)


def _clear(db, filing_id):
    db.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id).delete(synchronize_session=False)


@contextmanager
def _just_before_the_write(engine, other_write):
    """Run ``other_write`` once, committed in a session of its own, just before the first statement that writes the
    progress table; yields the statements it ran before, so a case can check that it ran."""
    ran: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if not ran and WRITE.match(statement):
            ran.append(statement)
            with _session(engine) as other:
                other_write(other)
                other.commit()

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield ran
    finally:
        event.remove(engine, "before_cursor_execute", before)


def test_a_clear_committed_just_before_the_write_leaves_a_fresh_row(postgres_engine, filing_id):
    _seed(postgres_engine, filing_id, age_seconds=60)
    with _just_before_the_write(postgres_engine, lambda other: _clear(other, filing_id)) as ran:
        _write(postgres_engine, filing_id, "analyzing")
    assert ran, "the clear did not run before the write"
    assert _rows(postgres_engine, filing_id) == [{"stage": "analyzing", "started_at": NOW, "elapsed_seconds": 0.0}]


def test_an_insert_committed_just_before_the_write_is_updated_with_its_start_kept(postgres_engine, filing_id):
    started_at = NOW - timedelta(seconds=30)

    def insert(other):
        other.add(SummaryGenerationProgress(filing_id=filing_id, stage="fetching", started_at=started_at,
                                            updated_at=started_at + timedelta(seconds=10), elapsed_seconds=10.0))

    with _just_before_the_write(postgres_engine, insert) as ran:
        _write(postgres_engine, filing_id, "analyzing")
    assert ran, "the insert did not run before the write"
    assert _rows(postgres_engine, filing_id) == [
        {"stage": "analyzing", "started_at": started_at, "elapsed_seconds": pytest.approx(30.0, abs=1e-6)}]


@pytest.mark.parametrize("commit_clear", [True, False])
def test_a_write_behind_an_uncommitted_clear_waits_and_follows_its_outcome(postgres_engine, filing_id, commit_clear):
    started_at = _seed(postgres_engine, filing_id, age_seconds=30)
    entered = threading.Event()
    finished = threading.Event()

    def before(conn, cursor, statement, parameters, context, executemany):
        if WRITE.match(statement):
            entered.set()

    def write():
        try:
            _write(postgres_engine, filing_id, "analyzing")
        finally:
            finished.set()

    with _session(postgres_engine) as clearing:
        _clear(clearing, filing_id)  # the uncommitted delete holds the row
        event.listen(postgres_engine, "before_cursor_execute", before)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(write)
                try:
                    assert entered.wait(5), "the write did not reach its database write"
                    if finished.wait(0.2):
                        future.result(timeout=5)  # a write that raised shows its own error
                        pytest.fail("the write passed an uncommitted clear")
                finally:
                    if commit_clear:
                        clearing.commit()
                    else:
                        clearing.rollback()
                future.result(timeout=6)
        finally:
            event.remove(postgres_engine, "before_cursor_execute", before)
    # A committed clear starts the run's clock afresh; a rolled-back one leaves the row, and its start, as they were.
    expected = ({"stage": "analyzing", "started_at": NOW, "elapsed_seconds": 0.0} if commit_clear else
                {"stage": "analyzing", "started_at": started_at, "elapsed_seconds": pytest.approx(30.0, abs=1e-6)})
    assert _rows(postgres_engine, filing_id) == [expected]


def test_writers_of_a_filing_with_no_row_each_succeed_on_one_row(postgres_engine, filing_id):
    stages = ("fetching", "analyzing", "summarizing")
    at_the_write = threading.Barrier(len(stages), timeout=5)
    local = threading.local()

    def before(conn, cursor, statement, parameters, context, executemany):
        if getattr(local, "first", False) and WRITE.match(statement):
            local.first = False
            at_the_write.wait()

    def write(stage):
        local.first = True
        _write(postgres_engine, filing_id, stage)

    event.listen(postgres_engine, "before_cursor_execute", before)
    try:
        with ThreadPoolExecutor(max_workers=len(stages)) as pool:
            futures = [pool.submit(write, stage) for stage in stages]
            for future in futures:
                future.result(timeout=10)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", before)
    [row] = _rows(postgres_engine, filing_id)
    assert row["stage"] in stages and row["started_at"] == NOW


def test_a_runs_first_write_restarts_the_clock_on_an_earlier_runs_row(postgres_engine, filing_id):
    _seed(postgres_engine, filing_id, age_seconds=7200)
    with _session(postgres_engine) as db:
        summary_generation_service.record_progress(db, filing_id, "fetching", starts_run=True)
    assert _rows(postgres_engine, filing_id) == [{"stage": "fetching", "started_at": NOW, "elapsed_seconds": 0.0}]


# E215: the progress poll's stale mark.
STALLED = summary_generation_service.STALE_PROGRESS_SECONDS + 3600


def _poll(engine, filing_id):
    with _session(engine) as db:
        return summary_generation_service.progress_poll_answer(db, filing_id)


def _states(engine, filing_id):
    with _session(engine) as db:
        return [{"stage": row.stage, "error": row.error}
                for row in db.query(SummaryGenerationProgress).filter_by(filing_id=filing_id)]


def test_a_clear_committed_just_before_the_mark_answers_pending(postgres_engine, filing_id):
    _seed(postgres_engine, filing_id, age_seconds=STALLED)
    with _just_before_the_write(postgres_engine, lambda other: _clear(other, filing_id)) as ran:
        answer = _poll(postgres_engine, filing_id)
    assert ran, "the clear did not run before the mark"
    assert answer == {"stage": "pending", "elapsedSeconds": 0}
    assert _states(postgres_engine, filing_id) == []


def test_a_write_committed_just_before_the_mark_is_kept_and_answered(postgres_engine, filing_id):
    _seed(postgres_engine, filing_id, age_seconds=STALLED)

    def write(other):
        summary_generation_service.record_progress(other, filing_id, "analyzing")

    with _just_before_the_write(postgres_engine, write) as ran:
        answer = _poll(postgres_engine, filing_id)
    assert ran, "the write did not run before the mark"
    assert (answer["stage"], answer["error"]) == ("analyzing", None)
    assert _states(postgres_engine, filing_id) == [{"stage": "analyzing", "error": None}]


def _hold_a_write(db, filing_id):
    # A run's write, as record_progress's conflict update makes it.
    db.query(SummaryGenerationProgress).filter_by(filing_id=filing_id).update(
        {"stage": "analyzing", "updated_at": NOW, "error": None}, synchronize_session=False)


_HELD = {"write": _hold_a_write, "clear": _clear}
# What the poll answers, and the filing's rows, once the holder ends: a committed write leaves the row fresh, so the
# mark leaves it, and a committed clear leaves nothing; after a rollback the mark finds the stalled row it read.
_AFTER_COMMIT = {"write": [{"stage": "analyzing", "error": None}], "clear": []}
_MARKED = [{"stage": "error", "error": summary_generation_service.STALLED_ERROR}]


@pytest.mark.parametrize("holder", ["write", "clear"])
@pytest.mark.parametrize("commit_holder", [True, False])
def test_a_mark_behind_an_uncommitted_holder_waits_and_follows_its_outcome(
        postgres_engine, filing_id, holder, commit_holder):
    _seed(postgres_engine, filing_id, age_seconds=STALLED)
    entered = threading.Event()
    finished = threading.Event()

    def before(conn, cursor, statement, parameters, context, executemany):
        if WRITE.match(statement):
            entered.set()

    def poll():
        try:
            return _poll(postgres_engine, filing_id)
        finally:
            finished.set()

    with _session(postgres_engine) as holding:
        _HELD[holder](holding, filing_id)  # the uncommitted write or clear holds the row
        event.listen(postgres_engine, "before_cursor_execute", before)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(poll)
                try:
                    assert entered.wait(5), "the poll did not reach its mark"
                    if finished.wait(0.2):
                        future.result(timeout=5)  # a poll that raised shows its own error
                        pytest.fail(f"the mark passed an uncommitted {holder}")
                finally:
                    if commit_holder:
                        holding.commit()
                    else:
                        holding.rollback()
                answer = future.result(timeout=6)
        finally:
            event.remove(postgres_engine, "before_cursor_execute", before)
    rows = _AFTER_COMMIT[holder] if commit_holder else _MARKED
    if rows:
        assert {"stage": answer["stage"], "error": answer["error"]} == rows[0]
    else:
        assert answer == {"stage": "pending", "elapsedSeconds": 0}
    assert _states(postgres_engine, filing_id) == rows

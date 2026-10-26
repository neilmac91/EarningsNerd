"""E214: a filing's progress row is written in one statement, so a clear or an insert landing just before the write
cannot fail the run.

``summary_generation_service.record_progress`` read the row, then updated it or inserted one. A clear landing between
the two (a Pro force's on the generate stream, from either of the API's instances, or an admin reset) left the UPDATE
matching no row, and SQLAlchemy raised ``StaleDataError``; an insert landing there (another run of the same filing, on
the other instance) made the INSERT collide on the filing's key, ``IntegrityError``. Either reached the pipeline's
failure stage, and the reader got the error card. The write is now one ``INSERT … ON CONFLICT (filing_id) DO UPDATE``:
after a clear it inserts a fresh row, and after an insert it updates that row and keeps its ``started_at``, unless the
write starts a run (E216, below).

Each race runs the other write, committed in a session of its own, just before the statement that writes the progress
table, which before E214 came after the read. The service's clock is pinned, so each elapsed time is exact; SQLite's
date functions keep milliseconds, which the tolerance allows for. A seeded row's last write comes 10 s after its
start, so a count from the last write, not from the start, shows. These cases run on SQLite;
``tests/integration/test_summary_progress_transactions.py`` runs the races, and a clear that holds the row while the
write waits, on PostgreSQL.

E216: an admitted run's first write (``starts_run``, the pipeline's fetch stage) restarts the clock on a row an
earlier run left. Nothing clears that row before a retry after an error or the unready summary's regeneration, so
before E216 the new run's elapsed time counted from the earlier run's start (two hours, on a two-hour-old error row).
The last case drives the one orchestrator end to end, unforced and forced, onto such a row: the anchors pin the fetch
stage's request and the cases before it the write, and it holds the two together (the forced run included, and the
writer the pipeline reaches).
"""
import re
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, SessionLocal
from app.database import engine as app_engine
from app.models import Company, Filing, SummaryGenerationProgress
from app.services import summary_generation_service, summary_pipeline
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)
from app.utils.datetimes import utcnow

# The statement that writes the progress table: the UPDATE or INSERT before E214, or the upsert's INSERT.
WRITE = re.compile(r"\s*(?:INSERT INTO|UPDATE) summary_generation_progress\b")
# The service's clock in every case, pinned so an elapsed time is exact.
NOW = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setattr(summary_generation_service, "utcnow", lambda: NOW)


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _session(engine):
    """A session with production's settings (``SessionLocal``'s) on this case's engine."""
    return sessionmaker(**{**SessionLocal.kw, "bind": engine})()


@pytest.fixture
def filing_id(engine) -> int:
    with _session(engine) as db:
        company = Company(cik="0000000214", ticker="PRGW", name="Progress Writer")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000000214-26-000001", filing_type="10-K",
                        filing_date=utcnow(), sec_url="https://example.test/filing/",
                        document_url="https://example.test/filing.htm")
        db.add(filing)
        db.commit()
        return filing.id


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def _row(engine, filing_id):
    with _session(engine) as db:
        row = db.get(SummaryGenerationProgress, filing_id)
        if row is None:
            return None
        return {"stage": row.stage, "started_at": _aware(row.started_at), "updated_at": _aware(row.updated_at),
                "elapsed_seconds": row.elapsed_seconds, "error": row.error, "section_coverage": row.section_coverage}


def _seed(engine, filing_id, *, age_seconds, stage="fetching", error=None, section_coverage=None):
    started_at = NOW - timedelta(seconds=age_seconds)
    with _session(engine) as db:
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage=stage, started_at=started_at,
                                         updated_at=started_at + timedelta(seconds=10), elapsed_seconds=10.0,
                                         error=error, section_coverage=section_coverage))
        db.commit()
    return started_at


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


def _write(engine, filing_id, stage, **kwargs):
    with _session(engine) as db:
        summary_generation_service.record_progress(db, filing_id, stage, **kwargs)


def test_a_clear_just_before_the_write_leaves_a_fresh_row(engine, filing_id):
    _seed(engine, filing_id, age_seconds=60)

    def clear(other):
        other.query(SummaryGenerationProgress).filter(
            SummaryGenerationProgress.filing_id == filing_id).delete(synchronize_session=False)

    with _just_before_the_write(engine, clear) as ran:
        _write(engine, filing_id, "analyzing")
    assert ran, "the clear did not run before the write"
    row = _row(engine, filing_id)
    # The run's row starts a fresh clock, as after a clear that lands before the run's first write.
    assert row["stage"] == "analyzing"
    assert row["started_at"] == NOW
    assert row["elapsed_seconds"] == 0.0


def test_an_insert_just_before_the_write_is_updated_with_its_start_kept(engine, filing_id):
    started_at = NOW - timedelta(seconds=30)

    def insert(other):
        other.add(SummaryGenerationProgress(filing_id=filing_id, stage="fetching", started_at=started_at,
                                            updated_at=started_at + timedelta(seconds=10), elapsed_seconds=10.0))

    with _just_before_the_write(engine, insert) as ran:
        _write(engine, filing_id, "analyzing")
    assert ran, "the insert did not run before the write"
    row = _row(engine, filing_id)
    assert row["stage"] == "analyzing"
    assert row["started_at"] == started_at
    assert row["elapsed_seconds"] == pytest.approx(30.0, abs=1e-3)


@pytest.mark.parametrize("starts_run", [False, True])
def test_the_first_write_inserts_the_row(engine, filing_id, starts_run):
    _write(engine, filing_id, "fetching", starts_run=starts_run)
    row = _row(engine, filing_id)
    assert row["stage"] == "fetching"
    assert row["started_at"] == row["updated_at"] == NOW
    assert row["elapsed_seconds"] == 0.0
    assert row["error"] is None and row["section_coverage"] is None
    with _session(engine) as db:
        # SQL NULL, as before E214, and not JSON null, which the ORM reads as None too.
        assert db.query(SummaryGenerationProgress).filter(
            SummaryGenerationProgress.filing_id == filing_id,
            SummaryGenerationProgress.section_coverage.is_(None)).count() == 1


def test_a_later_write_keeps_the_start_counts_from_it_and_clears_an_error(engine, filing_id):
    coverage = {"business": "full"}
    started_at = _seed(engine, filing_id, age_seconds=30, error="an earlier failure", section_coverage=coverage)
    _write(engine, filing_id, "analyzing")
    row = _row(engine, filing_id)
    assert row["stage"] == "analyzing"
    assert row["started_at"] == started_at
    assert row["updated_at"] == NOW
    assert row["elapsed_seconds"] == pytest.approx(30.0, abs=1e-3)
    assert row["error"] is None
    assert row["section_coverage"] == coverage  # kept: this write names none


def test_a_write_records_its_error_and_replaces_the_coverage_it_names(engine, filing_id):
    _seed(engine, filing_id, age_seconds=30, section_coverage={"business": "full"})
    _write(engine, filing_id, "error", error="Pipeline timeout", section_coverage={"business": "partial"})
    row = _row(engine, filing_id)
    assert row["stage"] == "error"
    assert row["error"] == "Pipeline timeout"
    assert row["section_coverage"] == {"business": "partial"}


def test_a_runs_first_write_restarts_the_clock_on_an_earlier_runs_row(engine, filing_id):
    coverage = {"business": "full"}
    _seed(engine, filing_id, age_seconds=7200, stage="error", error="Pipeline timeout", section_coverage=coverage)
    _write(engine, filing_id, "fetching", starts_run=True)
    row = _row(engine, filing_id)
    assert row["stage"] == "fetching"
    assert row["started_at"] == row["updated_at"] == NOW
    assert row["elapsed_seconds"] == 0.0
    assert row["error"] is None
    assert row["section_coverage"] == coverage  # kept: this write names none


@pytest.fixture
def pipeline_tables():
    """The test database the one orchestrator runs on, as its anchors set it up."""
    Base.metadata.create_all(bind=app_engine)
    reset_inflight()
    yield
    reset_inflight()


@pytest.mark.asyncio
@pytest.mark.parametrize("forced", [False, True], ids=["unforced", "forced"])
async def test_a_run_onto_an_earlier_runs_error_row_counts_from_its_own_start(pipeline_tables, forced):
    """An unforced run (a retry after an error) and a forced one (as the unready summary's regeneration runs) each end
    with the row counting from their own start, not from the earlier run's two hours before."""
    filing_id = seed_company_filing()
    earlier = NOW - timedelta(hours=2)
    with SessionLocal() as db:
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage="error", error="Pipeline timeout", started_at=earlier,
                                         updated_at=earlier + timedelta(seconds=10), elapsed_seconds=10.0))
        db.commit()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)):
        events = [event async for event in summary_pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
            force_regenerate=forced, replace_unready_only=forced)]
    assert events[-1]["type"] == "complete", events[-1]
    with SessionLocal() as db:
        row = db.get(SummaryGenerationProgress, filing_id)
        assert (row.stage, _aware(row.started_at), row.elapsed_seconds, row.error) == ("completed", NOW, 0.0, None)

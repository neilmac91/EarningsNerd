"""The Alpha Vantage ingest reads its rows' existing events in chunked queries, not one SELECT per row.

A daily calendar CSV carries ~6k rows, and the per-row lookup cost one round trip to Cloud SQL each
(~1.5 ms, about 9 s of the job's DB phase). The first test fails if the lookups go back to one per
row. The others pin what the loop around the lookup must keep doing: an in-file duplicate updates the
row it just inserted, each insert is flushed at once, and a row that cannot be read stops the pass at
that row, with the rows before it applied.
"""
import math
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.database import SessionLocal, engine
from app.models import Base, EarningsEvent
from app.models.earnings import (
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    STATUS_CONFIRMED,
    STATUS_ESTIMATED,
)
from app.services import earnings_calendar_service as svc

TODAY = date(2026, 7, 1)
FPE = date(2026, 6, 30)
PREFIX = "LKP"


@pytest.fixture(scope="module", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _clean():
    _clear()
    yield
    _clear()


def _clear():
    with SessionLocal() as db:
        db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%")).delete(synchronize_session=False)
        db.commit()


def _row(i, report_date, fpe=FPE):
    symbol = f"{PREFIX}{i:04d}"
    return SimpleNamespace(symbol=symbol, company_name=f"{symbol} Inc", report_date=report_date,
                           fiscal_period_end=fpe, eps_estimate=1.5, currency="USD", event_time="amc")


@contextmanager
def _event_selects():
    """Counts the SELECTs that read earnings_events while the block runs."""
    seen = []

    def count(conn, cursor, statement, parameters, context, executemany):
        text = statement.lstrip().upper()
        if text.startswith("SELECT") and "EARNINGS_EVENTS" in text:
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield lambda: len(seen)
    finally:
        event.remove(engine, "before_cursor_execute", count)


@pytest.mark.requires_db
@pytest.mark.parametrize("n_rows", [10, 1200])
def test_existing_events_are_read_in_chunks_whatever_the_row_count(n_rows):
    """Half the rows update a stored estimate, half insert, one is confirmed (touched, not moved):
    the reads stay at one query per chunk of tickers, and every row lands as before."""
    with SessionLocal() as db:
        for i in range(0, n_rows, 2):
            db.add(EarningsEvent(
                ticker=f"{PREFIX}{i:04d}", fiscal_period_end=FPE, event_date=TODAY + timedelta(days=10),
                status=STATUS_CONFIRMED if i == 0 else STATUS_ESTIMATED, confidence=CONFIDENCE_MEDIUM,
                source=SOURCE_ALPHA_VANTAGE,
            ))
        db.commit()
    rows = [_row(i, TODAY + timedelta(days=12)) for i in range(n_rows)]

    with SessionLocal() as db, _event_selects() as selects:
        upserted = svc.ingest_alpha_vantage(db, rows, today=TODAY)
        db.commit()
        reads = selects()

    assert reads == math.ceil(n_rows / svc._EVENT_LOOKUP_CHUNK)
    assert upserted == n_rows - 1  # the confirmed row is only marked seen
    with SessionLocal() as db:
        stored = {e.ticker: e for e in db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%"))}
    assert len(stored) == n_rows
    confirmed = stored[f"{PREFIX}0000"]
    assert (confirmed.status, confirmed.event_date) == (STATUS_CONFIRMED, TODAY + timedelta(days=10))
    moved = stored[f"{PREFIX}0002"]
    assert (moved.event_date, moved.prior_event_date) == (TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    inserted = stored[f"{PREFIX}0001"]
    assert (inserted.status, inserted.event_date, inserted.prior_event_date) == (
        STATUS_ESTIMATED, TODAY + timedelta(days=12), None)


@pytest.mark.requires_db
def test_an_in_file_duplicate_updates_the_row_it_just_inserted():
    rows = [_row(1, TODAY + timedelta(days=5)), _row(1, TODAY + timedelta(days=8))]
    with SessionLocal() as db:
        assert svc.ingest_alpha_vantage(db, rows, today=TODAY) == 2
        db.commit()
    with SessionLocal() as db:
        (only,) = db.query(EarningsEvent).filter(EarningsEvent.ticker == f"{PREFIX}0001").all()
    assert (only.event_date, only.prior_event_date) == (TODAY + timedelta(days=8), TODAY + timedelta(days=5))


@pytest.mark.requires_db
def test_a_row_that_cannot_be_read_stops_the_pass_there_with_earlier_inserts_flushed():
    """The bad row raises at the same point as before (comparing its date), after the row before it
    was inserted and flushed, and before the row after it is read."""
    rows = [_row(1, TODAY + timedelta(days=5)), _row(2, "2026-07-09"), _row(3, TODAY + timedelta(days=6))]
    db = SessionLocal()
    try:
        with pytest.raises(TypeError):
            svc.ingest_alpha_vantage(db, rows, today=TODAY)
        # autoflush is off: this query sees only what the ingest flushed.
        flushed = {e.ticker for e in db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%"))}
        assert flushed == {f"{PREFIX}0001"}
        assert not db.new
    finally:
        db.rollback()
        db.close()

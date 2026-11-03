"""The Alpha Vantage ingest reads its rows' existing events in chunked queries, not one SELECT per row.

A daily calendar CSV carries ~6k rows, and the per-row lookup cost one round trip to Cloud SQL each
(~1.5 ms, about 9 s of the job's DB phase). The first test fails if the lookups go back to one per
row. The others pin what the prefetch and the loop around the lookup must keep doing:
- a ticker's other stored periods, which the prefetch also loads, are never the row a CSV row updates;
- stored rows under each of the file's periods are all found;
- with the index filter on, a stored member row is updated and a non-member row is left alone;
- rows given as a one-shot iterator are all ingested, though the prefetch walks them first;
- an in-file duplicate updates the row it just inserted;
- each insert is flushed at once, and a row that cannot be read stops the pass at that row, with the
  rows before it applied.
"""
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select

from app.database import SessionLocal, engine
from app.models import Base, EarningsEvent
from app.models.earnings import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    SOURCE_EDGAR_8K,
    SOURCE_PATTERN,
    STATUS_CONFIRMED,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
)
from app.services import earnings_calendar_service as svc

TODAY = date(2026, 7, 1)
FPE = date(2026, 6, 30)
FPE_PREV = date(2026, 3, 31)
FPE_NEXT = date(2026, 9, 30)
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
    """Most rows update a stored estimate, one in ten inserts, one is confirmed (touched, not moved):
    the reads stay at one query per chunk of tickers, and every row lands as before. Every chunk's
    first and last ticker (LKP0000, 0499, 0500, 0999, 1000, 1199) is stored, so a chunk that drops
    an edge ticker leaves a stored key out of the map, and the pass's second insert for it fails."""
    with SessionLocal() as db:
        for i in (i for i in range(n_rows) if i % 10 != 3):
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

    # Literal counts, not ones derived from the chunk constant: a chunk under 400 tickers (down to
    # one ticker per query) changes the 1,200-row count and fails here.
    assert reads == {10: 1, 1200: 3}[n_rows]
    assert upserted == n_rows - 1  # the confirmed row is only marked seen
    with SessionLocal() as db:
        stored = {e.ticker: e for e in db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%"))}
    assert len(stored) == n_rows
    confirmed = stored[f"{PREFIX}0000"]
    assert (confirmed.status, confirmed.event_date) == (STATUS_CONFIRMED, TODAY + timedelta(days=10))
    moved = stored[f"{PREFIX}0002"]
    assert (moved.event_date, moved.prior_event_date) == (TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    inserted = stored[f"{PREFIX}0003"]
    assert (inserted.status, inserted.event_date, inserted.prior_event_date) == (
        STATUS_ESTIMATED, TODAY + timedelta(days=12), None)


@pytest.mark.requires_db
def test_rows_given_as_a_one_shot_iterator_are_all_ingested():
    """The prefetch and the pass each walk the rows, so the ingest takes its own list of them first;
    a generator read by the prefetch alone would leave the pass nothing to upsert."""
    with SessionLocal() as db:
        db.add(EarningsEvent(
            ticker=f"{PREFIX}0001", fiscal_period_end=FPE, event_date=TODAY + timedelta(days=10),
            status=STATUS_ESTIMATED, confidence=CONFIDENCE_MEDIUM, source=SOURCE_ALPHA_VANTAGE,
        ))
        db.commit()
    rows = (_row(i, TODAY + timedelta(days=12)) for i in (1, 2))

    with SessionLocal() as db:
        assert svc.ingest_alpha_vantage(db, rows, today=TODAY) == 2
        db.commit()

    after = _snapshot()
    assert after[(f"{PREFIX}0001", FPE)][1:3] == (TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    assert after[(f"{PREFIX}0002", FPE)][1] == TODAY + timedelta(days=12)


def _store(ticker, fpe, status, event_date, source=SOURCE_ALPHA_VANTAGE):
    return EarningsEvent(
        ticker=ticker, fiscal_period_end=fpe, event_date=event_date, status=status,
        confidence=CONFIDENCE_HIGH if status == STATUS_REPORTED else CONFIDENCE_MEDIUM, source=source,
    )


def _snapshot():
    with SessionLocal() as db:
        return {
            (e.ticker, e.fiscal_period_end): (e.status, e.event_date, e.prior_event_date, e.source, e.last_seen_at)
            for e in db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%"))
        }


@pytest.mark.requires_db
def test_a_tickers_other_stored_period_is_never_the_row_its_csv_row_updates():
    """The IN pair loads a ticker's events for every period in the file, so LKP0001's reported Q1 row
    and LKP0003's pattern Q3 row are loaded beside the Q2 rows their CSV rows update (LKP0002's and
    LKP0004's rows put Q1 and Q3 in the file). Only the map's two-part key keeps them out of the
    lookups. LKP0001 stores its other row first and LKP0003 second, so a map keyed on the ticker alone
    fails one of them whichever of a ticker's rows it keeps: a Q2 update lands on the Q3 row, or is
    skipped against the reported Q1 row."""
    with SessionLocal() as db:
        db.add_all([
            _store(f"{PREFIX}0001", FPE_PREV, STATUS_REPORTED, TODAY - timedelta(days=60), SOURCE_EDGAR_8K),
            _store(f"{PREFIX}0001", FPE, STATUS_ESTIMATED, TODAY + timedelta(days=10)),
        ])
        db.commit()
        db.add_all([
            _store(f"{PREFIX}0003", FPE, STATUS_ESTIMATED, TODAY + timedelta(days=10)),
            _store(f"{PREFIX}0003", FPE_NEXT, STATUS_ESTIMATED, TODAY + timedelta(days=90), SOURCE_PATTERN),
        ])
        db.commit()
    before = _snapshot()
    rows = [
        _row(1, TODAY + timedelta(days=12)),
        _row(3, TODAY + timedelta(days=12)),
        _row(2, TODAY + timedelta(days=5), fpe=FPE_PREV),
        _row(4, TODAY + timedelta(days=70), fpe=FPE_NEXT),
    ]

    with SessionLocal() as db:
        assert svc.ingest_alpha_vantage(db, rows, today=TODAY) == 4
        db.commit()

    after = _snapshot()
    for ticker in (f"{PREFIX}0001", f"{PREFIX}0003"):
        status, event_date, prior, _, _ = after[(ticker, FPE)]
        assert (status, event_date, prior) == (STATUS_ESTIMATED, TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    # The other periods' rows are exactly as stored: not moved, not re-sourced, not even marked seen.
    for key in ((f"{PREFIX}0001", FPE_PREV), (f"{PREFIX}0003", FPE_NEXT)):
        assert after[key] == before[key]
    assert after[(f"{PREFIX}0002", FPE_PREV)][1] == TODAY + timedelta(days=5)
    assert after[(f"{PREFIX}0004", FPE_NEXT)][1] == TODAY + timedelta(days=70)


@pytest.mark.requires_db
def test_stored_rows_under_each_of_the_files_periods_are_all_found():
    """A real AV file spans several fiscal periods. The prefetch's one IN list of periods must hold
    every row's period: a stored row under a period missing from it is left out of the map, and the
    pass inserts it a second time."""
    with SessionLocal() as db:
        db.add_all([
            _store(f"{PREFIX}0001", FPE, STATUS_ESTIMATED, TODAY + timedelta(days=10)),
            _store(f"{PREFIX}0002", FPE_PREV, STATUS_ESTIMATED, TODAY + timedelta(days=10)),
            _store(f"{PREFIX}0003", FPE_NEXT, STATUS_ESTIMATED, TODAY + timedelta(days=10)),
        ])
        db.commit()
    rows = [
        _row(1, TODAY + timedelta(days=12)),
        _row(2, TODAY + timedelta(days=12), fpe=FPE_PREV),
        _row(3, TODAY + timedelta(days=12), fpe=FPE_NEXT),
    ]

    with SessionLocal() as db, _event_selects() as selects:
        assert svc.ingest_alpha_vantage(db, rows, today=TODAY) == 3
        db.commit()
        assert selects() == 1  # one chunk of tickers, every period in its one IN list

    after = _snapshot()
    for key in ((f"{PREFIX}0001", FPE), (f"{PREFIX}0002", FPE_PREV), (f"{PREFIX}0003", FPE_NEXT)):
        status, event_date, prior, _, _ = after[key]
        assert (status, event_date, prior) == (STATUS_ESTIMATED, TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    assert len(after) == 3


@pytest.mark.requires_db
def test_with_the_index_filter_on_a_stored_member_row_is_updated_and_a_non_member_is_left_alone(monkeypatch):
    """The worker runs the refresh with the filter on. The prefetch reads rows through the same
    _ingest_key as the pass, so a stored member row is in the map: if it were not, the pass would
    insert a second row for its key and the flush would fail on uq_earnings_events_ticker_period."""
    from app.config import settings
    from app.services import index_membership_service as idx

    members = {f"{PREFIX}0001", f"{PREFIX}0003"}
    monkeypatch.setattr(idx, "_MEMBER_TICKERS", frozenset(members))
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)
    with SessionLocal() as db:
        db.add_all([_store(f"{PREFIX}{i:04d}", FPE, STATUS_ESTIMATED, TODAY + timedelta(days=10)) for i in (1, 2, 3)])
        db.commit()
    before = _snapshot()
    rows = [_row(i, TODAY + timedelta(days=12)) for i in (1, 2, 3, 4)]

    stats = svc.RefreshStats()
    with SessionLocal() as db:
        assert svc.ingest_alpha_vantage(db, rows, today=TODAY, stats=stats) == 2
        db.commit()

    assert stats.skipped_non_member == 2
    after = _snapshot()
    for i in (1, 3):
        status, event_date, prior, _, _ = after[(f"{PREFIX}{i:04d}", FPE)]
        assert (status, event_date, prior) == (STATUS_ESTIMATED, TODAY + timedelta(days=12), TODAY + timedelta(days=10))
    assert after[(f"{PREFIX}0002", FPE)] == before[(f"{PREFIX}0002", FPE)]
    assert (f"{PREFIX}0004", FPE) not in after


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
    """The bad row raises at the same point as before (comparing its date): after LKP0000's stored row
    was updated and LKP0001 inserted, the insert's flush writing both, and before the row after it is
    read. LKP0000 is stored, so a prefetch that gave up at the bad row would leave it out of the map
    and the pass would fail earlier, inserting it a second time."""
    with SessionLocal() as db:
        db.add(_store(f"{PREFIX}0000", FPE, STATUS_ESTIMATED, TODAY + timedelta(days=10)))
        db.commit()
    rows = [
        _row(0, TODAY + timedelta(days=4)),
        _row(1, TODAY + timedelta(days=5)),
        _row(2, "2026-07-09"),
        _row(3, TODAY + timedelta(days=6)),
    ]
    db = SessionLocal()
    try:
        with pytest.raises(TypeError):
            svc.ingest_alpha_vantage(db, rows, today=TODAY)
        # autoflush is off, and a column select bypasses the identity map: this reads only what the
        # ingest flushed.
        flushed = dict(db.execute(
            select(EarningsEvent.ticker, EarningsEvent.event_date).where(EarningsEvent.ticker.like(f"{PREFIX}%"))
        ).all())
        assert flushed == {f"{PREFIX}0000": TODAY + timedelta(days=4), f"{PREFIX}0001": TODAY + timedelta(days=5)}
        assert not db.new
    finally:
        db.rollback()
        db.close()

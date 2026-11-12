"""The refresh's later steps read every change its earlier steps made, whatever the file's order (E306).

``SessionLocal`` runs with autoflush off, so a query or a bulk UPDATE reads the database, not the session's pending
changes. The Alpha Vantage pass flushed only at an insert, so an update after the file's last insert was still
pending when two later steps read the table:
- the stale-estimate downgrade, a bulk UPDATE, read such a row at its old past date and set it low, though the file
  had just moved it into the future, while a neighbour that an insert flushed stayed medium;
- the EDGAR pass's attach query looked for such a row at its old date, so a 2.02 hit for it found no row and was
  skipped, and the downgrade then set the row low.

The downgrade also read the EDGAR pass's pending flips: a stale row the sweep reported in the same run was counted in
``stale_downgraded`` and written low before the commit wrote it high. Each of the two steps now flushes before it reads,
so they read every change also when the Alpha Vantage pass stopped at a row it could not read.

Each test runs the real ``run_refresh`` with stubbed providers, in every order of the file's rows that matters, and
expects one outcome. ``stale_downgraded`` counts the whole table, so each test counts the other stale rows the
database holds first and expects exactly those.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.database import SessionLocal, engine
from app.models import Base, EarningsEvent
from app.models.earnings import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
)
from app.services import earnings_calendar_service as svc

TODAY = date(2026, 7, 1)
PREFIX = "RRD"


@pytest.fixture(scope="module", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(svc, "today_eastern", lambda: TODAY)
    _clear()
    yield
    _clear()


def _clear():
    with SessionLocal() as db:
        db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%")).delete(synchronize_session=False)
        db.commit()


def _store(*events: tuple[str, date, date]) -> None:
    """Open estimates at medium confidence, each ``(ticker, fiscal_period_end, event_date)``."""
    with SessionLocal() as db:
        db.add_all(
            EarningsEvent(
                ticker=ticker, company_name=f"{ticker} Inc", fiscal_period_end=fpe, event_date=event_date,
                status=STATUS_ESTIMATED, confidence=CONFIDENCE_MEDIUM, source=SOURCE_ALPHA_VANTAGE,
            )
            for ticker, fpe, event_date in events
        )
        db.commit()


def _csv(ticker: str, fpe: date, report_date: date) -> SimpleNamespace:
    return SimpleNamespace(symbol=ticker, company_name=f"{ticker} Inc", report_date=report_date,
                           fiscal_period_end=fpe, eps_estimate=1.0, currency="USD", event_time="amc")


def _hit(ticker: str, filed: date, accession: str) -> SimpleNamespace:
    return SimpleNamespace(items=["2.02"], ticker=ticker, filed_date=filed, accession_no=accession,
                           acceptance_datetime=None, cik="0000000001")


class _AlphaVantage:
    def __init__(self, rows):
        self.rows = rows

    async def fetch_earnings_calendar(self):
        return list(self.rows)


class _Efts:
    def __init__(self, hits):
        self.hits = hits

    async def search(self, **kwargs):
        return SimpleNamespace(hits=list(self.hits), total=len(self.hits))


def _other_stale_rows() -> int:
    """Stale estimates other tests left in this worker's database, which the downgrade also counts."""
    with SessionLocal() as db:
        return db.query(EarningsEvent).filter(
            ~EarningsEvent.ticker.like(f"{PREFIX}%"),
            EarningsEvent.status == STATUS_ESTIMATED,
            EarningsEvent.event_date < TODAY,
            EarningsEvent.confidence != CONFIDENCE_LOW,
        ).count()


async def _refresh(rows, hits=()):
    """Run the refresh; return its stats and this module's rows as ``ticker: (status, confidence, event_date)``."""
    with SessionLocal() as db:
        stats = await svc.run_refresh(db, av_client=_AlphaVantage(rows), efts_client=_Efts(hits))
    with SessionLocal() as db:
        events = {
            event.ticker: (event.status, event.confidence, event.event_date)
            for event in db.query(EarningsEvent).filter(EarningsEvent.ticker.like(f"{PREFIX}%"))
        }
    return stats, events


@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["A N B", "N A B", "A B N"])
async def test_the_downgrade_reads_every_date_the_file_moved(order):
    """A and B are stale estimates the file moves into the future; N is a new row. Before E306 the order decided
    their confidence: in "A N B" the downgrade read B at its old date and set it low while A stayed medium, and in
    "N A B" it set both low. Both now stay medium in every order, and neither is counted stale."""
    fpe, stale, moved = date(2026, 6, 30), date(2026, 6, 20), date(2026, 7, 20)
    _store((f"{PREFIX}A", fpe, stale), (f"{PREFIX}B", fpe, stale))
    rows = {key: _csv(f"{PREFIX}{key}", fpe, moved) for key in "ANB"}
    others = _other_stale_rows()

    stats, events = await _refresh([rows[key] for key in order.split()])

    assert events == {f"{PREFIX}{key}": (STATUS_ESTIMATED, CONFIDENCE_MEDIUM, moved) for key in "ANB"}
    assert (stats.av_upserted, stats.stale_downgraded, stats.source_errors) == (3, others, 0)


@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["N C", "C N"])
async def test_a_2_02_hit_finds_the_row_the_file_just_moved(order):
    """C's stored date (1 March) is more than 100 days before the 8-K, outside the attach window, and its fiscal
    quarter ends in May, not on the calendar quarter-end the fallback tries, so only the file's new date (2 July)
    lets the hit find it. Before E306, in "N C" the attach query read the old date and skipped the hit as having no
    prior row, and the downgrade then set C low. Now the hit reports C in both orders."""
    fpe, stored, moved, filed = date(2026, 5, 31), date(2026, 3, 1), date(2026, 7, 2), date(2026, 7, 1)
    _store((f"{PREFIX}C", fpe, stored))
    rows = {"C": _csv(f"{PREFIX}C", fpe, moved), "N": _csv(f"{PREFIX}N", date(2026, 6, 30), date(2026, 7, 20))}

    stats, events = await _refresh([rows[key] for key in order.split()], [_hit(f"{PREFIX}C", filed, "0000000001-26-000001")])

    assert events == {
        f"{PREFIX}C": (STATUS_REPORTED, CONFIDENCE_HIGH, filed),
        f"{PREFIX}N": (STATUS_ESTIMATED, CONFIDENCE_MEDIUM, date(2026, 7, 20)),
    }
    assert (stats.edgar_reported, stats.skipped_no_prior, stats.source_errors) == (1, 0, 0)


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_a_stale_row_the_sweep_reports_is_not_counted_stale():
    """D's estimate (29 June) has passed, and an 8-K filed the next day reports it. Before E306 the downgrade read
    the flip still pending, counted D in ``stale_downgraded`` and wrote it low before the commit wrote it high. It
    now reads the flip: D is not counted, and ends reported."""
    _store((f"{PREFIX}D", date(2026, 3, 31), date(2026, 6, 29)))
    others = _other_stale_rows()

    stats, events = await _refresh([], [_hit(f"{PREFIX}D", date(2026, 6, 30), "0000000001-26-000002")])

    assert events == {f"{PREFIX}D": (STATUS_REPORTED, CONFIDENCE_HIGH, date(2026, 6, 30))}
    assert (stats.edgar_reported, stats.stale_downgraded, stats.source_errors) == (1, others, 0)


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_a_2_02_hit_finds_the_moved_row_when_the_pass_stops_at_a_row_it_cannot_read():
    """The pass raises at a row whose date is text (#1986's case), after it moved C into the attach window and before
    the end of the file; the refresh logs the error and goes on. The EDGAR pass flushes before its query, so the hit
    still finds C at its new date and reports it."""
    fpe, stored, moved, filed = date(2026, 5, 31), date(2026, 3, 1), date(2026, 7, 2), date(2026, 7, 1)
    _store((f"{PREFIX}C", fpe, stored))
    rows = [_csv(f"{PREFIX}N", date(2026, 6, 30), date(2026, 7, 20)), _csv(f"{PREFIX}C", fpe, moved),
            _csv(f"{PREFIX}X", date(2026, 6, 30), "2026-07-09")]

    stats, events = await _refresh(rows, [_hit(f"{PREFIX}C", filed, "0000000001-26-000003")])

    assert events == {
        f"{PREFIX}C": (STATUS_REPORTED, CONFIDENCE_HIGH, filed),
        f"{PREFIX}N": (STATUS_ESTIMATED, CONFIDENCE_MEDIUM, date(2026, 7, 20)),
    }
    assert (stats.edgar_reported, stats.skipped_no_prior, stats.source_errors) == (1, 0, 1)

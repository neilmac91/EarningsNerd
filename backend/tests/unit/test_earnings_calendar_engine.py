"""Earnings-calendar engine: pure helpers + ingest/reconciliation over earnings_events."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import earnings_calendar_service as svc
from app.models.earnings import (
    SOURCE_ALPHA_VANTAGE,
    SOURCE_EDGAR_8K,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


# ---- pure helpers ---------------------------------------------------------

def test_infer_event_time_dst_safe():
    # 2026-07-30 is EDT (UTC-4): 13:00 UTC = 09:00 ET (before 09:30) => bmo.
    assert svc.infer_event_time(datetime(2026, 7, 30, 13, 0, tzinfo=timezone.utc)) == "bmo"
    # 20:30 UTC = 16:30 ET (after close) => amc.
    assert svc.infer_event_time(datetime(2026, 7, 30, 20, 30, tzinfo=timezone.utc)) == "amc"
    # 2026-01-29 is EST (UTC-5): 14:00 UTC = 09:00 ET => bmo (would be wrong with a fixed UTC cutoff).
    assert svc.infer_event_time(datetime(2026, 1, 29, 14, 0, tzinfo=timezone.utc)) == "bmo"
    # 21:30 UTC = 16:30 ET in winter => amc.
    assert svc.infer_event_time(datetime(2026, 1, 29, 21, 30, tzinfo=timezone.utc)) == "amc"
    # Midday => dmh; None in => None out.
    assert svc.infer_event_time(datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc)) == "dmh"
    assert svc.infer_event_time(None) is None


def test_most_recent_quarter_end():
    assert svc.most_recent_quarter_end(date(2026, 7, 30)) == date(2026, 6, 30)
    assert svc.most_recent_quarter_end(date(2026, 1, 5)) == date(2025, 12, 31)
    assert svc.most_recent_quarter_end(date(2026, 3, 31)) == date(2026, 3, 31)


def test_anticipation_score_ranks_curated_and_watch_count():
    curated = svc.compute_anticipation_score(is_curated=True, watch_count=0, has_estimate=False)
    watched = svc.compute_anticipation_score(is_curated=False, watch_count=50, has_estimate=True)
    noise = svc.compute_anticipation_score(is_curated=False, watch_count=0, has_estimate=False)
    assert curated > watched > noise
    assert noise == 0.0
    # More watchers => higher score.
    assert (
        svc.compute_anticipation_score(is_curated=False, watch_count=100, has_estimate=False)
        > svc.compute_anticipation_score(is_curated=False, watch_count=10, has_estimate=False)
    )


# ---- ingest + reconciliation ---------------------------------------------

def _clear(*tickers):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.query(EarningsEvent).filter(EarningsEvent.ticker.in_([t.upper() for t in tickers])).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


def _av_row(symbol, report_date, fpe, eps=1.0, time=None):
    return SimpleNamespace(
        symbol=symbol, company_name=f"{symbol} Inc", report_date=report_date,
        fiscal_period_end=fpe, eps_estimate=eps, currency="USD", event_time=time,
    )


@pytest.mark.requires_db
def test_av_ingest_inserts_then_updates_and_tracks_date_change():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("NEWC")
    fpe = date(2026, 6, 30)
    db = SessionLocal()
    n = svc.ingest_alpha_vantage(db, [_av_row("NEWC", date(2026, 7, 20), fpe)])
    db.commit()
    assert n == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "NEWC").one()
    assert ev.status == STATUS_ESTIMATED and ev.source == SOURCE_ALPHA_VANTAGE
    assert ev.event_date == date(2026, 7, 20)

    # A moved date is recorded on the row.
    svc.ingest_alpha_vantage(db, [_av_row("NEWC", date(2026, 7, 22), fpe)])
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "NEWC").one()
    assert ev.event_date == date(2026, 7, 22)
    assert ev.prior_event_date == date(2026, 7, 20)
    assert ev.date_changed_at is not None
    db.close()
    _clear("NEWC")


@pytest.mark.requires_db
def test_reported_is_terminal_and_av_never_overwrites():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("RPTD")
    fpe = date(2026, 3, 31)
    db = SessionLocal()
    # Seed an estimate, then an 8-K reports it.
    svc.ingest_alpha_vantage(db, [_av_row("RPTD", date(2026, 4, 30), fpe, eps=2.0)])
    db.commit()
    hit = SimpleNamespace(
        items=["2.02", "9.01"], ticker="RPTD", filed_date="2026-04-30",
        accession_no="0000320193-26-000050", cik="0000320193", company="RPTD Inc",
        acceptance_datetime="2026-04-30T20:30:00+00:00",
    )
    reported = svc.ingest_edgar_reported(db, [hit])
    db.commit()
    assert reported == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "RPTD").one()
    assert ev.status == STATUS_REPORTED
    assert ev.source == SOURCE_EDGAR_8K
    assert ev.accession_number == "0000320193-26-000050"
    assert ev.event_time == "amc"  # 20:30 UTC = 16:30 EDT

    # A later AV pass must NOT overwrite the reported row.
    svc.ingest_alpha_vantage(db, [_av_row("RPTD", date(2026, 5, 15), fpe, eps=9.9)])
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "RPTD").one()
    assert ev.status == STATUS_REPORTED
    assert ev.event_date == date(2026, 4, 30)  # unchanged
    db.close()
    _clear("RPTD")


@pytest.mark.requires_db
def test_reported_without_prior_estimate_inserts_row():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("FRSH")
    db = SessionLocal()
    hit = SimpleNamespace(
        items=["2.02"], ticker="FRSH", filed_date="2026-07-30",
        accession_no="acc-1", cik="0001", company="Fresh Inc", acceptance_datetime=None,
    )
    reported = svc.ingest_edgar_reported(db, [hit])
    db.commit()
    assert reported == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "FRSH").one()
    assert ev.status == STATUS_REPORTED
    assert ev.fiscal_period_end == date(2026, 6, 30)  # nearest calendar quarter-end
    db.close()
    _clear("FRSH")


@pytest.mark.requires_db
def test_non_2_02_8k_ignored():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("SKIP")
    db = SessionLocal()
    hit = SimpleNamespace(
        items=["5.02"], ticker="SKIP", filed_date="2026-07-30",
        accession_no="acc-x", cik="0002", company="Skip Inc", acceptance_datetime=None,
    )
    reported = svc.ingest_edgar_reported(db, [hit])
    db.commit()
    assert reported == 0
    assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "SKIP").first() is None
    db.close()


@pytest.mark.requires_db
def test_events_in_range_serializes_contract():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("SER")
    db = SessionLocal()
    db.add(EarningsEvent(
        ticker="SER", company_name="Ser Inc", fiscal_period_end=date(2026, 3, 31),
        event_date=date(2026, 7, 15), event_time="bmo", status="estimated",
        confidence="high", eps_estimate=1.25, anticipation_score=42.0, source="alpha_vantage",
    ))
    db.commit()
    out = svc.events_in_range(db, date(2026, 7, 1), date(2026, 7, 31))
    db.close()
    row = next(r for r in out if r["ticker"] == "SER")
    assert row == {
        "ticker": "SER", "company_name": "Ser Inc", "event_date": "2026-07-15",
        "event_time": "bmo", "status": "estimated", "confidence": "high",
        "eps_estimate": 1.25, "eps_actual": None, "anticipation_score": 42.0,
    }
    _clear("SER")

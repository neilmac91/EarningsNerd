"""Earnings-calendar engine: pure helpers + ingest/reconciliation over earnings_events."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import earnings_calendar_service as svc
from app.models.earnings import (
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
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


def test_is_probable_earnings_release_thresholds():
    """The timing guard: earnings releases pass via the quarter-close gap OR the on-estimate delta;
    pre-announcements and interim 2.02s fail both arms."""
    q2 = date(2026, 6, 30)
    # BIIB pre-announcement: filed 7/1 (gap 1), estimate was 7/29 (delta 28) → not a release.
    assert not svc.is_probable_earnings_release(
        date(2026, 7, 1), fiscal_period_end=q2, event_date=date(2026, 7, 29)
    )
    # TSLA delivery numbers: filed 7/2 (gap 2), estimate 7/22 (delta 20) → not a release.
    assert not svc.is_probable_earnings_release(
        date(2026, 7, 2), fiscal_period_end=q2, event_date=date(2026, 7, 22)
    )
    # JPM-style: filed 14 days after quarter close, on the expected day → release.
    assert svc.is_probable_earnings_release(
        date(2026, 7, 14), fiscal_period_end=q2, event_date=date(2026, 7, 14)
    )
    # Delta arm alone: odd fiscal calendar (gap outside window) but filed on the expected day.
    assert svc.is_probable_earnings_release(
        date(2026, 7, 5), fiscal_period_end=q2, event_date=date(2026, 7, 3)
    )
    # Stale leftover row: a late 2.02 more than a quarter past the row's period → not this quarter's release.
    assert not svc.is_probable_earnings_release(
        date(2026, 10, 10), fiscal_period_end=q2, event_date=date(2026, 7, 20)
    )
    # Boundaries: gap 10 and 90 pass; gap 9 with delta 8 fails; delta 7 passes.
    assert svc.is_probable_earnings_release(
        q2 + timedelta(days=10), fiscal_period_end=q2, event_date=q2 + timedelta(days=60)
    )
    assert svc.is_probable_earnings_release(
        q2 + timedelta(days=90), fiscal_period_end=q2, event_date=date(2027, 1, 30)
    )
    assert not svc.is_probable_earnings_release(
        q2 + timedelta(days=9), fiscal_period_end=q2, event_date=q2 + timedelta(days=17)
    )
    assert svc.is_probable_earnings_release(
        q2 + timedelta(days=2), fiscal_period_end=q2, event_date=q2 + timedelta(days=9)
    )


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
    n = svc.ingest_alpha_vantage(db, [_av_row("NEWC", date(2026, 7, 20), fpe)], today=date(2026, 7, 1))
    db.commit()
    assert n == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "NEWC").one()
    assert ev.status == STATUS_ESTIMATED and ev.source == SOURCE_ALPHA_VANTAGE
    assert ev.event_date == date(2026, 7, 20)

    # A moved date is recorded on the row.
    svc.ingest_alpha_vantage(db, [_av_row("NEWC", date(2026, 7, 22), fpe)], today=date(2026, 7, 1))
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
    svc.ingest_alpha_vantage(db, [_av_row("RPTD", date(2026, 4, 30), fpe, eps=2.0)], today=date(2026, 4, 1))
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
    svc.ingest_alpha_vantage(db, [_av_row("RPTD", date(2026, 5, 15), fpe, eps=9.9)], today=date(2026, 5, 1))
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "RPTD").one()
    assert ev.status == STATUS_REPORTED
    assert ev.event_date == date(2026, 4, 30)  # unchanged
    db.close()
    _clear("RPTD")


@pytest.mark.requires_db
def test_no_prior_row_skips_market_sweep_hit():
    """Flip-only sweep: a 2.02 hit with no prior calendar row is skipped, never inserted — the
    item code alone can't establish an earnings event (royalty-trust distribution 8-Ks etc.)."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("FRSH")
    db = SessionLocal()
    hit = SimpleNamespace(
        items=["2.02"], ticker="FRSH", filed_date="2026-07-30",
        accession_no="acc-1", cik="0001", company="Fresh Inc", acceptance_datetime=None,
    )
    stats = svc.RefreshStats()
    reported = svc.ingest_edgar_reported(db, [hit], stats=stats)
    db.commit()
    assert reported == 0
    assert stats.skipped_no_prior == 1
    assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "FRSH").first() is None
    db.close()


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
def test_in_run_duplicate_does_not_break_commit():
    """Regression for the critical ingest bug: an AV row and an EDGAR 8-K that resolve to the same
    (ticker, fiscal_period_end) within ONE un-flushed transaction must not double-INSERT and blow
    up the final commit (SessionLocal is autoflush=False)."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("DUPE")
    db = SessionLocal()
    # AV estimate for Q2 with a far-off date, then a same-day 8-K whose derived quarter-end == the
    # AV row's fiscal_period_end. Without the per-insert flush the EDGAR path can't see the pending
    # AV row and inserts a second (DUPE, 2026-06-30), making commit() raise on the unique constraint.
    svc.ingest_alpha_vantage(db, [_av_row("DUPE", date(2026, 1, 5), date(2026, 6, 30))], today=date(2026, 1, 2))
    hit = SimpleNamespace(
        items=["2.02"], ticker="DUPE", filed_date="2026-07-31",
        accession_no="dupe-acc", cik="0009", company="Dupe Inc", acceptance_datetime=None,
    )
    svc.ingest_edgar_reported(db, [hit])
    db.commit()  # must NOT raise
    rows = db.query(EarningsEvent).filter(EarningsEvent.ticker == "DUPE").all()
    assert len(rows) == 1  # single row, flipped to reported
    assert rows[0].status == STATUS_REPORTED
    db.close()
    _clear("DUPE")


@pytest.mark.requires_db
def test_reported_at_not_fabricated_without_acceptance():
    """When the sweep has no acceptance timestamp, reported_at stays NULL (not the job clock)."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("NOACC")
    db = SessionLocal()
    # Seed the estimate the hit attaches to (the sweep is flip-only): gap 30d passes the guard.
    svc.ingest_alpha_vantage(
        db, [_av_row("NOACC", date(2026, 7, 30), date(2026, 6, 30))], today=date(2026, 7, 1)
    )
    hit = SimpleNamespace(
        items=["2.02"], ticker="NOACC", filed_date="2026-07-30",
        accession_no="noacc", cik="0010", company="NoAcc Inc", acceptance_datetime=None,
    )
    svc.ingest_edgar_reported(db, [hit])
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "NOACC").one()
    assert ev.status == STATUS_REPORTED
    assert ev.reported_at is None  # honest: no fabricated timestamp
    db.close()
    _clear("NOACC")


@pytest.mark.requires_db
def test_av_does_not_overwrite_confirmed():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("CONF")
    db = SessionLocal()
    db.add(EarningsEvent(
        ticker="CONF", company_name="Conf Inc", fiscal_period_end=date(2026, 3, 31),
        event_date=date(2026, 4, 20), status="confirmed", confidence="high",
        source="earnings_whispers",
    ))
    db.commit()
    svc.ingest_alpha_vantage(
        db, [_av_row("CONF", date(2026, 4, 28), date(2026, 3, 31), eps=9.9)], today=date(2026, 4, 1)
    )
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "CONF").one()
    assert ev.status == "confirmed"
    assert ev.event_date == date(2026, 4, 20)  # AV did not overwrite the confirmed date
    assert ev.source == "earnings_whispers"
    db.close()
    _clear("CONF")


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
    out = svc.events_in_range(db, date(2026, 7, 1), date(2026, 7, 31), today=date(2026, 7, 1))
    db.close()
    row = next(r for r in out if r["ticker"] == "SER")
    assert row == {
        "ticker": "SER", "company_name": "Ser Inc", "event_date": "2026-07-15",
        "event_time": "bmo", "status": "estimated", "confidence": "high",
        "eps_estimate": 1.25, "eps_actual": None, "anticipation_score": 42.0,
    }
    _clear("SER")


# ---- timing-plausibility guard on the flip paths ---------------------------

@pytest.mark.requires_db
def test_guard_rejects_preannouncement_flip():
    """The BIIB regression: a 2.02 pre-announcement (gap 1d, delta 28d) must NOT flip the
    estimate — the row keeps its provider date and stays estimated."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("BIIB")
    db = SessionLocal()
    svc.ingest_alpha_vantage(
        db, [_av_row("BIIB", date(2026, 7, 29), date(2026, 6, 30))], today=date(2026, 7, 1)
    )
    hit = SimpleNamespace(
        items=["2.02", "9.01"], ticker="BIIB", filed_date="2026-07-01",
        accession_no="0000875045-26-000068", cik="0000875045", company="BIOGEN INC.",
        acceptance_datetime="2026-07-01T12:00:00+00:00",
    )
    stats = svc.RefreshStats()
    reported = svc.ingest_edgar_reported(db, [hit], stats=stats)
    db.commit()
    assert reported == 0
    assert stats.skipped_non_earnings == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "BIIB").one()
    assert ev.status == STATUS_ESTIMATED
    assert ev.event_date == date(2026, 7, 29)  # provider estimate untouched
    assert ev.source == SOURCE_ALPHA_VANTAGE
    assert ev.accession_number is None
    db.close()
    _clear("BIIB")


@pytest.mark.requires_db
def test_guard_accepts_on_estimate_release_despite_odd_fiscal_gap():
    """The delta arm: filing on the estimated day flips even when the row's fiscal-period gap
    falls outside the reporting window (odd fiscal calendars)."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("ODDF")
    db = SessionLocal()
    db.add(EarningsEvent(
        ticker="ODDF", company_name="Odd Fiscal Inc", fiscal_period_end=date(2026, 5, 2),
        event_date=date(2026, 5, 8), status=STATUS_ESTIMATED, confidence="medium",
        source=SOURCE_ALPHA_VANTAGE,
    ))
    db.commit()
    hit = SimpleNamespace(
        items=["2.02"], ticker="ODDF", filed_date="2026-05-08",
        accession_no="oddf-acc", cik="0011", company="Odd Fiscal Inc", acceptance_datetime=None,
    )
    reported = svc.ingest_edgar_reported(db, [hit])  # gap 6d fails, delta 0d passes
    db.commit()
    assert reported == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "ODDF").one()
    assert ev.status == STATUS_REPORTED
    db.close()
    _clear("ODDF")


@pytest.mark.requires_db
def test_guard_applies_on_dup_fallback_path():
    """A row outside the attach window (stale far-past estimate) reached via the (ticker, fpe)
    fallback still gets the guard: an implausible hit must not flip it."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("GRD2")
    db = SessionLocal()
    db.add(EarningsEvent(
        ticker="GRD2", company_name="Guard Two Inc", fiscal_period_end=date(2026, 6, 30),
        event_date=date(2026, 1, 5), status=STATUS_ESTIMATED, confidence="medium",
        source=SOURCE_ALPHA_VANTAGE,
    ))
    db.commit()
    hit = SimpleNamespace(
        items=["2.02"], ticker="GRD2", filed_date="2026-07-02",
        accession_no="grd2-acc", cik="0012", company="Guard Two Inc", acceptance_datetime=None,
    )
    stats = svc.RefreshStats()
    reported = svc.ingest_edgar_reported(db, [hit], stats=stats)  # gap 2d, delta 178d → reject
    db.commit()
    assert reported == 0
    assert stats.skipped_non_earnings == 1
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "GRD2").one()
    assert ev.status == STATUS_ESTIMATED
    assert ev.event_date == date(2026, 1, 5)
    db.close()
    _clear("GRD2")


# ---- past-date hygiene ------------------------------------------------------

@pytest.mark.requires_db
def test_av_ingest_skips_past_dated_rows():
    """A stale provider snapshot (report_date already behind us) must not create or move rows —
    past-dated estimates are also flip-bait for the sweep's 100-day attach window."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("PAST")
    today = date(2026, 7, 4)
    db = SessionLocal()
    n = svc.ingest_alpha_vantage(db, [_av_row("PAST", date(2026, 7, 3), date(2026, 6, 30))], today=today)
    db.commit()
    assert n == 0
    assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "PAST").first() is None

    # An existing future estimate must not be dragged into the past by a stale snapshot either.
    svc.ingest_alpha_vantage(db, [_av_row("PAST", date(2026, 7, 29), date(2026, 6, 30))], today=today)
    db.commit()
    svc.ingest_alpha_vantage(db, [_av_row("PAST", date(2026, 7, 1), date(2026, 6, 30))], today=today)
    db.commit()
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "PAST").one()
    assert ev.event_date == date(2026, 7, 29)
    # Today's date is NOT past — same-day rows still ingest.
    n = svc.ingest_alpha_vantage(db, [_av_row("PAST", today, date(2026, 6, 30))], today=today)
    assert n == 1
    db.close()
    _clear("PAST")


@pytest.mark.requires_db
def test_events_in_range_past_days_serve_facts_only():
    """Past days show only reported rows; today and the future keep estimates."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("PRPT", "PEST", "TEST", "FEST")
    today = date(2026, 7, 4)
    db = SessionLocal()
    db.add(EarningsEvent(  # reported in the past → shown (fact)
        ticker="PRPT", company_name="x", fiscal_period_end=date(2026, 3, 31),
        event_date=date(2026, 7, 1), status=STATUS_REPORTED, confidence="high", source=SOURCE_EDGAR_8K,
    ))
    db.add(EarningsEvent(  # estimated in the past → hidden (ZCMD-on-7/4 regression)
        ticker="PEST", company_name="x", fiscal_period_end=date(2026, 3, 31),
        event_date=date(2026, 7, 3), status=STATUS_ESTIMATED, confidence="medium", source=SOURCE_ALPHA_VANTAGE,
    ))
    db.add(EarningsEvent(  # estimated today → shown
        ticker="TEST", company_name="x", fiscal_period_end=date(2026, 3, 31),
        event_date=today, status=STATUS_ESTIMATED, confidence="medium", source=SOURCE_ALPHA_VANTAGE,
    ))
    db.add(EarningsEvent(  # estimated in the future → shown
        ticker="FEST", company_name="x", fiscal_period_end=date(2026, 6, 30),
        event_date=date(2026, 7, 10), status=STATUS_ESTIMATED, confidence="medium", source=SOURCE_ALPHA_VANTAGE,
    ))
    db.commit()
    out = svc.events_in_range(db, date(2026, 7, 1), date(2026, 7, 31), today=today)
    db.close()
    tickers = {r["ticker"] for r in out if r["ticker"] in {"PRPT", "PEST", "TEST", "FEST"}}
    assert tickers == {"PRPT", "TEST", "FEST"}
    _clear("PRPT", "PEST", "TEST", "FEST")


@pytest.mark.requires_db
def test_downgrade_stale_estimates():
    """Past-dated estimates drop to low confidence; reported, already-low and future rows are untouched."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    _clear("STL1", "STL2", "STL3", "STL4")
    today = date(2026, 7, 4)
    db = SessionLocal()
    def _row(ticker, event_date, status, confidence):
        return EarningsEvent(
            ticker=ticker, company_name="x", fiscal_period_end=date(2026, 3, 31),
            event_date=event_date, status=status, confidence=confidence, source=SOURCE_ALPHA_VANTAGE,
        )
    db.add(_row("STL1", date(2026, 7, 1), STATUS_ESTIMATED, CONFIDENCE_MEDIUM))  # → low
    db.add(_row("STL2", date(2026, 7, 1), STATUS_ESTIMATED, CONFIDENCE_LOW))     # already low
    db.add(_row("STL3", date(2026, 7, 1), STATUS_REPORTED, "high"))              # fact — untouched
    db.add(_row("STL4", date(2026, 7, 10), STATUS_ESTIMATED, CONFIDENCE_MEDIUM)) # future — untouched
    db.commit()
    changed = svc.downgrade_stale_estimates(db, today=today)
    db.commit()
    assert changed == 1
    by_ticker = {
        ev.ticker: ev
        for ev in db.query(EarningsEvent).filter(
            EarningsEvent.ticker.in_(["STL1", "STL2", "STL3", "STL4"])
        )
    }
    assert by_ticker["STL1"].confidence == CONFIDENCE_LOW
    assert by_ticker["STL2"].confidence == CONFIDENCE_LOW
    assert by_ticker["STL3"].confidence == "high"
    assert by_ticker["STL4"].confidence == CONFIDENCE_MEDIUM
    db.close()
    _clear("STL1", "STL2", "STL3", "STL4")


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_run_refresh_sweep_window_override_and_new_stats():
    """--sweep-from/--sweep-to reach the EFTS query; stats carries the new counters; the stale
    downgrade runs inside the refresh."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    class _AVStub:
        async def fetch_earnings_calendar(self):
            return []

    class _EftsStub:
        def __init__(self):
            self.calls = []

        async def search(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(hits=[], total=0)

    _clear("RSTL")
    db = SessionLocal()
    db.add(EarningsEvent(  # stale estimate: fixed past date, downgraded by the refresh
        ticker="RSTL", company_name="x", fiscal_period_end=date(2025, 12, 31),
        event_date=date(2026, 1, 15), status=STATUS_ESTIMATED, confidence=CONFIDENCE_MEDIUM,
        source=SOURCE_ALPHA_VANTAGE,
    ))
    db.commit()

    efts = _EftsStub()
    stats = await svc.run_refresh(
        db, av_client=_AVStub(), efts_client=efts,
        sweep_from=date(2026, 6, 28), sweep_to=date(2026, 7, 4),
    )
    assert efts.calls[0]["start_date"] == "2026-06-28"
    assert efts.calls[0]["end_date"] == "2026-07-04"
    d = stats.as_dict()
    assert {"skipped_non_earnings", "skipped_no_prior", "stale_downgraded"} <= set(d)
    assert stats.stale_downgraded >= 1
    assert stats.commit_failed is False
    ev = db.query(EarningsEvent).filter(EarningsEvent.ticker == "RSTL").one()
    assert ev.confidence == CONFIDENCE_LOW

    # Default window: trailing 2 ET days.
    await svc.run_refresh(db, av_client=_AVStub(), efts_client=efts)
    today = svc.today_eastern()
    assert efts.calls[-1]["start_date"] == (today - timedelta(days=2)).isoformat()
    assert efts.calls[-1]["end_date"] == today.isoformat()
    db.close()
    _clear("RSTL")

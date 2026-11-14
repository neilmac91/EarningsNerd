"""The insider endpoint's read of the stored Form 4 trades (ADR 0009): app/services/insider_service.py.

A real SQLite database and no SEC: the read makes no request (the conftest's network gate would fail one). The
scan that fills the store is tests/unit/test_insider_scan_service.py; the route is tests/unit/test_insiders_route.py.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Company
from app.models.insider import InsiderFiling, InsiderScan, InsiderTransaction
from app.services import insider_scan_service as scan_service
from app.services.insider_service import read_insider_activity

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
CIK = "320193"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Company(cik="0000320193", ticker="AAPL", name="Apple Inc."))
        session.commit()
        yield session
    engine.dispose()


def trade(db, n, code, shares, price, days_ago, *, plan=False, cik=CIK):
    day = NOW.date() - timedelta(days=days_ago)
    db.add(InsiderTransaction(
        accession=f"0000320193-26-{n:06d}", ordinal=0, issuer_cik=cik, insider_name=f"Insider {n}",
        insider_title="Director", is_director=True, is_officer=False, is_ten_pct_owner=False, ticker="AAPL",
        transaction_date=day, transaction_code=code, transaction_label="Purchase" if code == "P" else "Sale",
        shares=shares, price=price, value=shares * price, acquired_disposed="A" if code == "P" else "D",
        is_10b5_1=plan, filed_date=day + timedelta(days=1), created_at=NOW,
    ))


def complete_scan(db, *, cik=CIK, listed_ago=timedelta(minutes=5)):
    db.add(InsiderScan(issuer_cik=cik, status="idle", pauses=0, steps=1, last_listed_at=NOW - listed_ago,
                       created_at=NOW - timedelta(hours=1), updated_at=NOW - timedelta(minutes=5)))
    db.add(InsiderFiling(accession="0000320193-26-000001", issuer_cik=cik, filed_date=date(2026, 9, 1), status="ok",
                         created_at=NOW, updated_at=NOW))


def test_the_stored_trades_are_summarised_over_the_window_and_listed_newest_first(db):
    trade(db, 1, "P", 100, 10.0, days_ago=5)
    trade(db, 2, "S", 400, 12.0, days_ago=2, plan=True)
    trade(db, 3, "S", 50, 11.0, days_ago=40)
    trade(db, 4, "P", 999, 1.0, days_ago=200)             # outside the 90-day window
    trade(db, 5, "S", 777, 1.0, days_ago=1, cik="555")    # another issuer's
    complete_scan(db)
    db.commit()

    activity = read_insider_activity(db, "aapl ", now=NOW)

    assert (activity["ticker"], activity["company_name"], activity["cik"], activity["window_days"]) == ("AAPL", "Apple Inc.", CIK, 90)
    assert [row["insider_name"] for row in activity["transactions"]] == ["Insider 2", "Insider 1", "Insider 3"]
    assert activity["total_transactions"] == 3
    summary = activity["summary"]
    assert (summary["buy_count"], summary["sell_count"], summary["buy_shares"], summary["sell_shares"]) == (1, 2, 100, 450)
    assert (summary["plan_10b5_1_sell_shares"], summary["discretionary_net_shares"]) == (400, 50)
    first = activity["transactions"][0]
    assert (first["transaction_date"], first["filed_date"], first["accession"], first["value"], first["is_10b5_1"]) == (
        "2026-11-12", "2026-11-13", "0000320193-26-000002", 4800.0, True)
    assert activity["scan"] == {"status": "complete", "filings_listed": 1, "filings_read": 1, "oldest_filed_date": "2026-09-01",
                                "refreshed_at": "2026-11-14T11:55:00Z", "retry_after_seconds": None}
    assert activity["scan_due"] is False


def test_a_shorter_window_narrows_the_list_the_count_and_the_summary_together(db):
    trade(db, 1, "P", 100, 10.0, days_ago=5)
    trade(db, 2, "S", 50, 11.0, days_ago=40)
    db.commit()

    activity = read_insider_activity(db, "AAPL", window_days=30, now=NOW)
    assert (activity["total_transactions"], len(activity["transactions"])) == (1, 1)
    assert (activity["summary"]["buy_count"], activity["summary"]["sell_count"]) == (1, 0)


def test_the_list_is_cut_to_its_limit_and_the_count_and_summary_are_not(db):
    for n in range(1, 8):
        trade(db, n, "P", 10, 1.0, days_ago=n)
    db.commit()

    activity = read_insider_activity(db, "AAPL", recent_limit=3, now=NOW)
    assert (len(activity["transactions"]), activity["total_transactions"], activity["summary"]["buy_count"]) == (3, 7, 7)


def test_a_company_never_scanned_reads_as_scanning_with_nothing_stored_and_a_step_due(db):
    activity = read_insider_activity(db, "AAPL", now=NOW)

    assert (activity["transactions"], activity["total_transactions"], activity["summary"]["buy_count"]) == ([], 0, 0)
    assert activity["scan"] == {"status": "scanning", "filings_listed": 0, "filings_read": 0, "oldest_filed_date": None,
                                "refreshed_at": None, "retry_after_seconds": scan_service.POLL_SECONDS}
    assert activity["scan_due"] is True


def test_no_step_is_due_for_a_further_issuer_while_enough_scans_are_under_way(db):
    for n in range(scan_service.MAX_SCANS_UNDER_WAY):
        db.add(InsiderScan(issuer_cik=str(900 + n), status="scanning", pauses=0, steps=1, created_at=NOW,
                           updated_at=NOW - timedelta(minutes=1)))
    db.commit()
    assert read_insider_activity(db, "AAPL", now=NOW)["scan_due"] is False

    stalled = db.query(InsiderScan).filter_by(issuer_cik="900").one()
    stalled.updated_at = NOW - scan_service.UNDER_WAY_WINDOW - timedelta(seconds=1)   # one of them went quiet
    db.commit()
    assert read_insider_activity(db, "AAPL", now=NOW)["scan_due"] is True


@pytest.mark.parametrize("status", ["idle", "paused", "failed"])
def test_only_scans_that_are_reading_filings_count_as_under_way(db, status):
    """Three issuers that finished or paused a moment ago hold no place on the worker."""
    for n in range(scan_service.MAX_SCANS_UNDER_WAY):
        db.add(InsiderScan(issuer_cik=str(900 + n), status=status, pauses=0, steps=1, created_at=NOW,
                           updated_at=NOW - timedelta(seconds=30)))
    db.commit()
    assert read_insider_activity(db, "AAPL", now=NOW)["scan_due"] is True


def test_a_scan_of_this_issuer_does_not_count_against_itself(db):
    for cik in (CIK, "901", "902"):
        db.add(InsiderScan(issuer_cik=cik, status="scanning", pauses=0, steps=1, created_at=NOW - timedelta(hours=1),
                           updated_at=NOW - timedelta(minutes=2), last_listed_at=NOW - timedelta(minutes=3)))
    db.add(InsiderFiling(accession="0000320193-26-000009", issuer_cik=CIK, status="listed", created_at=NOW, updated_at=NOW))
    db.commit()
    assert read_insider_activity(db, "AAPL", now=NOW)["scan_due"] is True   # its own chain went quiet: restart it


@pytest.mark.parametrize("ticker", ["MSFT", "", "AAPL.X"])
def test_a_ticker_no_stored_company_has_is_none(db, ticker):
    assert read_insider_activity(db, ticker, now=NOW) is None


def test_a_company_without_a_real_cik_is_none(db):
    db.add(Company(cik="0", ticker="NOCIK", name="No CIK Inc."))
    db.commit()
    assert read_insider_activity(db, "NOCIK", now=NOW) is None

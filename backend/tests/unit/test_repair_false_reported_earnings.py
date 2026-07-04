"""Repair script for falsely-reported earnings rows: classification + mutation semantics.

The script re-classifies edgar_8k `reported` rows with the SAME guard the engine uses
(`is_probable_earnings_release`), so these tests pin the repair contract: keep genuine flips,
restore false flips to their prior estimate, delete insert-path creations.
"""
import importlib
import os
import sys
from datetime import date, datetime, timezone

import pytest

from app.models.earnings import (
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    SOURCE_EDGAR_8K,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
repair_mod = importlib.import_module("repair_false_reported_earnings")


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


TICKERS = ["RSTOR", "RDEL", "RKPRI", "RKGAP", "ROOW", "REST"]
WINDOW = (date(2026, 6, 28), date(2026, 7, 4))


def _clear():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.query(EarningsEvent).filter(EarningsEvent.ticker.in_(TICKERS)).delete(synchronize_session=False)
    db.commit()
    db.close()


def _seed_all():
    """The six classification shapes (tickers map 1:1 to expected outcomes)."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    rows = [
        # RSTOR — BIIB shape: pre-announcement flip. prior 7/29, filed 7/1 (gap 1, delta 28) → RESTORE.
        EarningsEvent(
            ticker="RSTOR", company_name="Restore Inc", fiscal_period_end=date(2026, 6, 30),
            event_date=date(2026, 7, 1), status=STATUS_REPORTED, confidence="high",
            source=SOURCE_EDGAR_8K, accession_number="acc-rstor", reported_at=now,
            prior_event_date=date(2026, 7, 29), date_changed_at=now, event_time="bmo",
        ),
        # RDEL — MVO shape: insert-path creation (prior NULL), gap 2 → DELETE.
        EarningsEvent(
            ticker="RDEL", company_name="Delete Trust", fiscal_period_end=date(2026, 6, 30),
            event_date=date(2026, 7, 2), status=STATUS_REPORTED, confidence="high",
            source=SOURCE_EDGAR_8K, accession_number="acc-rdel", reported_at=now,
        ),
        # RKPRI — genuine flip with a recorded date move: prior 6/30, filed 7/1, fpe 5/31
        # (gap 31 and delta 1 both pass) → KEEP.
        EarningsEvent(
            ticker="RKPRI", company_name="Keep Prior Inc", fiscal_period_end=date(2026, 5, 31),
            event_date=date(2026, 7, 1), status=STATUS_REPORTED, confidence="high",
            source=SOURCE_EDGAR_8K, accession_number="acc-rkpri", reported_at=now,
            prior_event_date=date(2026, 6, 30), date_changed_at=now,
        ),
        # RKGAP — STZ shape: prior NULL (estimate matched the filed date exactly), gap 31 → KEEP.
        EarningsEvent(
            ticker="RKGAP", company_name="Keep Gap Inc", fiscal_period_end=date(2026, 5, 31),
            event_date=date(2026, 7, 1), status=STATUS_REPORTED, confidence="high",
            source=SOURCE_EDGAR_8K, accession_number="acc-rkgap", reported_at=now,
        ),
        # ROOW — out of the repair window (event 7/20) with a restore-worthy shape → untouched.
        EarningsEvent(
            ticker="ROOW", company_name="Out Of Window Inc", fiscal_period_end=date(2026, 6, 30),
            event_date=date(2026, 7, 20), status=STATUS_REPORTED, confidence="high",
            source=SOURCE_EDGAR_8K, accession_number="acc-roow", reported_at=now,
            prior_event_date=date(2026, 9, 20), date_changed_at=now,
        ),
        # REST — plain estimate in the window → not selected (status filter), untouched.
        EarningsEvent(
            ticker="REST", company_name="Estimate Inc", fiscal_period_end=date(2026, 6, 30),
            event_date=date(2026, 7, 1), status=STATUS_ESTIMATED, confidence=CONFIDENCE_MEDIUM,
            source=SOURCE_ALPHA_VANTAGE,
        ),
    ]
    db.add_all(rows)
    db.commit()
    db.close()


def _fetch_all():
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    rows = {
        ev.ticker: ev
        for ev in db.query(EarningsEvent).filter(EarningsEvent.ticker.in_(TICKERS)).all()
    }
    db.expunge_all()
    db.close()
    return rows


@pytest.mark.requires_db
def test_dry_run_classifies_without_mutating():
    from app.database import SessionLocal

    _clear()
    _seed_all()
    try:
        db = SessionLocal()
        counts = repair_mod.repair(db, *WINDOW, dry_run=True)
        db.close()
        assert counts == {"keep": 2, "restore": 1, "delete": 1}

        rows = _fetch_all()
        assert set(rows) == set(TICKERS)  # nothing deleted
        assert rows["RSTOR"].status == STATUS_REPORTED  # nothing restored
        assert rows["RSTOR"].event_date == date(2026, 7, 1)
    finally:
        _clear()


@pytest.mark.requires_db
def test_execute_restores_deletes_and_keeps():
    from app.database import SessionLocal

    _clear()
    _seed_all()
    try:
        db = SessionLocal()
        counts = repair_mod.repair(db, *WINDOW, dry_run=False)
        db.close()
        assert counts == {"keep": 2, "restore": 1, "delete": 1}

        rows = _fetch_all()
        # Restored: back to a plain provider estimate on the prior date.
        rstor = rows["RSTOR"]
        assert rstor.event_date == date(2026, 7, 29)
        assert rstor.status == STATUS_ESTIMATED
        assert rstor.confidence == CONFIDENCE_MEDIUM
        assert rstor.source == SOURCE_ALPHA_VANTAGE
        assert rstor.accession_number is None
        assert rstor.reported_at is None
        assert rstor.prior_event_date is None
        assert rstor.date_changed_at is None
        # Deleted: the no-prior implausible row is gone.
        assert "RDEL" not in rows
        # Kept: both genuine flips untouched.
        for t in ("RKPRI", "RKGAP"):
            assert rows[t].status == STATUS_REPORTED
            assert rows[t].event_date == date(2026, 7, 1)
            assert rows[t].accession_number == f"acc-{t.lower()}"
        assert rows["RKPRI"].prior_event_date == date(2026, 6, 30)
        # Out-of-window and non-reported rows untouched.
        assert rows["ROOW"].status == STATUS_REPORTED
        assert rows["ROOW"].event_date == date(2026, 7, 20)
        assert rows["REST"].status == STATUS_ESTIMATED
    finally:
        _clear()


@pytest.mark.requires_db
def test_ticker_filter_scopes_the_repair():
    from app.database import SessionLocal

    _clear()
    _seed_all()
    try:
        db = SessionLocal()
        counts = repair_mod.repair(db, *WINDOW, dry_run=False, ticker="rstor")
        db.close()
        assert counts == {"keep": 0, "restore": 1, "delete": 0}
        rows = _fetch_all()
        assert rows["RSTOR"].status == STATUS_ESTIMATED  # repaired
        assert "RDEL" in rows  # untouched — outside the ticker scope
    finally:
        _clear()

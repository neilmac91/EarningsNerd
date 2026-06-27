"""New-filing detection + alert delivery engine (filing_scan_service).

DB-backed on SQLite (tables created via create_all); EDGAR fetch and email send are injected as
mocks, so no live SEC/Resend calls. Covers: no-historical-spam baseline, real-time vs digest
gating, 8-K Pro-gating, form-type prefs, dedup (one alert per eligible watcher, never twice).
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.filing_scan_service import run_daily_digest, run_filing_scan

NOW = datetime(2026, 6, 17, tzinfo=timezone.utc)
WATCH_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _filing_dict(accession, ftype, date_str):
    return {
        "accession_number": accession,
        "filing_type": ftype,
        "filing_date": date_str,
        "report_date": None,
        "document_url": f"https://sec.example/{accession}/doc.htm",
        "sec_url": f"https://sec.example/{accession}/",
        "cik": "x",
    }


def _fetch_returning(filings):
    async def _fetch(cik, filing_types=None, limit=None):
        return filings

    return _fetch


def _log_count(user_id):
    from app.database import SessionLocal
    from app.models import NotificationLog

    db = SessionLocal()
    try:
        return db.query(NotificationLog).filter(NotificationLog.user_id == user_id).count()
    finally:
        db.close()


@contextmanager
def _scenario(*, is_pro, prefs_overrides=None, watch_since=WATCH_SINCE, n_users=1):
    """Create n watchers of one company. Yields (company_id, ticker, [user_ids])."""
    from app.database import SessionLocal
    from app.models import Company, NotificationPreferences, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)

    user_ids = []
    for i in range(n_users):
        user = User(
            email=f"scan-{suffix}-{i}@example.com",
            hashed_password="x",
            email_verified=True,
            is_active=True,
            is_pro=is_pro,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(Watchlist(user_id=user.id, company_id=company.id, created_at=watch_since))
        prefs = NotificationPreferences(user_id=user.id)
        for k, v in (prefs_overrides or {}).items():
            setattr(prefs, k, v)
        db.add(prefs)
        db.commit()
        user_ids.append(user.id)

    company_id, ticker = company.id, company.ticker
    db.close()
    try:
        yield company_id, ticker, user_ids
    finally:
        db = SessionLocal()
        from app.models import Company, Filing, NotificationLog, NotificationPreferences, User, Watchlist

        db.query(NotificationLog).filter(NotificationLog.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(NotificationPreferences).filter(
            NotificationPreferences.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id == company_id).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == company_id).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_pro_realtime_sent_once_skips_historical_and_dedupes():
    from app.database import SessionLocal

    with _scenario(is_pro=True, prefs_overrides={"realtime": True}) as (cid, ticker, [uid]):
        filings = [
            _filing_dict("acc-new", "10-Q", "2026-06-16"),     # after baseline → alert
            _filing_dict("acc-old", "10-Q", "2026-01-01"),     # before watch → must NOT alert
        ]
        send = AsyncMock()
        db = SessionLocal()
        stats = await run_filing_scan(
            db, fetch_filings=_fetch_returning(filings), send_alert=send, now=NOW, cadence_minutes=0
        )
        db.close()

        assert send.await_count == 1  # only the new filing, not the back-catalogue
        assert send.await_args.kwargs["filing_type"] == "10-Q"
        assert send.await_args.kwargs["ticker"] == ticker
        assert stats["alerts_sent"] == 1
        assert _log_count(uid) == 1

        # Re-deliver the same filings → dedup: no second send, no new log row.
        send2 = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(
            db, fetch_filings=_fetch_returning(filings), send_alert=send2, now=NOW, cadence_minutes=0
        )
        db.close()
        assert send2.await_count == 0
        assert _log_count(uid) == 1


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_free_user_gets_digest_not_realtime():
    from app.database import SessionLocal

    with _scenario(is_pro=False) as (cid, ticker, [uid]):
        filings = [_filing_dict("acc-q1", "10-Q", "2026-06-16")]

        realtime = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(
            db, fetch_filings=_fetch_returning(filings), send_alert=realtime, now=NOW, cadence_minutes=0
        )
        db.close()
        assert realtime.await_count == 0  # free → never real-time
        assert _log_count(uid) == 0

        digest = AsyncMock()
        db = SessionLocal()
        await run_daily_digest(db, send_digest=digest, now=NOW)
        db.close()
        assert digest.await_count == 1
        assert len(digest.await_args.kwargs["items"]) == 1
        assert digest.await_args.kwargs["items"][0]["ticker"] == ticker
        assert _log_count(uid) == 1

        # Digest is idempotent too.
        digest2 = AsyncMock()
        db = SessionLocal()
        await run_daily_digest(db, send_digest=digest2, now=NOW)
        db.close()
        assert digest2.await_count == 0


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_8k_is_pro_only():
    from app.database import SessionLocal

    # Pro with 8-K opted in → real-time 8-K alert.
    with _scenario(is_pro=True, prefs_overrides={"realtime": True, "notify_8k": True}) as (cid, ticker, [uid]):
        send = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(
            db,
            fetch_filings=_fetch_returning([_filing_dict("acc-8k", "8-K", "2026-06-16")]),
            send_alert=send,
            now=NOW,
            cadence_minutes=0,
        )
        db.close()
        assert send.await_count == 1
        assert send.await_args.kwargs["filing_type"] == "8-K"

    # Free with 8-K opted in → never (neither real-time nor digest).
    with _scenario(is_pro=False, prefs_overrides={"notify_8k": True}) as (cid, ticker, [uid]):
        db = SessionLocal()
        await run_filing_scan(
            db,
            fetch_filings=_fetch_returning([_filing_dict("acc-8k2", "8-K", "2026-06-16")]),
            send_alert=AsyncMock(),
            now=NOW,
            cadence_minutes=0,
        )
        db.close()
        digest = AsyncMock()
        db = SessionLocal()
        await run_daily_digest(db, send_digest=digest, now=NOW)
        db.close()
        assert digest.await_count == 0
        assert _log_count(uid) == 0


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_form_type_preference_suppresses_alert():
    from app.database import SessionLocal

    with _scenario(is_pro=True, prefs_overrides={"realtime": True, "notify_10q": False}) as (cid, ticker, [uid]):
        send = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(
            db,
            fetch_filings=_fetch_returning([_filing_dict("acc-q", "10-Q", "2026-06-16")]),
            send_alert=send,
            now=NOW,
            cadence_minutes=0,
        )
        db.close()
        assert send.await_count == 0
        assert _log_count(uid) == 0


@pytest.mark.requires_db
def test_write_log_savepoint_isolates_duplicate_from_pending_changes():
    """A duplicate log insert must roll back ONLY that insert (SAVEPOINT), not other pending
    changes in the same transaction — the bug fixed per PR review."""
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import Filing, Watchlist
    from app.services.filing_scan_service import _write_log

    with _scenario(is_pro=True) as (cid, ticker, [uid]):
        db = SessionLocal()
        filing = Filing(
            company_id=cid,
            accession_number=f"acc-sp-{uuid.uuid4().hex[:6]}",
            filing_type="10-Q",
            filing_date=datetime(2026, 6, 16, tzinfo=timezone.utc),
            document_url="https://sec.example/doc.htm",
            sec_url="https://sec.example/",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        fid = filing.id

        assert _write_log(db, uid, fid, "email", "sent") is True

        # An unrelated, uncommitted change in the same transaction.
        watch = db.query(Watchlist).filter(Watchlist.user_id == uid).first()
        watch.last_alerted_accession = "WATERMARK"

        # Duplicate insert → savepoint rollback; the watch change must survive.
        assert _write_log(db, uid, fid, "email", "sent") is False
        db.commit()
        db.close()

        db2 = SessionLocal()
        persisted = db2.query(Watchlist).filter(Watchlist.user_id == uid).first().last_alerted_accession
        db2.close()
        assert persisted == "WATERMARK"  # not discarded by the duplicate rollback
        assert _log_count(uid) == 1


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_each_eligible_watcher_gets_exactly_one_alert():
    from app.database import SessionLocal

    with _scenario(is_pro=True, prefs_overrides={"realtime": True}, n_users=2) as (cid, ticker, uids):
        send = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(
            db,
            fetch_filings=_fetch_returning([_filing_dict("acc-multi", "10-Q", "2026-06-16")]),
            send_alert=send,
            now=NOW,
            cadence_minutes=0,
        )
        db.close()
        assert send.await_count == 2  # one per watcher
        recipients = {call.kwargs["to_email"] for call in send.await_args_list}
        assert len(recipients) == 2
        for uid in uids:
            assert _log_count(uid) == 1


def test_scan_form_types_gated_by_fpi_flag(monkeypatch):
    """FPI forms are fetched per company only when ENABLE_FPI_FILINGS is on (cost control)."""
    from app.config import settings
    from app.services import filing_scan_service as svc

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    off = svc._scan_form_types()
    assert "20-F" not in off and "6-K" not in off and "40-F" not in off
    assert "10-K" in off and "10-Q" in off and "8-K" in off  # domestic forms always present

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    on = svc._scan_form_types()
    assert {"20-F", "6-K", "40-F"}.issubset(set(on))
    assert "10-K" in on and "8-K" in on

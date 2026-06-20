"""GET /api/users/me/notifications + POST /me/notifications/seen — the in-app bell.

The bell reads the same ``notification_log`` rows the alert scanner writes. Auth is bypassed with a
dependency override returning a stand-in user whose ``notifications_seen_at`` we control directly, so
we can exercise the unread-count / read-flag logic without running a scan.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded():
    """Seed a user with a company, 3 filings, 3 'sent' alert logs (t1<t2<t3) + 1 'failed' log."""
    from app.database import SessionLocal
    from app.models import Company, Filing, NotificationLog, User

    db = SessionLocal()
    user = User(email=f"bell-{uuid.uuid4().hex}@example.com", hashed_password="x",
                email_verified=True, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id

    company = Company(cik=uuid.uuid4().hex[:10], ticker="TST", name="Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id

    base = datetime(2026, 1, 1, 12, 0, 0)
    times = [base, base + timedelta(days=1), base + timedelta(days=2)]
    fids = []
    for i, t in enumerate(times):
        f = Filing(company_id=cid, accession_number=f"acc-{uuid.uuid4().hex}-{i}",
                   filing_type="10-Q", filing_date=t,
                   document_url="https://sec.gov/x", sec_url="https://sec.gov/x")
        db.add(f)
        db.flush()
        fids.append(f.id)
        db.add(NotificationLog(user_id=uid, filing_id=f.id, channel="email",
                               status="sent", created_at=t))
    # A failed log (different channel to dodge the unique constraint) that must be excluded.
    db.add(NotificationLog(user_id=uid, filing_id=fids[0], channel="in_app",
                           status="failed", created_at=times[2]))
    db.commit()
    db.close()

    try:
        yield SimpleNamespace(uid=uid, cid=cid, fids=fids, times=times)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db = SessionLocal()
        db.query(NotificationLog).filter(NotificationLog.user_id == uid).delete()
        db.query(Filing).filter(Filing.company_id == cid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


def _as_user(uid, seen):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uid, notifications_seen_at=seen, is_pro=False, subscription=None,
        email="x@example.com", full_name="Tester")


@pytest.mark.requires_db
def test_lists_sent_alerts_newest_first_all_unread(client):
    with _seeded() as s:
        _as_user(s.uid, None)
        resp = client.get("/api/users/me/notifications")
        assert resp.status_code == 200
        body = resp.json()
        # 3 sent logs surface; the 'failed' log is excluded.
        assert len(body["items"]) == 3
        assert body["unread_count"] == 3
        # Newest first.
        assert [it["filing_id"] for it in body["items"]] == [s.fids[2], s.fids[1], s.fids[0]]
        assert all(it["read"] is False for it in body["items"])
        assert body["items"][0]["ticker"] == "TST"
        assert body["items"][0]["filing_type"] == "10-Q"


@pytest.mark.requires_db
def test_unread_count_and_read_flag_respect_seen(client):
    with _seeded() as s:
        _as_user(s.uid, s.times[1])  # seen at t2
        body = client.get("/api/users/me/notifications").json()
        # Only the t3 alert is newer than t2.
        assert body["unread_count"] == 1
        by_filing = {it["filing_id"]: it for it in body["items"]}
        assert by_filing[s.fids[2]]["read"] is False  # t3 > seen
        assert by_filing[s.fids[1]]["read"] is True    # t2 == seen
        assert by_filing[s.fids[0]]["read"] is True    # t1 < seen


@pytest.mark.requires_db
def test_mark_seen_resets_unread(client):
    from app.database import SessionLocal
    from app.models import User

    with _seeded() as s:
        _as_user(s.uid, None)
        resp = client.post("/api/users/me/notifications/seen")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0
        # Persisted on the user row.
        db = SessionLocal()
        try:
            assert db.get(User, s.uid).notifications_seen_at is not None
        finally:
            db.close()


@pytest.mark.requires_db
def test_limit_is_bounded(client):
    with _seeded() as s:
        _as_user(s.uid, None)
        assert client.get("/api/users/me/notifications?limit=1").json()["items"].__len__() == 1
        assert client.get("/api/users/me/notifications?limit=0").status_code == 422

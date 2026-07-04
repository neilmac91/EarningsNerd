"""HTTP-level tests: public /api/calendar, the alert toggle + tiered 403 bodies, and AV CSV parse."""
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _cleanup_rows():
    """Delete every row these tests create so the shared SQLite DB stays clean — leftover Watchlist
    rows otherwise pollute the global filing-scan/digest queries in other test files."""
    from app.database import SessionLocal
    from app.models import Company, EarningsAlertLog, EarningsEvent, User, Watchlist

    models = [User, Company, Watchlist, EarningsEvent, EarningsAlertLog]
    db = SessionLocal()
    before = {m: {r[0] for r in db.query(m.id).all()} for m in models}
    db.close()
    yield
    db = SessionLocal()
    for m in (EarningsAlertLog, Watchlist, EarningsEvent, Company, User):
        db.query(m).filter(~m.id.in_(before[m])).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture()
def client():
    from main import app

    return TestClient(app)


def _seed_event(ticker, event_date, score=100.0):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.add(EarningsEvent(
        ticker=ticker.upper(), company_name=f"{ticker} Inc", fiscal_period_end=date(2026, 3, 31),
        event_date=event_date, event_time="amc", status="estimated", confidence="medium",
        eps_estimate=1.5, anticipation_score=score, source="alpha_vantage",
    ))
    db.commit()
    db.close()


def test_calendar_endpoint_public_returns_events(client):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    # Relative-future so the estimated row stays ahead of the serve-time past-day filter forever.
    d = date.today() + timedelta(days=30)
    _seed_event("PUBX", d)
    try:
        resp = client.get("/api/calendar", params={
            "from": (d - timedelta(days=10)).isoformat(),
            "to": (d + timedelta(days=10)).isoformat(),
        })
        assert resp.status_code == 200
        body = resp.json()
        assert any(e["ticker"] == "PUBX" and e["event_date"] == d.isoformat() for e in body["events"])
    finally:
        db = SessionLocal()
        db.query(EarningsEvent).filter(EarningsEvent.ticker == "PUBX").delete()
        db.commit()
        db.close()


def test_calendar_rejects_inverted_and_too_wide_ranges(client):
    assert client.get("/api/calendar", params={"from": "2026-08-10", "to": "2026-08-01"}).status_code == 400
    assert client.get("/api/calendar", params={"from": "2026-01-01", "to": "2026-12-31"}).status_code == 400


def test_calendar_requires_params(client):
    assert client.get("/api/calendar").status_code == 422


def _make_user(is_pro=False):
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    u = User(email=f"cal-api-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
             email_verified=True, is_pro=is_pro)
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    return uid


def _auth_as(uid):
    """Override get_current_user to return the live DB user for uid (real get_db is untouched)."""
    from main import app
    from app.routers.auth import get_current_user
    from app.database import SessionLocal
    from app.models import User

    def _override():
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == uid).first()
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = _override


def _clear_auth():
    from main import app
    from app.routers.auth import get_current_user

    app.dependency_overrides.pop(get_current_user, None)


def test_free_cap_403_carries_code(client):
    from app.database import SessionLocal
    from app.models import Company

    uid = _make_user(is_pro=False)
    _auth_as(uid)
    try:
        tickers = ["CA", "CB", "CC", "CD"]
        db = SessionLocal()
        for t in tickers:
            if not db.query(Company).filter(Company.ticker == t).first():
                db.add(Company(cik=f"capi-{uuid.uuid4().hex[:8]}", ticker=t, name=f"{t} Inc"))
        db.commit()
        db.close()

        for t in tickers[:3]:
            r = client.post(f"/api/watchlist/{t}/earnings-alert")
            assert r.status_code == 200, r.text
        # The 4th trips the free cap with the machine-readable code.
        blocked = client.post("/api/watchlist/CD/earnings-alert")
        assert blocked.status_code == 403
        body = blocked.json()
        assert body.get("code") == "earnings_alert_limit"
        assert "3" in body.get("detail", "")
    finally:
        _clear_auth()


def test_pro_cap_403_has_no_code(client):
    """Pro's cap is invisible: the over-limit 403 is terse and carries NO code."""
    from app.database import SessionLocal
    from app.models import Company, Watchlist
    from app.services.entitlements import PRO_EARNINGS_ALERT_LIMIT

    uid = _make_user(is_pro=True)
    _auth_as(uid)
    try:
        db = SessionLocal()
        for i in range(PRO_EARNINGS_ALERT_LIMIT):
            c = Company(cik=f"prc-{uuid.uuid4().hex[:8]}", ticker=f"PA{i:03d}", name="x")
            db.add(c)
            db.flush()
            db.add(Watchlist(user_id=uid, company_id=c.id, earnings_alert=True))
        db.add(Company(cik=f"prc-{uuid.uuid4().hex[:8]}", ticker="PAOVR", name="x"))
        db.commit()
        db.close()

        blocked = client.post("/api/watchlist/PAOVR/earnings-alert")
        assert blocked.status_code == 403
        body = blocked.json()
        assert "code" not in body  # invisible guardrail — nothing to key an upsell on
    finally:
        _clear_auth()


def test_alpha_vantage_csv_parse():
    from app.integrations.alpha_vantage import AlphaVantageClient

    csv_body = (
        "symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay\n"
        "AAPL,Apple Inc,2026-07-30,2026-06-30,1.88,USD,post-market\n"
        "BADROW,,,,,,\n"  # no report date → skipped
        "MSFT,Microsoft,2026-07-29,2026-06-30,,USD,pre-market\n"
    )
    rows = AlphaVantageClient._parse_csv(csv_body)
    assert [r.symbol for r in rows] == ["AAPL", "MSFT"]
    aapl = rows[0]
    assert aapl.report_date == date(2026, 7, 30)
    assert aapl.fiscal_period_end == date(2026, 6, 30)
    assert aapl.eps_estimate == 1.88
    assert aapl.event_time == "amc"
    assert rows[1].event_time == "bmo"
    assert rows[1].eps_estimate is None


def test_calendar_endpoint_filters_to_index_when_enabled(client, monkeypatch):
    """With the index filter on, /api/calendar returns only S&P 500 / Nasdaq 100 members."""
    from app.config import settings
    from app.services import index_membership_service as idx

    monkeypatch.setattr(idx, "_MEMBER_TICKERS", frozenset({"MEMBX"}))
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)

    d = date.today() + timedelta(days=30)
    _seed_event("MEMBX", d)
    _seed_event("TAILX", d)  # non-member: must be filtered out
    resp = client.get("/api/calendar", params={
        "from": (d - timedelta(days=5)).isoformat(),
        "to": (d + timedelta(days=5)).isoformat(),
    })
    assert resp.status_code == 200
    tickers = {e["ticker"] for e in resp.json()["events"]}
    assert "MEMBX" in tickers and "TAILX" not in tickers

"""Earnings-day alerts: per-company toggle, tiered caps (Free 3 visible / Pro 100 invisible),
and the dedup'd digest send."""
import uuid
from datetime import date

import pytest

from app.services import earnings_alert_service as alerts
from app.services.earnings_alert_service import EarningsAlertLimitError
from app.services.entitlements import FREE_EARNINGS_ALERT_LIMIT, PRO_EARNINGS_ALERT_LIMIT


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _cleanup_rows():
    """Delete every row these tests create (users, companies, watchlist, events, alert logs) so the
    shared SQLite DB stays clean — leftover Watchlist rows otherwise pollute the global
    filing-scan/digest queries in other test files."""
    from app.database import SessionLocal
    from app.models import Company, EarningsAlertLog, EarningsEvent, User, Watchlist

    models = [User, Company, Watchlist, EarningsEvent, EarningsAlertLog]
    db = SessionLocal()
    before = {m: {r[0] for r in db.query(m.id).all()} for m in models}
    db.close()
    yield
    db = SessionLocal()
    # Child → parent order for FK safety.
    for m in (EarningsAlertLog, Watchlist, EarningsEvent, Company, User):
        db.query(m).filter(~m.id.in_(before[m])).delete(synchronize_session=False)
    db.commit()
    db.close()


def _mk_user(is_pro=False):
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    u = User(email=f"al-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
             email_verified=True, is_pro=is_pro)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u.id


def _mk_company(ticker):
    from app.database import SessionLocal
    from app.models import Company

    db = SessionLocal()
    c = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if c is None:
        c = Company(cik=f"cik-{uuid.uuid4().hex[:10]}", ticker=ticker.upper(), name=f"{ticker} Inc")
        db.add(c)
        db.commit()
    db.close()


def _load_user(uid):
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    u = db.query(User).get(uid)
    return db, u


@pytest.mark.requires_db
def test_free_cap_blocks_fourth_alert():
    uid = _mk_user(is_pro=False)
    for t in ("AA", "BB", "CC", "DD"):
        _mk_company(t)

    db, user = _load_user(uid)
    try:
        for t in ("AA", "BB", "CC"):
            assert alerts.set_earnings_alert(db, user, t, enabled=True) is True
        assert alerts.count_enabled(db, uid) == FREE_EARNINGS_ALERT_LIMIT

        with pytest.raises(EarningsAlertLimitError) as exc:
            alerts.set_earnings_alert(db, user, "DD", enabled=True)
        assert exc.value.plan_is_pro is False
        assert exc.value.limit == FREE_EARNINGS_ALERT_LIMIT
        # The blocked enable did not persist.
        assert alerts.count_enabled(db, uid) == FREE_EARNINGS_ALERT_LIMIT
    finally:
        db.close()


@pytest.mark.requires_db
def test_disable_frees_a_slot_and_reenable_works():
    uid = _mk_user(is_pro=False)
    for t in ("EE", "FF", "GG", "HH"):
        _mk_company(t)
    db, user = _load_user(uid)
    try:
        for t in ("EE", "FF", "GG"):
            alerts.set_earnings_alert(db, user, t, enabled=True)
        alerts.set_earnings_alert(db, user, "EE", enabled=False)
        assert alerts.count_enabled(db, uid) == 2
        # Now a fourth distinct company fits.
        assert alerts.set_earnings_alert(db, user, "HH", enabled=True) is True
        assert alerts.count_enabled(db, uid) == 3
    finally:
        db.close()


@pytest.mark.requires_db
def test_reenable_same_company_is_idempotent_not_a_new_slot():
    uid = _mk_user(is_pro=False)
    for t in ("II", "JJ", "KK"):
        _mk_company(t)
    db, user = _load_user(uid)
    try:
        for t in ("II", "JJ", "KK"):
            alerts.set_earnings_alert(db, user, t, enabled=True)
        # Enabling an already-on company again must not raise or consume a slot.
        assert alerts.set_earnings_alert(db, user, "II", enabled=True) is True
        assert alerts.count_enabled(db, uid) == 3
    finally:
        db.close()


@pytest.mark.requires_db
def test_pro_cap_is_100_and_flagged_pro():
    uid = _mk_user(is_pro=True)
    db, user = _load_user(uid)
    try:
        # Fabricate PRO_LIMIT enabled rows cheaply, then assert the (limit+1)th is blocked as pro.
        from app.models import Company, Watchlist
        for i in range(PRO_EARNINGS_ALERT_LIMIT):
            c = Company(cik=f"pc-{uuid.uuid4().hex[:10]}", ticker=f"P{i:03d}", name="x")
            db.add(c)
            db.flush()
            db.add(Watchlist(user_id=uid, company_id=c.id, earnings_alert=True))
        db.commit()
        assert alerts.count_enabled(db, uid) == PRO_EARNINGS_ALERT_LIMIT

        _mk_company("OVER")
        with pytest.raises(EarningsAlertLimitError) as exc:
            alerts.set_earnings_alert(db, user, "OVER", enabled=True)
        assert exc.value.plan_is_pro is True
        assert exc.value.limit == PRO_EARNINGS_ALERT_LIMIT
    finally:
        db.close()


@pytest.mark.requires_db
def test_enabled_tickers_lists_only_enabled():
    uid = _mk_user(is_pro=False)
    for t in ("LL", "MM"):
        _mk_company(t)
    db, user = _load_user(uid)
    try:
        alerts.set_earnings_alert(db, user, "LL", enabled=True)
        assert set(alerts.enabled_tickers(db, uid)) == {"LL"}
    finally:
        db.close()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_digest_sends_once_and_dedups():
    from app.database import SessionLocal
    from app.models import Company, EarningsEvent, Watchlist

    uid = _mk_user(is_pro=False)
    today = date.today()
    db = SessionLocal()
    c = Company(cik=f"dg-{uuid.uuid4().hex[:10]}", ticker="DIGG", name="Digg Inc")
    db.add(c)
    db.flush()
    db.add(Watchlist(user_id=uid, company_id=c.id, earnings_alert=True))
    db.add(EarningsEvent(
        ticker="DIGG", company_name="Digg Inc", fiscal_period_end=date(2026, 3, 31),
        event_date=today, event_time="amc", status="estimated", confidence="medium",
        anticipation_score=10.0, source="alpha_vantage",
    ))
    db.commit()

    sent = []

    async def _fake_sender(*, to_email, name, items):
        sent.append((to_email, [it["ticker"] for it in items]))

    stats1 = await alerts.send_earnings_day_alerts(db, today=today, sender=_fake_sender)
    assert stats1["emails"] == 1
    assert sent and sent[0][1] == ["DIGG"]

    # Second run the same day must not re-send (dedup ledger).
    stats2 = await alerts.send_earnings_day_alerts(db, today=today, sender=_fake_sender)
    assert stats2["emails"] == 0
    assert len(sent) == 1
    db.close()

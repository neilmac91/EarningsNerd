"""Route tests for POST /api/waitlist/join (E13c), plus the stats and verify routes it feeds.

Per-test in-memory SQLite, ``get_db`` overridden, both email senders monkeypatched on the router
module (they are imported by name there). Every test uses uuid emails so no two rows can collide
even if the engine were ever shared. ``TestCommitTimeConflicts`` swaps in a per-test SQLite file
so a rival session can commit on its own connection between the join's checks and its insert.
"""
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from main import app
from app.database import Base, get_db
from app.models import WaitlistSignup
from app.routers import watchlist as watchlist_router
from app.services import turnstile, waitlist_service


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def emails(monkeypatch):
    """Recorders for the welcome + referral senders; ``welcome_error`` makes the welcome send raise."""
    rec = {"welcome": [], "referral": [], "welcome_error": None}

    async def _welcome(**kwargs):
        rec["welcome"].append(kwargs)
        if rec["welcome_error"] is not None:
            raise rec["welcome_error"]

    async def _referral(**kwargs):
        rec["referral"].append(kwargs)

    monkeypatch.setattr(watchlist_router, "send_waitlist_welcome_email", _welcome)
    monkeypatch.setattr(watchlist_router, "send_referral_success_email", _referral)
    return rec


@pytest.fixture
def client(session_factory, monkeypatch, emails):
    watchlist_router.WAITLIST_JOIN_LIMITER._hits.clear()
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        watchlist_router.WAITLIST_JOIN_LIMITER._hits.clear()
        with session_factory() as s:
            s.query(WaitlistSignup).delete()
            s.commit()


def _join(client, **payload):
    return client.post("/api/waitlist/join", json=payload)


def _seed_referrer(session_factory, code: str = "ref00001") -> str:
    email = _email()
    with session_factory() as s:
        s.add(WaitlistSignup(email=email, name="Ref", referral_code=code, position=1, priority_score=0))
        s.commit()
    return email


def test_honeypot_is_rejected_with_400(client, session_factory):
    resp = _join(client, email=_email(), honeypot="bot-filled")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid submission."
    with session_factory() as s:
        assert s.query(WaitlistSignup).count() == 0


@pytest.mark.parametrize("field", ["name", "source"])
def test_oversized_or_control_character_name_and_source_are_422(client, session_factory, emails, field):
    assert _join(client, email=_email(), **{field: "x" * 101}).status_code == 422
    assert _join(client, email=_email(), **{field: "Eve\r\nBcc: x"}).status_code == 422
    with session_factory() as s:
        assert s.query(WaitlistSignup).count() == 0
    assert emails["welcome"] == []

    ok = _join(client, email=_email(), **{field: "  Jane Doe  "})
    assert ok.status_code == 200, ok.text
    with session_factory() as s:
        assert getattr(s.query(WaitlistSignup).one(), field) == "Jane Doe"


def test_unknown_referral_code_is_400_invalid_referral(client, session_factory):
    resp = _join(client, email=_email(), referral_code="nosuch01")
    assert resp.status_code == 400
    assert resp.json() == {
        "success": False,
        "error": "invalid_referral",
        "message": "Referral code not recognized.",
    }
    with session_factory() as s:
        assert s.query(WaitlistSignup).count() == 0


def test_duplicate_email_returns_already_registered(client, emails):
    email = _email()
    first = _join(client, email=email)
    assert first.status_code == 200 and first.json()["success"] is True

    dup = _join(client, email=email.upper())  # the validator lower-cases, so this is the same row
    assert dup.status_code == 200
    body = dup.json()
    assert body["success"] is False and body["error"] == "already_registered"
    assert body["referral_code"] == first.json()["referral_code"]
    assert len(emails["welcome"]) == 1  # no second welcome email


def test_existing_email_is_checked_before_the_referral_code(client, session_factory, emails):
    """A rejoin with a bad referral code is still answered as already_registered (200), not as
    invalid_referral (400): the existing-email check runs before the referral lookup."""
    email = _email()
    first = _join(client, email=email)
    assert first.status_code == 200 and first.json()["success"] is True

    rejoin = _join(client, email=email, referral_code="nosuch01")
    assert rejoin.status_code == 200, rejoin.text
    body = rejoin.json()
    assert body["success"] is False and body["error"] == "already_registered"
    assert body["referral_code"] == first.json()["referral_code"]
    with session_factory() as s:
        assert s.query(WaitlistSignup).filter_by(email=email).count() == 1
    assert len(emails["welcome"]) == 1


def test_valid_referral_bumps_referrer_priority_and_sends_referral_email(client, session_factory, emails):
    referrer_email = _seed_referrer(session_factory, code="ref00001")
    resp = _join(client, email=_email(), referral_code="REF00001")  # normalised to lower-case
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    with session_factory() as s:
        referrer = s.query(WaitlistSignup).filter_by(email=referrer_email).one()
        assert referrer.priority_score == 1
        joined = s.query(WaitlistSignup).filter_by(referred_by="ref00001").one()
        assert joined.referral_code == resp.json()["referral_code"]

    assert [r["to_email"] for r in emails["referral"]] == [referrer_email]
    assert emails["referral"][0]["new_position"] == watchlist_router.calculate_waitlist_position(1, 1)


def test_welcome_email_sent_flag_tracks_the_send(client, session_factory, emails):
    ok_email = _email()
    ok = _join(client, email=ok_email)
    assert ok.status_code == 200 and ok.json()["email_sent"] is True

    emails["welcome_error"] = RuntimeError("resend down")
    failed_email = _email()
    failed = _join(client, email=failed_email)
    assert failed.status_code == 200, failed.text
    assert failed.json()["success"] is True and failed.json()["email_sent"] is False

    with session_factory() as s:
        rows = {r.email: r.welcome_email_sent for r in s.query(WaitlistSignup).all()}
    assert rows[ok_email] is True
    assert rows[failed_email] is False  # row persists, flag stays False
    assert len(emails["welcome"]) == 2


def test_failed_welcome_flag_commit_is_rolled_back_logged_and_still_200(
    client, session_factory, emails, caplog
):
    """The flag commit shares the welcome try: a failed flush is rolled back, logged and swallowed.

    The failed flush leaves the session needing a rollback and expires the loaded rows, so the
    ``signup.id`` log read and the referrer read only work because the router rolls back first.
    """
    referrer_email = _seed_referrer(session_factory, code="ref00001")
    email = _email()

    def _fail_the_flag_flush(session, _flush_context):
        if any(isinstance(obj, WaitlistSignup) and obj.welcome_email_sent for obj in session.dirty):
            raise RuntimeError("flag commit failed")

    event.listen(session_factory, "after_flush", _fail_the_flag_flush)
    caplog.set_level(logging.ERROR, logger="app.routers.watchlist")
    resp = _join(client, email=email, referral_code="ref00001")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True and body["email_sent"] is False
    with session_factory() as s:
        row = s.query(WaitlistSignup).filter_by(email=email).one()
        signup_id, flag, code = row.id, row.welcome_email_sent, row.referral_code
        assert s.query(WaitlistSignup).filter_by(email=referrer_email).one().priority_score == 1
    assert flag is False and code == body["referral_code"]  # the row persists; the flag does not
    assert [w["to_email"] for w in emails["welcome"]] == [email]
    assert [r["to_email"] for r in emails["referral"]] == [referrer_email]
    assert [r.getMessage() for r in caplog.records if r.name == "app.routers.watchlist"] == [
        f"Waitlist welcome email failed for signup {signup_id}"
    ]


def test_join_total_signups_position_and_stats_count_existing_rows(client):
    first = _join(client, email=_email())
    second = _join(client, email=_email())
    assert (first.json()["total_signups"], first.json()["position"]) == (0, 1)
    assert (second.json()["total_signups"], second.json()["position"]) == (1, 2)

    stats = client.get("/api/waitlist/stats")
    assert stats.status_code == 200
    assert stats.json() == {"total_signups": 2}


def test_verification_link_verifies_then_404s_once_the_entry_is_gone(client, session_factory, emails):
    email = _email()
    assert _join(client, email=email).status_code == 200
    token = emails["welcome"][0]["verification_link"].rsplit("/", 1)[-1]

    ok = client.post(f"/api/waitlist/verify/{token}")
    assert ok.status_code == 200
    assert ok.json() == {"success": True, "message": "Email verified."}
    with session_factory() as s:
        row = s.query(WaitlistSignup).filter_by(email=email).one()
        assert row.email_verified is True
        s.delete(row)
        s.commit()

    gone = client.post(f"/api/waitlist/verify/{token}")
    assert gone.status_code == 404
    assert gone.json() == {"detail": "Waitlist entry not found."}


def _before_first_commit(session_factory, rival_write) -> None:
    """Call ``rival_write(session)`` once, just before the next commit of a ``session_factory`` session.

    Stands in for a concurrent request that commits after the join's up-front checks and before
    its insert reaches the database (the join's first commit is the insert).
    """
    fired = []

    def _hook(session):
        if not fired:
            fired.append(True)
            rival_write(session)

    event.listen(session_factory, "before_commit", _hook)


class TestCommitTimeConflicts:
    @pytest.fixture
    def session_factory(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'waitlist.db'}", poolclass=NullPool)
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_concurrent_join_of_the_same_email_returns_already_registered(
        self, client, session_factory, emails
    ):
        _seed_referrer(session_factory, code="ref00001")
        email = _email()

        def _rival_joins_first(_session):
            with session_factory() as rival:
                rival.add(WaitlistSignup(email=email, referral_code="rival001", position=7, priority_score=1))
                rival.commit()

        _before_first_commit(session_factory, _rival_joins_first)
        resp = _join(client, email=email, referral_code="ref00001")

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "success": False,
            "error": "already_registered",
            "message": "This email is already on the waitlist!",
            "position": 2,  # 7 - 1 * REFERRAL_BONUS
            "referral_code": "rival001",
            "referral_link": waitlist_service.build_referral_link("rival001"),
        }
        with session_factory() as s:
            assert s.query(WaitlistSignup).filter_by(referral_code="ref00001").one().priority_score == 0
            assert s.query(WaitlistSignup).filter_by(email=email).one().referral_code == "rival001"
        assert emails["welcome"] == [] and emails["referral"] == []

    def test_insert_conflict_with_no_row_for_the_email_is_500(self, client, session_factory, emails):
        email = _email()

        def _rival_takes_the_new_referral_code(session):
            pending = next(obj for obj in session.new if isinstance(obj, WaitlistSignup))
            with session_factory() as rival:
                rival.add(
                    WaitlistSignup(
                        email=_email(), referral_code=pending.referral_code, position=1, priority_score=0
                    )
                )
                rival.commit()

        _before_first_commit(session_factory, _rival_takes_the_new_referral_code)
        resp = _join(client, email=email)

        assert resp.status_code == 500
        assert resp.json() == {"detail": "Unable to create waitlist signup."}
        with session_factory() as s:
            assert s.query(WaitlistSignup).filter_by(email=email).count() == 0
            assert s.query(WaitlistSignup).count() == 1  # only the rival's row
        assert emails["welcome"] == []

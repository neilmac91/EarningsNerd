"""The scheduled retention purge deletes exactly the rows DATA_RETENTION_POLICY.md promises to
delete on a clock, in bounded batches, and a dry run counts without deleting."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ContactSubmission, LoginAttempt, OAuthState, RefreshToken, User, UserSearch
from app.services import retention_service as retention

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
NAIVE_NOW = NOW.replace(tzinfo=None)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _days(n: int) -> datetime:
    return NOW - timedelta(days=n)


def _seed(db: Session) -> dict:
    user = User(email="ret@example.com")
    db.add(user)
    db.flush()
    rows = {
        "search_old": UserSearch(user_id=user.id, query="old", created_at=_days(366)),
        "search_new": UserSearch(user_id=user.id, query="new", created_at=_days(364)),
        "attempt_old": LoginAttempt(email_hash="a" * 64, failed_count=3, updated_at=_days(8)),
        "attempt_new": LoginAttempt(email_hash="b" * 64, failed_count=3, updated_at=_days(6)),
        # Stale but still locked: the lock outlives the seven-day window and must not vanish.
        "attempt_locked": LoginAttempt(
            email_hash="c" * 64, failed_count=9, updated_at=_days(8), locked_until=NOW + timedelta(hours=1)
        ),
        "state_expired": OAuthState(state="s1", nonce="n", expires_at=NAIVE_NOW - timedelta(minutes=1)),
        "state_live": OAuthState(state="s2", nonce="n", expires_at=NAIVE_NOW + timedelta(minutes=1)),
        "token_long_expired": RefreshToken(user_id=user.id, token_hash="t1", expires_at=NAIVE_NOW - timedelta(days=31)),
        "token_recently_expired": RefreshToken(user_id=user.id, token_hash="t2", expires_at=NAIVE_NOW - timedelta(days=29)),
        "token_long_revoked": RefreshToken(
            user_id=user.id, token_hash="t3", expires_at=NAIVE_NOW + timedelta(days=10),
            revoked_at=NAIVE_NOW - timedelta(days=31),
        ),
        "token_live": RefreshToken(user_id=user.id, token_hash="t4", expires_at=NAIVE_NOW + timedelta(days=10)),
        "contact_old": ContactSubmission(name="n", email="c@example.com", message="m", created_at=_days(366)),
        "contact_new": ContactSubmission(name="n", email="c@example.com", message="m", created_at=_days(364)),
    }
    db.add_all(rows.values())
    db.commit()
    return rows


def _remaining(db: Session) -> dict:
    return {
        "searches": {r.query for r in db.execute(select(UserSearch)).scalars()},
        "attempts": {r.email_hash[0] for r in db.execute(select(LoginAttempt)).scalars()},
        "states": {r.state for r in db.execute(select(OAuthState)).scalars()},
        "tokens": {r.token_hash for r in db.execute(select(RefreshToken)).scalars()},
        "contacts": {r.created_at.day for r in db.execute(select(ContactSubmission)).scalars()},
    }


EXPECTED_STATS = {
    "dry_run": False, "search_history_purged": 1, "login_attempts_purged": 1, "oauth_states_purged": 1,
    "refresh_tokens_purged": 2, "contact_submissions_purged": 1,
}


def test_purges_exactly_the_policy_rows_and_keeps_everything_inside_the_window(db):
    _seed(db)
    assert retention.run_retention_purge(db, now=NOW) == EXPECTED_STATS
    assert _remaining(db) == {
        "searches": {"new"},
        "attempts": {"b", "c"},  # the locked row survives its stale timestamp
        "states": {"s2"},
        "tokens": {"t2", "t4"},  # recently expired keeps its 30-day grace; live stays
        "contacts": {(NOW - timedelta(days=364)).day},
    }


def test_dry_run_reports_the_same_counts_and_deletes_nothing(db):
    _seed(db)
    before = _remaining(db)
    assert retention.run_retention_purge(db, dry_run=True, now=NOW) == {**EXPECTED_STATS, "dry_run": True}
    assert _remaining(db) == before


def test_batches_cover_a_backlog_larger_than_one_batch(db):
    user = User(email="bulk@example.com")
    db.add(user)
    db.flush()
    db.add_all(UserSearch(user_id=user.id, query=f"q{i}", created_at=_days(400)) for i in range(7))
    db.commit()
    stats = retention.run_retention_purge(db, now=NOW, batch_size=3)
    assert stats["search_history_purged"] == 7
    assert db.execute(select(UserSearch)).scalars().all() == []


def test_batch_size_must_be_positive(db):
    with pytest.raises(ValueError):
        retention.run_retention_purge(db, now=NOW, batch_size=0)


def test_second_run_is_a_no_op(db):
    _seed(db)
    retention.run_retention_purge(db, now=NOW)
    again = retention.run_retention_purge(db, now=NOW)
    assert all(v == 0 for k, v in again.items() if k.endswith("_purged"))

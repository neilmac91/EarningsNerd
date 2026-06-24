"""
Unit tests for the closed-beta invite service (mint / validate / single-use redeem).

Runs against a fresh in-memory SQLite engine (all models registered via `import app.models`), so it
needs no Postgres and no running app.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401  — registers User/InviteCode on Base.metadata
from app.models.invite import InviteCode
from app.services import invite_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_mint_then_validate_then_redeem(db):
    invite, raw, link = invite_service.mint_invite(db, created_by=None, email=None)
    assert link.endswith(f"/register?invite={raw}")
    # The raw token is never persisted — only its hash.
    assert db.query(InviteCode).filter(InviteCode.code_hash == raw).first() is None

    assert invite_service.validate_invite(db, raw, "anyone@example.com") is not None

    user = SimpleNamespace(id=42)
    assert invite_service.redeem_invite(db, invite, user) is True
    # Single-use: a second redeem loses the guarded UPDATE.
    assert invite_service.redeem_invite(db, invite, user) is False
    # And it no longer validates once used.
    assert invite_service.validate_invite(db, raw, "anyone@example.com") is None


def test_missing_or_unknown_token_is_invalid(db):
    assert invite_service.validate_invite(db, None, "a@b.com") is None
    assert invite_service.validate_invite(db, "", "a@b.com") is None
    assert invite_service.validate_invite(db, "not-a-real-token", "a@b.com") is None


def test_expired_invite_is_invalid(db):
    _invite, raw, _ = invite_service.mint_invite(db, created_by=None, email=None, expires_in_hours=-1)
    assert invite_service.validate_invite(db, raw, "a@b.com") is None


def test_revoked_invite_is_invalid(db):
    invite, raw, _ = invite_service.mint_invite(db, created_by=None, email=None)
    invite.is_revoked = True
    db.commit()
    assert invite_service.validate_invite(db, raw, "a@b.com") is None


def test_email_bound_invite_enforces_match(db):
    _invite, raw, _ = invite_service.mint_invite(db, created_by=None, email="Friend@Example.com")
    # Case-insensitive match accepted; a different address rejected.
    assert invite_service.validate_invite(db, raw, "friend@example.com") is not None
    assert invite_service.validate_invite(db, raw, "stranger@example.com") is None

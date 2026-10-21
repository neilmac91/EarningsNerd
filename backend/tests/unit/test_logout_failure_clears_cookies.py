"""A logout whose revoke fails still logs this browser out.

``POST /api/auth/logout`` clears the session cookies only once its revoke has returned. When the revoke
raised (the token store down, the pool exhausted), the exception reached the global handler, whose fresh
500 carried none of the deletions: the access cookie, ``en_session`` and the 30-day refresh cookie all
stayed in the browser, and on a shared computer the next person to open the site was signed in as the
first. The route now answers 503 on a response of its own that carries the three deletions. Setting them
on the injected Response and raising instead would drop them, as FastAPI renders an HTTPException as a
fresh response (``/refresh``'s clears are lost that way: ``test_auth_token_flows.py`` pins it).

A failed revoke writes no audit row, since no session is known to have ended, and leaves nothing
half-committed: the unit's own ``release_request_session`` rolls it back, so the token stays live in the
database while the browser loses it. A successful logout is pinned beside it, unchanged.
"""
import logging
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session

from main import app
from app.database import SessionLocal
from app.models import AuditLog, RefreshToken, User
from app.services import refresh_token_service
from app.services.password_utils import get_password_hash
from tests.support.summary_stream_harness import reset_rate_limiters

PASSWORD = "Sup3rSecretPassw0rd"  # test fixture, not a credential  # gitleaks:allow

# The three deletions, as the test settings render them (expiry stamps redacted).
SESSION_CLEARED = [
    'earningsnerd_access_token=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax',
    'en_session=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax',
    'earningsnerd_refresh_token=""; expires=<t>; Max-Age=0; Path=/api/auth; SameSite=lax',
]
LOGOUT_INCOMPLETE = {"detail": "This browser is logged out, but we could not end the session on the server."}
_EXPIRES = re.compile(r"expires=[^;]+")


@pytest.fixture(scope="module")
def client():
    # Server exceptions answer as the app's handlers answer them, so the code before the fix shows its 500.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client):
    reset_rate_limiters()
    client.cookies.clear()
    yield
    client.cookies.clear()


@pytest.fixture
def account(client):
    """A verified password account, logged in on ``client``: (user id, email, raw refresh token)."""
    email = f"logoutfail_{uuid.uuid4().hex[:12]}@example.com"
    with SessionLocal() as db:
        user = User(email=email, hashed_password=get_password_hash(PASSWORD), email_verified=True, is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    refresh = client.cookies.get("earningsnerd_refresh_token")
    assert refresh and client.get("/api/auth/me").status_code == 200
    return user_id, email, refresh


@pytest.fixture(params=["flush-fails", "pool-exhausted"])
def the_revoke_fails(request, monkeypatch):
    """Make the logout's revoke raise: at its commit's flush, after it marked the token revoked in the session (the
    token store down), or before it reads anything (no connection to be had)."""
    if request.param == "pool-exhausted":
        def _no_connection(*_args, **_kwargs):
            raise PoolTimeoutError("QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 10.00")

        monkeypatch.setattr(refresh_token_service, "revoke_and_commit", _no_connection)
        yield
        return

    def _before_flush(session, _flush_context, _instances):
        if any(isinstance(obj, RefreshToken) and obj.revoked_at is not None for obj in session.dirty):
            raise RuntimeError("refresh-token store down")

    event.listen(Session, "before_flush", _before_flush)
    yield
    event.remove(Session, "before_flush", _before_flush)


def _cookies(resp) -> list[str]:
    """The response's Set-Cookie headers in order, expiry stamps redacted."""
    return [_EXPIRES.sub("expires=<t>", header) for header in resp.headers.get_list("set-cookie")]


def _logout_rows(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(AuditLog).filter(AuditLog.user_id == str(user_id), AuditLog.action == "logout").count()


def _live_refresh_tokens(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).count()


@pytest.mark.requires_db
def test_a_logout_whose_revoke_fails_answers_503_and_still_clears_the_session_cookies(
    client, account, the_revoke_fails, caplog
):
    user_id, email, refresh = account
    caplog.set_level(logging.ERROR, logger="app.routers.auth")

    resp = client.post("/api/auth/logout")

    assert resp.status_code == 503, resp.text
    assert resp.json() == LOGOUT_INCOMPLETE
    assert _cookies(resp) == SESSION_CLEARED
    # The jar applied the deletions: the browser holds no session the next request could use.
    assert client.cookies.get("earningsnerd_access_token") is None
    assert client.cookies.get("earningsnerd_refresh_token") is None
    assert client.get("/api/auth/me").status_code == 401
    # No session is known to have ended, so no row says one did; the failed unit committed nothing.
    assert _logout_rows(user_id) == 0
    assert _live_refresh_tokens(user_id) == 1
    # Logged with its traceback (Sentry reads it), naming neither the account nor its token.
    failures = [r for r in caplog.records if r.name == "app.routers.auth" and r.levelno == logging.ERROR]
    assert len(failures) == 1 and failures[0].exc_info is not None
    assert email not in failures[0].getMessage() and refresh not in failures[0].getMessage()


@pytest.mark.requires_db
def test_a_logout_that_revokes_answers_200_and_clears_the_session_cookies(client, account):
    user_id, _email, _refresh = account

    resp = client.post("/api/auth/logout")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "success"}
    assert _cookies(resp) == SESSION_CLEARED
    assert client.get("/api/auth/me").status_code == 401
    assert _logout_rows(user_id) == 1
    assert _live_refresh_tokens(user_id) == 0

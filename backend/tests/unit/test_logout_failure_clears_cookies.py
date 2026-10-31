"""A logout whose revoke fails still logs this browser out; one that fails after the revoke committed succeeded.

``POST /api/auth/logout`` clears the session cookies only once its revoke has returned. When the revoke
raised (the token store down, the pool exhausted), the exception reached the global handler, whose fresh
500 carried none of the deletions: the access cookie, ``en_session`` and the 30-day refresh cookie all
stayed in the browser, and on a shared computer the next person to open the site was signed in as the
first. The route now answers 503 on a response of its own that carries the three deletions. Setting them
on the injected Response and raising instead would drop them, as FastAPI renders an HTTPException as a
fresh response (``/refresh``'s were, until E121 removed them; ``test_raised_answers_carry_no_injected_headers.py``
now refuses the form).

A failed revoke writes no audit row, since no session is known to have ended, and leaves nothing
half-committed: the unit's own ``release_request_session`` rolls it back, so the token stays live in the
database while the browser loses it. A step that raises after the revoke committed (the audit write, the
release) does not undo it: the session ended, so the logout answers 200 as one that succeeded. The plain
successful logout is pinned in ``test_auth_token_flows.py`` (``test_session_cookie_headers_and_their_order``).
"""
import logging
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from main import app
from app.config import settings
from app.database import SessionLocal, engine, get_db
from app.models import AuditLog, RefreshToken, User
from app.services import audit_service, filing_list_service
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
REVOKE_FAILED = "Logout could not revoke the refresh token; clearing this browser's session cookies"
ENDED_THEN_FAILED = "Logout ended the session, but a step after the revoke's commit failed"
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


def _store_down():
    """The token store refuses the revoke's write: its commit's flush raises once it marked the token revoked."""
    def _before_flush(session, _flush_context, _instances):
        if any(isinstance(obj, RefreshToken) and obj.revoked_at is not None for obj in session.dirty):
            raise RuntimeError("refresh-token store down")

    event.listen(Session, "before_flush", _before_flush)
    return lambda: event.remove(Session, "before_flush", _before_flush)


def _pool_exhausted():
    """The request's session draws from a pool with no connection to give: one slot, held elsewhere, and a short
    wait. Every checkout in the request times out as a saturated QueuePool's does, the account lookup before the
    revoke included (get_current_user_optional logs it and reads no user), so the revoke's own first statement
    raises the pool's TimeoutError."""
    exhausted = create_engine(
        engine.url, connect_args={"check_same_thread": False}, poolclass=QueuePool,
        pool_size=1, max_overflow=0, pool_timeout=0.1,
    )
    held = exhausted.connect()
    sessions = sessionmaker(**{**SessionLocal.kw, "bind": exhausted})

    def _exhausted_db():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _exhausted_db

    def _undo():
        app.dependency_overrides.pop(get_db, None)
        held.close()
        exhausted.dispose()

    return _undo


@pytest.fixture(params=["flush-fails", "pool-exhausted"])
def the_revoke_fails(request):
    """Make the logout's revoke raise inside its own unit: at its commit's flush, after it marked the token revoked
    (the token store down), or at its first statement's checkout (the pool exhausted). The value is what it raises."""
    if request.param == "flush-fails":
        undo, raised = _store_down(), RuntimeError
    else:
        undo, raised = _pool_exhausted(), PoolTimeoutError
    yield raised
    undo()


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


def _logged(caplog, message: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "app.routers.auth" and r.getMessage() == message]


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
    failures = _logged(caplog, REVOKE_FAILED)
    assert len(failures) == 1 and failures[0].exc_info is not None and failures[0].exc_info[0] is the_revoke_fails
    assert _logged(caplog, ENDED_THEN_FAILED) == []
    assert email not in failures[0].getMessage() and refresh not in failures[0].getMessage()


@pytest.mark.requires_db
def test_the_503s_deletions_carry_the_production_cookie_domain(client, account, monkeypatch):
    """Production scopes the session cookies to the parent domain (COOKIE_DOMAIN=.earningsnerd.io), and a deletion
    without that domain names another cookie, which the browser keeps. Set after the login, as
    test_auth_cookies.py's domain_scoped sets it, so the request still carries the session the revoke fails on."""
    user_id, _email, _refresh = account
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".earningsnerd.io")
    undo = _store_down()
    try:
        resp = client.post("/api/auth/logout")
    finally:
        undo()

    assert resp.status_code == 503, resp.text
    assert _cookies(resp) == [cookie.replace('=""; ', '=""; Domain=.earningsnerd.io; ', 1) for cookie in SESSION_CLEARED]
    assert _live_refresh_tokens(user_id) == 1


@pytest.fixture(params=["audit-write-raises", "release-raises"])
def a_step_after_the_commit_fails(request, monkeypatch):
    """Make the unit raise after revoke_and_commit returned: the logout's audit write, or the session's release (after
    it released the session, so nothing is left for the finalizer). The value is the logout rows that step leaves."""
    if request.param == "audit-write-raises":
        def _audit_down(*_args, **_kwargs):
            raise RuntimeError("audit store down")

        monkeypatch.setattr(audit_service, "log_logout", _audit_down)
        return 0
    release = filing_list_service.release_request_session

    def _release_then_raise(db):
        release(db)
        raise RuntimeError("release failed")

    monkeypatch.setattr(filing_list_service, "release_request_session", _release_then_raise)
    return 1


@pytest.mark.requires_db
def test_a_logout_that_fails_after_its_revoke_committed_answers_as_one_that_succeeded(
    client, account, a_step_after_the_commit_fails, caplog
):
    user_id, email, refresh = account
    caplog.set_level(logging.ERROR, logger="app.routers.auth")

    resp = client.post("/api/auth/logout")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "success"}
    assert _cookies(resp) == SESSION_CLEARED
    assert client.get("/api/auth/me").status_code == 401
    # The revoke committed before the step that raised; the audit row is that step's own outcome.
    assert _live_refresh_tokens(user_id) == 0
    assert _logout_rows(user_id) == a_step_after_the_commit_fails
    ended = _logged(caplog, ENDED_THEN_FAILED)
    assert len(ended) == 1 and ended[0].exc_info is not None
    assert _logged(caplog, REVOKE_FAILED) == []
    assert email not in ended[0].getMessage() and refresh not in ended[0].getMessage()

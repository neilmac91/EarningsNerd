"""Real PostgreSQL races for refresh-token rotation and revocation (E127); behavioral cases stay in the
unit home.

REFRESH_CONCURRENCY_TEST_DATABASE_URL enables this required CI gate. A configured invalid or
unavailable database fails; every case owns a disposable schema and never changes public tables.

A rotation reads its token, checks that it is live, mints a successor and marks the token rotated; a
logout and a logout-all revoke what they read as live. Since #1394 runs them in the thread pool, and
always across the API's two instances, two of them can interleave inside those steps. Each case runs
two of them on one user's token, each in a session made with production's ``SessionLocal`` settings
(autoflush off), so their statements reach the database in production's order. The first holds its
COMMIT until the second is blocked on a lock or has finished, so the second makes its first read, and
its check if nothing stops it, while the first's writes are uncommitted:
- two refreshes with one cookie: one rotates, and the other meets the replay sweep, as the second of
  two did when refresh ran on the event loop, so no live token is left;
- a refresh and a logout-all, in either order: no live token is left;
- a refresh and a password reset, in either order: no live token is left, as account recovery promises;
- a refresh and a password change, in either order: only the changer's new session is left;
- a logout, then a refresh with the same cookie: the refresh is refused and no live token is left;
- a refresh, then a logout with the same cookie: the logout signs out the successor the refresh minted;
- a refresh with the cookie another tab's refresh left, then a logout with the cookie before it: the
  logout walks the chain to its live tip and signs that out;
- a refresh, then a sign-in: the sign-in's new token does not wait for the lock;
- a password reset or change, and a password login that verified the old password before it committed,
  in either order: the login mints only while the hash it verified is the account's (E121), so the
  reset leaves no live token and the change only its own;
- a password reset and a password change that verified the old password, in either order, and two such
  changes: a change writes only while the hash it verified is the account's (E121), so the reset's
  password stands with no live token, and of two changes the first's password and session;
- two first passwords set at once on an account that had none: the first stands, with its session;
- two password logins of one account: the second waits for the first's commit, and both mint;
- two unlinks of one account, one per provider on an account with no password or one provider twice, and
  an unlink while a first password is set: the unlink counts what committed before it (E121), so the
  account keeps a sign-in method, the double unlink finds no link, and the new password counts;
- two first sign-ins of one OAuth identity, two links of one identity to an account, and two invited sign-ups
  with one invite: no lock serializes them, so the unique email, the unique provider link and the invite's
  guarded redemption decide, and the second is refused or loses at its mint with nothing of its own
  committed (E121);
- one verification link posted twice at once: the second waits at the account's row, which the first's token
  read locked, finds the link burnt and is refused as an unknown link (E121).
Without the users-row lock each writer takes first, the second request writes on what it read before
the first's commit: the two refreshes leave two live successors, and a logout, logout-all, reset or
change leaves the refresh's successor live.

The account's deletion takes the same lock before its cascade deletes the tokens. Those cases start it
once a token writer holds the lock, and hold the writer there until the deletion is blocked or has
deleted something: taking the lock last, the deletion would delete the tokens first, and the writer's
token write and the deletion's own row delete would wait on each other until PostgreSQL aborted one. A
writer that waits out a deletion finds its token, or a login, change or reset the account, or an unlink
its links, gone and writes nothing (before E121's reset-and-change slice (#1727) a reset read the account
before the lock, waited at its revocation's lock instead, and its commit matched no row). Of two deletions
of one account, the second waits out the first under the lock and finds the account gone there, even with
the account loaded in its session before the first committed.
"""
import asyncio
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pytest
from starlette.requests import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import settings
from app.database import Base, SessionLocal
from app.models import AuditLog, OAuthAccount, OAuthState, RefreshToken, User
from app.routers import auth as auth_module
from app.services import auth_account_service, oauth_account_service, user_account_service
from app.services.account_agreement_service import accept_current_agreement
from app.services import refresh_token_service as tokens

HANG_GUARD_S = 5.0  # a passing case never waits for it
OLD_PASSWORD_HASH = "the old password's hash"


@pytest.fixture
def postgres_engine():
    url = os.environ.get("REFRESH_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("REFRESH_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "Refresh concurrency gate requires PostgreSQL"
    schema = f"refresh_rotation_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)  # every table: the account's deletion cascades through them
        with engine.begin() as conn:
            # Token ids apart from user ids, so a lock taken by a token's id in place of its user's fails.
            conn.execute(text("ALTER SEQUENCE refresh_tokens_id_seq RESTART WITH 1000"))
        yield engine
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine
    or connection: an autoflushing one flushes a pending write at its next query, where production waits for
    the commit, and can serialize two requests that production does not (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


def _signed_in(engine, password_hash: Optional[str] = OLD_PASSWORD_HASH) -> tuple[int, str]:
    """A user with one live refresh token; returns ``(user_id, raw_token)``."""
    with _session(engine) as db:
        user = User(email=f"reader-{uuid.uuid4().hex}@example.com", is_active=True, hashed_password=password_hash)
        db.add(user)
        db.flush()
        user_id = user.id
        _, raw_token = tokens.create_refresh_token(db, user)
        db.commit()
    return user_id, raw_token


def _stored_hashes(engine) -> list[str]:
    """Every account's password hash; a case's schema holds one account."""
    with _session(engine) as db:
        return [user.hashed_password for user in db.query(User)]


@pytest.mark.parametrize("provider", ("google", "apple"))
def test_overlapping_oauth_callbacks_consume_signup_state_once(postgres_engine, provider):
    """The first DELETE stays uncommitted until the second callback is observed waiting on its lock.

    A SELECT-then-DELETE implementation can hand both consumers the same signup assent: the
    second reads the still-visible row before waiting to delete it. Real PostgreSQL, production's
    session options and a confirmed lock wait distinguish that bug from two sequential calls.
    The actual callback also refuses missing/wrong browser binding before consuming the row.
    """
    state = f"oauth-race-{uuid.uuid4().hex}"
    agreement = accept_current_agreement()
    with _session(postgres_engine) as db:
        if provider == "google":
            oauth_account_service.save_google_state(db, state, None, agreement)
        else:
            oauth_account_service.save_apple_state(db, state, "synthetic-nonce", None, agreement)

    cookie_name = auth_module._OAUTH_STATE_COOKIE if provider == "google" else auth_module._APPLE_STATE_COOKIE
    for cookie in (None, f"{cookie_name}=wrong-browser-binding"):
        request = Request({
            "type": "http", "method": "GET" if provider == "google" else "POST",
            "path": f"/api/auth/{provider}/callback",
            "headers": [(b"cookie", cookie.encode())] if cookie else [],
        })
        with _session(postgres_engine) as db:
            if provider == "google":
                callback = auth_module.google_callback(
                    request=request, db=db, code="synthetic-code", state=state, error=None,
                )
            else:
                callback = auth_module.apple_callback(
                    request=request, db=db, code=None, state=state,
                    id_token="synthetic-token", user=None, error=None,
                )
            response = asyncio.run(callback)
            assert response.status_code == 302
            assert "error=oauth_state_mismatch" in response.headers["location"]
            assert db.query(OAuthState).filter_by(state=state).count() == 1

    role = threading.local()
    first_deleted = threading.Event()
    second_done = threading.Event()
    second_pid: list[int] = []
    released: list[str] = []
    hung: list[str] = []

    def after_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        if getattr(role, "name", None) == "first" and statement.startswith("DELETE FROM oauth_states"):
            first_deleted.set()

    def before_commit(_conn):
        if getattr(role, "name", None) != "first":
            return
        # As in the refresh races, do not raise inside engine events: leave cleanup able to
        # release the first transaction, and assert any hang only after both workers finish.
        deadline = time.monotonic() + HANG_GUARD_S
        while time.monotonic() < deadline:
            if second_done.is_set():
                released.append("done")
                return
            if second_pid:
                with postgres_engine.connect() as probe:
                    wait = probe.execute(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": second_pid[0]},
                    ).scalar()
                if wait == "Lock":
                    released.append("blocked")
                    return
            time.sleep(0.01)
        hung.append("the second state consumer to block or finish")

    def consume(name):
        role.name = name
        try:
            with _session(postgres_engine) as db:
                if name == "second":
                    if not first_deleted.wait(HANG_GUARD_S):
                        hung.append("the first state consumer to delete the row")
                        return None
                    second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar())
                return oauth_account_service.consume_oauth_state(db, state)
        finally:
            if name == "second":
                second_done.set()

    event.listen(postgres_engine, "after_cursor_execute", after_statement)
    event.listen(postgres_engine, "commit", before_commit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(consume, "first")
            second = pool.submit(consume, "second")
            first_result = first.result(timeout=3 * HANG_GUARD_S)
            second_result = second.result(timeout=3 * HANG_GUARD_S)
    finally:
        event.remove(postgres_engine, "after_cursor_execute", after_statement)
        event.remove(postgres_engine, "commit", before_commit)

    assert not hung, f"waited out the {HANG_GUARD_S} s hang guard for {hung}"
    assert released == ["blocked"], "The consumers must actually overlap before the first commit"
    assert first_result is not None
    assert first_result[1:] == (None, agreement)
    assert second_result is None
    with _session(postgres_engine) as db:
        assert db.query(OAuthState).filter_by(state=state).count() == 0
        assert oauth_account_service.consume_oauth_state(db, state) is None


def _live_tokens(engine, user_id: int) -> int:
    with _session(engine) as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None),
        ).count()


def _deletion_audits(engine) -> int:
    with _session(engine) as db:
        return db.query(AuditLog).filter(AuditLog.action == "user_deleted").count()


# The route's outcomes when no provider is configured; the deletion's audit row records them (F19).
_NO_PROVIDER_CALLS = {"stripe": "skipped", "posthog": "skipped", "sentry": "skipped"}

_OPERATIONS = {
    "refresh": lambda db, user_id, raw: tokens.rotate_and_commit(db, raw),
    "logout": lambda db, user_id, raw: tokens.revoke_and_commit(db, raw) is not None,
    "logout_all": lambda db, user_id, raw: tokens.revoke_all_and_commit(db, user_id),
    "reset": lambda db, user_id, raw: auth_account_service.complete_password_reset_by_id(
        db, user_id, "a new password's hash",
    ),
    "change_password": lambda db, user_id, raw: _change_password(db, db.get(User, user_id)),
    "change_password_again": lambda db, user_id, raw: _change_password(
        db, db.get(User, user_id), "another changed password's hash",
    ),
    "set_first_password": lambda db, user_id, raw: _change_password(
        db, db.get(User, user_id), "a first password's hash", verified_hash=None,
    ),
    "set_first_password_again": lambda db, user_id, raw: _change_password(
        db, db.get(User, user_id), "another first password's hash", verified_hash=None,
    ),
    "password_login": lambda db, user_id, raw: _password_login(db, db.get(User, user_id)),
    "delete_account": lambda db, user_id, raw: user_account_service.delete_account(
        db, user_id, third_party_results=_NO_PROVIDER_CALLS,
    ),
    "delete_loaded_account": lambda db, user_id, raw: _delete_loaded_account(db, user_id),
    "sign_in": lambda db, user_id, raw: tokens.mint_refresh_token(db, db.get(User, user_id)),
    "unlink_google": lambda db, user_id, raw: oauth_account_service.unlink_oauth_provider(db, user_id, "google"),
    "unlink_apple": lambda db, user_id, raw: oauth_account_service.unlink_oauth_provider(db, user_id, "apple"),
    "unlink_google_loaded": lambda db, user_id, raw: _unlink_loaded(db, user_id, "google"),
}
_WRITES = ("INSERT INTO refresh_tokens", "UPDATE refresh_tokens", "DELETE FROM refresh_tokens", "DELETE FROM oauth_accounts")


def _delete_loaded_account(db: Session, user_id: int) -> None:
    """A deletion whose session holds the account loaded and unexpired when it begins, as any caller holding the
    row may: a check made before the lock, or through that loaded row, would find the account there after another
    deletion committed. The row stays referenced through the deletion: the session's identity map holds an
    unchanged row weakly, so an unreferenced one is dropped and read again. The route releases its session before
    its third-party calls, so its deletion starts with nothing loaded, as ``delete_account``'s does (the base's
    route held ``current_user``, but its audit row's commit had expired it by then)."""
    account = db.get(User, user_id)
    assert account is not None, "the first deletion committed before the second loaded the account"
    return user_account_service.delete_account(db, user_id, third_party_results=_NO_PROVIDER_CALLS)


def _unlink_loaded(db: Session, user_id: int, provider: str) -> None:
    """The unlink route's unit: its session holds the account the auth lookup loaded before the unit began, as
    ``current_user``. A guard that read the password from that loaded row would see it from before the race."""
    account = db.get(User, user_id)
    assert account is not None
    return oauth_account_service.unlink_oauth_provider(db, user_id, provider)


def _password_login(db: Session, user: User) -> Optional[str]:
    """The login route's second unit, for a password that matched OLD_PASSWORD_HASH before the race:
    the session's refresh token, or None when the login is refused. The account is loaded first, which
    the route's second unit does not do (the first unit's release leaves its session empty): a re-read
    that does not refresh the loaded account would then see the hash from before the race, so the case
    also holds the service to its ``populate_existing``."""
    login = auth_account_service.record_password_login(db, user.id, OLD_PASSWORD_HASH, user.email)
    return login[1] if login is not None else None


def _change_password(
    db: Session, user: User, new_hash: str = "a changed password's hash",
    verified_hash: Optional[str] = OLD_PASSWORD_HASH,
) -> Optional[str]:
    """The change-password route's writes, for a current password that matched ``verified_hash`` before
    the race (None: an account with no password sets its first): the new hash and every token revoked,
    then the acting device's new session minted, all in the mint's one commit; or None when the change
    is refused. The account is loaded first, which the route's change unit does not do (the release before
    its waits leaves its session empty and the user detached): a re-read that does not refresh the loaded
    account would then see the hash from before the race, so the case also holds the service to its
    ``populate_existing``."""
    if not auth_account_service.stage_password_change(db, user, new_hash, verified_hash):
        return None
    return tokens.mint_refresh_token(db, user)


def _race(
    engine, first: str, second: str, *, second_starts: str = "after_first_write", second_cookie_behind: bool = False,
    password_hash: Optional[str] = OLD_PASSWORD_HASH, links: tuple[str, ...] = (),
    other_chain: Optional[list[str]] = None,
) -> tuple[object, object, int, str]:
    """Run ``first`` and ``second`` on one user's token, and return each one's result (or the exception it
    raised), the user's live tokens after both, and what let ``first`` commit: ``"blocked"`` (``second``
    was waiting on a lock) or ``"done"`` (``second`` had finished). ``second`` starts once ``first`` has
    written a token row, or with ``after_first_lock`` once ``first`` holds the users row lock, where
    ``first`` then waits until ``second`` is blocked on a lock or has written. With
    ``second_cookie_behind``, another tab has rotated the token once before either starts: ``first``
    carries the new cookie and ``second`` the one before it. ``password_hash`` is the account's at the
    start; None for one that signs in only through Google or Apple. ``links`` are the providers linked to
    the account at the start. Given ``other_chain``, the account first signs in on a second device too, and
    that session's cookie is appended to the list (E96).

    Those waits run inside engine events, which must not raise: an exception there would leave the first
    request's transaction, and its locks, on the pooled connection. A wait that outlasts the hang guard
    records itself instead, and the race fails once both requests have ended."""
    user_id, raw = _signed_in(engine, password_hash)
    if links:
        with _session(engine) as db:
            db.add_all([
                OAuthAccount(user_id=user_id, provider=provider, provider_account_id=f"{provider}-{uuid.uuid4().hex}")
                for provider in links
            ])
            db.commit()
    if other_chain is not None:
        with _session(engine) as db:
            other_chain.append(tokens.mint_refresh_token(db, db.get(User, user_id)))
    # Production's session settings, bound to this case's engine. An autoflushing session would flush a
    # pending write at the request's next query, where production waits for its commit, and could
    # serialize two requests that production does not.
    request_session = sessionmaker(**{**SessionLocal.kw, "bind": engine})
    cookies = {"first": raw, "second": raw}
    if second_cookie_behind:
        with request_session() as db:
            cookies["first"] = tokens.rotate_and_commit(db, raw)[1]
    role = threading.local()
    first_ready = threading.Event()
    second_wrote = threading.Event()
    second_done = threading.Event()
    second_pid: list[int] = []
    released: list[str] = []
    hung: list[str] = []

    def wait_until(condition, waiting_for: str) -> None:
        deadline = time.monotonic() + HANG_GUARD_S
        while not condition():
            if time.monotonic() > deadline:
                hung.append(waiting_for)
                return
            time.sleep(0.01)

    def after_statement(conn, cursor, statement, parameters, context, executemany):
        name = getattr(role, "name", None)
        if name == "second" and statement.startswith(_WRITES):
            second_wrote.set()
        if name != "first" or first_ready.is_set():
            return
        if second_starts == "after_first_write" and statement.startswith(_WRITES):
            first_ready.set()
        elif second_starts == "after_first_lock" and statement.startswith("SELECT users.id") and " FOR " in statement:
            first_ready.set()
            wait_until(lambda: second_wrote.is_set() or second_blocked(), "the second request to block or write")

    def second_blocked() -> bool:
        if not second_pid:
            return False
        with engine.connect() as probe:
            wait = probe.execute(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": second_pid[0]},
            ).scalar()
        return wait == "Lock"

    def released_by_second() -> bool:
        if second_done.is_set():
            released.append("done")
        elif second_blocked():
            released.append("blocked")
        return bool(released)

    def before_commit(conn):
        if getattr(role, "name", None) == "first":
            wait_until(released_by_second, "the second request to block or finish")

    def run(name: str, operation: str):
        role.name = name
        try:
            with request_session() as db:
                if name == "second":
                    if not first_ready.wait(HANG_GUARD_S):
                        hung.append("the first request to reach the point the second starts at")
                        return None
                    second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar())
                return _OPERATIONS[operation](db, user_id, cookies[name])
        except Exception as exc:  # noqa: BLE001 - the outcome under test may be a refusal
            return exc
        finally:
            if name == "second":
                second_done.set()

    event.listen(engine, "after_cursor_execute", after_statement)
    event.listen(engine, "commit", before_commit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(run, "first", first), pool.submit(run, "second", second)]
            first_outcome, second_outcome = (future.result(timeout=3 * HANG_GUARD_S) for future in outcomes)
    finally:
        event.remove(engine, "after_cursor_execute", after_statement)
        event.remove(engine, "commit", before_commit)
    assert not hung, f"waited out the {HANG_GUARD_S} s hang guard for {hung}"
    return first_outcome, second_outcome, _live_tokens(engine, user_id), released[0] if released else "never"


def _kind(outcome: object) -> str:
    return type(outcome).__name__


def _result(outcome: object) -> object:
    """An exception by its type's name, a refresh's tuple as "rotated", any other value as is."""
    if isinstance(outcome, BaseException):
        return _kind(outcome)
    return "rotated" if isinstance(outcome, tuple) else outcome


def test_two_refreshes_with_one_cookie_rotate_once_and_the_second_meets_the_sweep(postgres_engine):
    first, second, live, released = _race(postgres_engine, "refresh", "refresh")
    assert (_kind(first), _kind(second), live, released) == ("tuple", "RefreshTokenReuseError", 0, "blocked")


def test_two_refreshes_with_one_cookie_end_that_chain_and_leave_the_accounts_other_session_live(postgres_engine):
    """E96: the replay sweep the second refresh meets revokes its cookie's chain, the successor the first minted
    included, and nothing else, so another device's session of the same account still rotates."""
    other: list[str] = []
    first, second, live, released = _race(postgres_engine, "refresh", "refresh", other_chain=other)
    assert (_kind(first), _kind(second), live, released) == ("tuple", "RefreshTokenReuseError", 1, "blocked")
    with _session(postgres_engine) as db:
        assert _kind(tokens.rotate_and_commit(db, other[0])) == "tuple"


@pytest.mark.parametrize("first,second", [("refresh", "logout_all"), ("logout_all", "refresh")])
def test_a_refresh_and_a_logout_all_leave_no_live_token(postgres_engine, first, second):
    first_outcome, second_outcome, live, released = _race(postgres_engine, first, second)
    refresh, logout_all = (first_outcome, second_outcome) if first == "refresh" else (second_outcome, first_outcome)
    # The refresh that wins keeps its rotation until the logout-all revokes its successor; the one that
    # loses is refused, its token already revoked. Either way the logout-all revokes one token.
    assert _kind(refresh) == ("tuple" if first == "refresh" else "RefreshTokenError")
    assert (logout_all, live, released) == (1, 0, "blocked")


@pytest.mark.parametrize("first,second", [("refresh", "reset"), ("reset", "refresh")])
def test_a_refresh_and_a_password_reset_leave_no_live_token(postgres_engine, first, second):
    """Account recovery signs out every session, a successor minted by a racing refresh included. The
    reset's own users UPDATE reaches the database only at its commit, after its bulk revoke, so the lock
    it takes before it reads the account is what makes it wait for the refresh."""
    first_outcome, second_outcome, live, released = _race(postgres_engine, first, second)
    refresh, reset = (first_outcome, second_outcome) if first == "refresh" else (second_outcome, first_outcome)
    expected = "rotated" if first == "refresh" else "RefreshTokenError"
    assert (_result(refresh), _kind(reset), live, released) == (expected, "NoneType", 0, "blocked")


@pytest.mark.parametrize("first,second", [("refresh", "change_password"), ("change_password", "refresh")])
def test_a_refresh_and_a_password_change_leave_only_the_changers_new_session(postgres_engine, first, second):
    """A password change signs out every other session, a successor minted by a racing refresh included,
    and keeps the acting device's re-issued one."""
    first_outcome, second_outcome, live, released = _race(postgres_engine, first, second)
    refresh, change = (first_outcome, second_outcome) if first == "refresh" else (second_outcome, first_outcome)
    expected = "rotated" if first == "refresh" else "RefreshTokenError"
    assert (_result(refresh), _kind(change), live, released) == (expected, "str", 1, "blocked")


def test_a_refresh_after_a_logout_with_the_same_cookie_is_refused(postgres_engine):
    logout, refresh, live, released = _race(postgres_engine, "logout", "refresh")
    assert (logout, _kind(refresh), live, released) == (True, "RefreshTokenError", 0, "blocked")


def test_a_logout_after_a_refresh_with_the_same_cookie_signs_out_its_successor(postgres_engine):
    """The refresh takes the lock first and rotates the cookie's token; the logout then finds that token
    rotated and revokes the successor, whose cookie may reach the browser after the logout clears it."""
    refresh, logout, live, released = _race(postgres_engine, "refresh", "logout")
    assert (_kind(refresh), logout, live, released) == ("tuple", True, 0, "blocked")


def test_a_logout_whose_cookie_another_tab_moved_on_signs_out_the_chains_live_tip(postgres_engine):
    """Another tab rotated the token once, and its next refresh holds the lock while this logout waits
    with the cookie from before both: the logout walks the rotation links to the live tip."""
    refresh, logout, live, released = _race(postgres_engine, "refresh", "logout", second_cookie_behind=True)
    assert (_result(refresh), logout, live, released) == ("rotated", True, 0, "blocked")


@pytest.mark.parametrize("writer,result", [("refresh", "rotated"), ("logout", True), ("logout_all", 1)])
def test_an_account_deletion_waits_for_a_token_writer_holding_the_lock(postgres_engine, writer, result):
    first, deletion, live, released = _race(postgres_engine, writer, "delete_account", second_starts="after_first_lock")
    # Both finish, the writer first; the deletion then removes the account and every token.
    assert (_result(first), _kind(deletion), live, released) == (result, "NoneType", 0, "blocked")


@pytest.mark.parametrize("writer,result", [
    ("refresh", "RefreshTokenError"), ("logout", False), ("logout_all", 0), ("password_login", None),
    ("change_password", None), ("reset", "AccountTokenInvalidError"),
])
def test_a_token_writer_that_waits_out_an_account_deletion_writes_nothing(postgres_engine, writer, result):
    deletion, second, live, released = _race(postgres_engine, "delete_account", writer)
    # Its read again under the lock finds the token, or the account, gone: a refusal, as for any
    # unknown token or a password that no longer matches.
    assert (_kind(deletion), _result(second), live, released) == ("NoneType", result, 0, "blocked")


def test_a_second_deletion_of_one_account_waits_out_the_first_and_finds_it_gone(postgres_engine):
    """The second deletion starts once the first holds the account's lock, loads the account while the first
    has not committed, then waits at the lock; once the first commits, the lock's own query finds no row and
    the deletion raises, so the route answers its own 500 (the deletion-failure policy is F18's). Checked
    before the lock, or through the loaded row, it would find the account and delete nothing, answering 200.
    The first deletion's audit row commits with it, and the second, refused, commits none: one row (F19)."""
    first, second, live, released = _race(
        postgres_engine, "delete_account", "delete_loaded_account", second_starts="after_first_lock",
    )
    assert (_kind(first), _result(second), live, released) == ("NoneType", "LookupError", 0, "blocked")
    assert _deletion_audits(postgres_engine) == 1


def test_a_sign_in_does_not_wait_for_a_rotation_holding_the_lock(postgres_engine):
    """FOR NO KEY UPDATE serializes the token writers but not the foreign-key check of a new token's insert:
    a sign-in finishes while a refresh holds the account's lock."""
    refresh, sign_in, live, released = _race(postgres_engine, "refresh", "sign_in")
    assert (_result(refresh), _kind(sign_in), live, released) == ("rotated", "str", 2, "done")


def _links(engine) -> list[str]:
    """The providers linked to any account in the case's schema, which holds the one account its race made."""
    with _session(engine) as db:
        return sorted(provider for (provider,) in db.query(OAuthAccount.provider))


def test_two_unlinks_of_an_account_with_no_password_leave_its_last_sign_in_method(postgres_engine):
    """Google and Apple unlinked at once from an account with no password: two clicks on the settings page, which
    tracks each provider's request on its own, or two tabs. The second starts once the first has deleted its link,
    waits at the account's users row lock for the first's commit, then counts one link left and refuses (E121). In
    the thread pool without the lock, both read two links, both pass the guard, and the account is left with no
    way to sign in; on the event loop they could not interleave."""
    first, second, _, released = _race(
        postgres_engine, "unlink_google", "unlink_apple", password_hash=None, links=("google", "apple"),
    )
    assert (_kind(first), _result(second), released, _links(postgres_engine)) == (
        "NoneType", "LastSignInMethodError", "blocked", ["apple"],
    )


def test_a_second_unlink_of_one_provider_waits_out_the_first_and_finds_it_gone(postgres_engine):
    """A double click on Unlink: the second request waits at the lock, then finds no link and refuses, so the route
    answers 404 and writes no second audit row. Without the lock it read the link, deleted it again, matching no
    row, and answered 200."""
    first, second, _, released = _race(postgres_engine, "unlink_google", "unlink_google", links=("google",))
    assert (_kind(first), _result(second), released, _links(postgres_engine)) == (
        "NoneType", "ProviderNotLinkedError", "blocked", [],
    )


def test_an_unlink_that_waits_out_a_first_password_counts_the_password(postgres_engine):
    """An account with no password and one link sets its first password while an unlink of that link waits at the
    lock, its session holding the account as loaded before. The unlink reads the password under the lock, finds
    it and unlinks; read from the loaded account it would find none and refuse the last sign-in method."""
    password, unlink, live, released = _race(
        postgres_engine, "set_first_password", "unlink_google_loaded", password_hash=None, links=("google",),
    )
    assert (_kind(password), _kind(unlink), live, released, _links(postgres_engine)) == (
        "str", "NoneType", 1, "blocked", [],
    )


def test_an_unlink_that_waits_out_an_account_deletion_finds_no_link(postgres_engine):
    """An unlink while the account is being deleted waits at the lock the deletion holds, then finds the account's
    links gone with it and refuses: no 200 and no audit row for an account that no longer exists."""
    deletion, unlink, live, released = _race(postgres_engine, "delete_account", "unlink_google", links=("google",))
    assert (_kind(deletion), _result(unlink), live, released, _links(postgres_engine)) == (
        "NoneType", "ProviderNotLinkedError", 0, "blocked", [],
    )


def _oauth_sign_in(db: Session, subject: str, email: str, invite_hash: Optional[str] = None):
    """A Google callback's sign-in unit as far as its commit: the resolve, then the mint."""
    user, _linked, _created = oauth_account_service.resolve_google_user(
        db, subject=subject, email=email, email_verified=True, full_name=None,
        invite_code_hash=invite_hash, agreement=accept_current_agreement(),
    )
    return oauth_account_service.mint_oauth_refresh_token(db, user, user_agent=None, ip=None)


def _second_sign_in_while_the_first_holds(engine, first: tuple, second: tuple) -> tuple[object, str]:
    """Resolve ``first`` (subject, email, invite hash) in one session, run ``second``'s whole sign-in in another
    thread until PostgreSQL shows it waiting on a lock, then mint and commit ``first``. Returns what ``second``
    returned or raised, and the statement it waited at ("" if it never waited)."""
    outcome: list[object] = []
    second_pid: list[int] = []

    def run_second() -> None:
        with _session(engine) as db:
            second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar())
            try:
                outcome.append(_oauth_sign_in(db, *second))
            except Exception as exc:  # noqa: BLE001 - the outcome under test may be a refusal
                outcome.append(exc)

    with _session(engine) as db:
        user, _linked, _created = oauth_account_service.resolve_google_user(
            db, subject=first[0], email=first[1], email_verified=True, full_name=None,
            invite_code_hash=first[2], agreement=accept_current_agreement(),
        )
        db.flush()  # the staged link, assent and last_login_at, uncommitted, as the mint's own flush would send them
        thread = threading.Thread(target=run_second)
        thread.start()
        deadline, waited = time.monotonic() + HANG_GUARD_S, ""
        while not waited and time.monotonic() < deadline and thread.is_alive():
            if second_pid:
                with engine.connect() as probe:
                    row = probe.execute(
                        text("SELECT wait_event_type, query FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": second_pid[0]},
                    ).first()
                if row is not None and row.wait_event_type == "Lock":
                    waited = row.query.strip()
            time.sleep(0.01)
        oauth_account_service.mint_oauth_refresh_token(db, user, user_agent=None, ip=None)
    thread.join(HANG_GUARD_S)
    assert not thread.is_alive(), "the second sign-in outlasted the hang guard"
    return outcome[0], waited


def _accounts_links_tokens(engine) -> tuple[int, int, int]:
    with _session(engine) as db:
        return db.query(User).count(), db.query(OAuthAccount).count(), db.query(RefreshToken).count()


def test_two_first_sign_ins_of_one_identity_create_one_account(postgres_engine, collection_ready, monkeypatch):
    """Two callbacks for one new Google identity, from two browsers. No lock serializes them, in the thread pool on
    one instance or across instances (E121): the second's account insert waits on the first's uncommitted row
    under the unique email, then fails, and the resolve refuses it as the lost create race, so the route redirects
    to its conflict page with nothing of its own committed: one account, one link, one session."""
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    email = f"twice-{uuid.uuid4().hex}@example.com"
    second, waited = _second_sign_in_while_the_first_holds(
        postgres_engine, ("google-subject", email, None), ("google-subject", email, None),
    )
    assert isinstance(second, oauth_account_service.OAuthSignInRefused)
    assert (second.lost_create_race, second.error_code) == (True, "google_account_conflict")
    assert waited.startswith("INSERT INTO users"), waited
    assert _accounts_links_tokens(postgres_engine) == (1, 1, 1)


def test_two_links_of_one_identity_to_an_account_link_it_once(postgres_engine, collection_ready):
    """Two callbacks for one Google identity whose address is a verified account's, from two browsers: both resolve
    a link to that account. The second's mint waits at the account's row for the first's commit, then its link
    insert meets the first's under ``uq_oauth_provider_account``, and the mint rolls it back as the conflict: one
    link, one session, and the second's redirect to the conflict page."""
    email = f"link-{uuid.uuid4().hex}@example.com"
    with _session(postgres_engine) as db:
        db.add(User(email=email, is_active=True, email_verified=True))
        db.commit()
    second, waited = _second_sign_in_while_the_first_holds(
        postgres_engine, ("google-subject", email, None), ("google-subject", email, None),
    )
    assert isinstance(second, oauth_account_service.OAuthAccountConflictError)
    assert waited.startswith("UPDATE users"), waited
    assert _accounts_links_tokens(postgres_engine) == (1, 1, 1)


def test_two_invited_sign_ups_with_one_invite_redeem_it_once(postgres_engine, collection_ready, monkeypatch):
    """Two new identities signing up under invite_only with one invite: the second's guarded redemption waits on
    the first's uncommitted one, then matches no unused invite, and the resolve refuses it (``invite_required``).
    One account, one link, one session, the invite redeemed once."""
    from app.models.invite import InviteCode
    from app.services import invite_service

    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    with _session(postgres_engine) as db:
        _row, raw, _link = invite_service.mint_invite(db, created_by=None)
    invite_hash = invite_service.hash_invite_token(raw)
    second, waited = _second_sign_in_while_the_first_holds(
        postgres_engine,
        ("google-first", f"first-{uuid.uuid4().hex}@example.com", invite_hash),
        ("google-second", f"second-{uuid.uuid4().hex}@example.com", invite_hash),
    )
    assert isinstance(second, oauth_account_service.OAuthSignInRefused)
    assert second.error_code == "invite_required"
    assert waited.startswith("UPDATE invite_codes"), waited
    assert _accounts_links_tokens(postgres_engine) == (1, 1, 1)
    with _session(postgres_engine) as db:
        assert db.query(InviteCode).filter(InviteCode.used_at.isnot(None)).count() == 1


def test_two_verifications_of_one_link_verify_it_once(postgres_engine):
    """One verification link posted twice at once (a double click, or React's development double effect): the
    second's token read waits at the account's row, which the first's read locked, until the first commits, then
    finds the link burnt and refuses it as an unknown link, so the route answers the link's 400, as the event loop's
    one-at-a-time order did on one instance (E121). Without the lock both read the link and both verified, and with
    the reverse trial on the second logged a failed grant or sent a second trial-started event."""
    email = f"verify-{uuid.uuid4().hex}@example.com"
    with _session(postgres_engine) as db:
        account = User(email=email, is_active=True, email_verified=False,
                       email_verification_token=auth_account_service._hash_token("the-link"))
        db.add(account)
        db.commit()
        user_id = account.id
    role = threading.local()
    first_locked = threading.Event()
    second_pid: list[int] = []
    second_statements: list[str] = []
    waited: list[str] = []

    def before_statement(conn, cursor, statement, parameters, context, executemany):
        if getattr(role, "name", None) == "second":
            second_statements.append(statement)

    def after_statement(conn, cursor, statement, parameters, context, executemany):
        if getattr(role, "name", None) == "first" and " FOR NO KEY UPDATE" in statement:
            first_locked.set()

    def before_commit(conn):
        # The first commits only once PostgreSQL shows the second waiting on a lock, or at the hang guard.
        if getattr(role, "name", None) != "first":
            return
        deadline = time.monotonic() + HANG_GUARD_S
        while not waited and time.monotonic() < deadline:
            with postgres_engine.connect() as probe:
                row = probe.execute(
                    text("SELECT wait_event_type, query FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": second_pid[0]},
                ).first() if second_pid else None
            if row is not None and row.wait_event_type == "Lock":
                waited.append(second_statements[-1])  # the statement it waits at, whole, as it started
            else:
                time.sleep(0.01)

    def run(name: str) -> object:
        role.name = name
        with _session(postgres_engine) as db:
            if name == "second":
                first_locked.wait(HANG_GUARD_S)
                second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar())
            try:
                return auth_account_service.verify_email_token(db, "the-link")
            except Exception as exc:  # noqa: BLE001 - the outcome under test may be a refusal
                return exc

    event.listen(postgres_engine, "before_cursor_execute", before_statement)
    event.listen(postgres_engine, "after_cursor_execute", after_statement)
    event.listen(postgres_engine, "commit", before_commit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, "first"), pool.submit(run, "second")]
            first, second = (future.result(timeout=3 * HANG_GUARD_S) for future in futures)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", before_statement)
        event.remove(postgres_engine, "after_cursor_execute", after_statement)
        event.remove(postgres_engine, "commit", before_commit)
    assert isinstance(first, tuple) and first[1] == user_id
    assert isinstance(second, auth_account_service.AccountTokenInvalidError), second
    # The second waited at its own locking token read (recorded whole as it started; pg_stat_activity, which cuts a
    # statement at track_activity_query_size, only shows the wait).
    assert waited and waited[0].startswith("SELECT users."), waited
    assert "WHERE users.email_verification_token" in waited[0], waited
    assert waited[0].rstrip().endswith("FOR NO KEY UPDATE"), waited
    with _session(postgres_engine) as db:
        verified = db.get(User, user_id)
        assert (verified.email_verified, verified.email_verification_token) == (True, None)


@pytest.mark.parametrize("revocation,result,live_after", [("reset", "NoneType", 0), ("change_password", "str", 1)])
def test_a_password_login_that_verified_the_old_password_mints_nothing_once_it_changes(
    postgres_engine, revocation, result, live_after,
):
    """A reset or change holds the lock while a login that verified the old password before it committed
    waits: the login finds the hash changed and mints nothing (E121), so the reset leaves no live token
    and the change only the changer's."""
    first, login, live, released = _race(postgres_engine, revocation, "password_login")
    assert (_kind(first), login, live, released) == (result, None, live_after, "blocked")


def test_two_password_logins_of_one_account_wait_for_each_other_and_both_mint(postgres_engine):
    """A login holds the account's lock from its re-check to its commit, so a second login of the same
    account, started once the first holds it, waits, then finds the hash unchanged and mints too, and
    both sessions are live beside the one from before. A lock two logins could share (FOR SHARE) would
    let both reach their users UPDATE and deadlock there."""
    first, second, live, released = _race(
        postgres_engine, "password_login", "password_login", second_starts="after_first_lock",
    )
    assert (_kind(first), _kind(second), live, released) == ("str", "str", 3, "blocked")


@pytest.mark.parametrize("revocation,result,live_after", [("reset", "NoneType", 0), ("change_password", "str", 1)])
def test_a_reset_or_change_after_a_password_login_signs_out_its_new_session(
    postgres_engine, revocation, result, live_after,
):
    """The login takes the lock first and mints; the reset or change waits for its commit, and its
    revocation then reaches the login's new token too."""
    login, second, live, released = _race(postgres_engine, "password_login", revocation)
    assert (_kind(login), _kind(second), live, released) == ("str", result, live_after, "blocked")


@pytest.mark.parametrize("first,second", [("reset", "change_password"), ("change_password", "reset")])
def test_a_reset_and_a_password_change_leave_the_resets_password_and_no_live_token(postgres_engine, first, second):
    """Account recovery wins in either order. A change that verified the old password before the reset
    committed waits for the reset's lock, then finds the hash changed and writes nothing (E121); a change
    that holds the lock first commits, and the reset that waited replaces its password and revokes its
    session."""
    first_outcome, second_outcome, live, released = _race(postgres_engine, first, second)
    reset, change = (first_outcome, second_outcome) if first == "reset" else (second_outcome, first_outcome)
    assert (_kind(reset), _kind(change), live, released) == (
        "NoneType", "NoneType" if first == "reset" else "str", 0, "blocked",
    )
    assert _stored_hashes(postgres_engine) == ["a new password's hash"]


def test_two_first_passwords_set_at_once_leave_the_first(postgres_engine):
    """An account with no password (it signs in only through Google or Apple) sets one in two requests at
    once. Each found no password to check; the one that waits for the other's lock finds a hash now and
    writes nothing (E121), so the first password and its session stand."""
    first, second, live, released = _race(
        postgres_engine, "set_first_password", "set_first_password_again", password_hash=None,
    )
    assert (_kind(first), second, live, released) == ("str", None, 1, "blocked")
    assert _stored_hashes(postgres_engine) == ["a first password's hash"]


def test_a_password_change_that_verified_the_old_password_writes_nothing_once_another_commits(postgres_engine):
    """Two changes verified the old password; the one that waits for the other's lock finds the hash
    changed and writes nothing (E121), so the first change's password and session stand."""
    first, second, live, released = _race(postgres_engine, "change_password", "change_password_again")
    assert (_kind(first), second, live, released) == ("str", None, 1, "blocked")
    assert _stored_hashes(postgres_engine) == ["a changed password's hash"]

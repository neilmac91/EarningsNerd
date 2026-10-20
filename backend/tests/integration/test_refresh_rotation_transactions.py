"""Real PostgreSQL races for refresh-token rotation and revocation (E127); behavioral cases stay in the
unit home.

REFRESH_CONCURRENCY_TEST_DATABASE_URL enables this required CI gate. A configured invalid or
unavailable database fails; every case owns a disposable schema and never changes public tables.

A rotation reads its token, checks that it is live, mints a successor and marks the token rotated; a
logout and a logout-all revoke what they read as live. Since #1394 runs them in the thread pool, and
always across the API's two instances, two of them can interleave inside those steps. Each case runs
two of them on one user's token. The first holds its COMMIT until the second is blocked on a lock or has
finished, so the second makes its first read, and its check if nothing stops it, while the first's
writes are uncommitted:
- two refreshes with one cookie: one rotates, and the other meets the replay sweep, as the second of
  two did when refresh ran on the event loop, so no live token is left;
- a refresh and a logout-all, in either order: no live token is left;
- a logout, then a refresh with the same cookie: the refresh is refused and no live token is left;
- a refresh, then a logout with the same cookie: the logout signs out the successor the refresh minted.
Without the users-row lock each writer takes first, the second request writes on what it read before
the first's commit: the two refreshes leave two live successors, and a logout or logout-all leaves the
refresh's successor live.

The account's deletion takes the same lock before its cascade deletes the tokens. Those cases start it
once a token writer holds the lock, and hold the writer there until the deletion is blocked or has
deleted something: taking the lock last, the deletion would delete the tokens first, and the writer's
token write and the deletion's own row delete would wait on each other until PostgreSQL aborted one. A
writer that waits out a deletion finds its token gone and writes nothing.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base
from app.models import RefreshToken, User
from app.services import refresh_token_service as tokens
from app.services import user_account_service

HANG_GUARD_S = 5.0  # a passing case never waits for it


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
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _signed_in(engine) -> tuple[int, str]:
    """A user with one live refresh token; returns ``(user_id, raw_token)``."""
    with Session(engine) as db:
        user = User(email=f"reader-{uuid.uuid4().hex}@example.com", is_active=True)
        db.add(user)
        db.flush()
        user_id = user.id
        _, raw_token = tokens.create_refresh_token(db, user)
        db.commit()
    return user_id, raw_token


def _live_tokens(engine, user_id: int) -> int:
    with Session(engine) as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None),
        ).count()


_OPERATIONS = {
    "refresh": lambda db, user_id, raw: tokens.rotate_and_commit(db, raw),
    "logout": lambda db, user_id, raw: tokens.revoke_and_commit(db, raw),
    "logout_all": lambda db, user_id, raw: tokens.revoke_all_and_commit(db, user_id),
    "delete_account": lambda db, user_id, raw: user_account_service.delete_user(db, db.get(User, user_id)),
}
_WRITES = ("INSERT INTO refresh_tokens", "UPDATE refresh_tokens", "DELETE FROM refresh_tokens")


def _race(engine, first: str, second: str, *, second_starts: str = "after_first_write") -> tuple[object, object, int]:
    """Run ``first`` and ``second`` on one user's token, and return each one's result (or the exception it
    raised) and the user's live tokens after both. ``second`` starts once ``first`` has written a token
    row, or with ``after_first_lock`` once ``first`` holds the users row lock, where ``first`` then waits
    until ``second`` is blocked on a lock or has written. ``first`` commits only once ``second`` is
    blocked on a lock or done."""
    user_id, raw = _signed_in(engine)
    role = threading.local()
    first_ready = threading.Event()
    second_wrote = threading.Event()
    second_done = threading.Event()
    second_pid: list[int] = []

    def wait_until(condition, failure: str) -> None:
        deadline = time.monotonic() + HANG_GUARD_S
        while not condition():
            assert time.monotonic() < deadline, failure
            time.sleep(0.01)

    def after_statement(conn, cursor, statement, parameters, context, executemany):
        name = getattr(role, "name", None)
        if name == "second" and statement.startswith(_WRITES):
            second_wrote.set()
        if name != "first" or first_ready.is_set():
            return
        if second_starts == "after_first_write" and statement.startswith(_WRITES):
            first_ready.set()
        elif second_starts == "after_first_lock" and "FOR NO KEY UPDATE" in statement:
            first_ready.set()
            wait_until(lambda: second_wrote.is_set() or second_blocked(), "the second request neither blocked nor wrote")

    def second_blocked() -> bool:
        if not second_pid:
            return False
        with engine.connect() as probe:
            wait = probe.execute(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": second_pid[0]},
            ).scalar()
        return wait == "Lock"

    def before_commit(conn):
        if getattr(role, "name", None) == "first":
            wait_until(lambda: second_done.is_set() or second_blocked(), "the second request neither blocked nor finished")

    def run(name: str, operation: str):
        role.name = name
        try:
            with Session(engine) as db:
                if name == "second":
                    assert first_ready.wait(HANG_GUARD_S), "the first request never reached the point the second starts at"
                    second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar())
                return _OPERATIONS[operation](db, user_id, raw)
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
    return first_outcome, second_outcome, _live_tokens(engine, user_id)


def _kind(outcome: object) -> str:
    return type(outcome).__name__


def _result(outcome: object) -> object:
    """An exception by its type's name, a refresh's (user, cookie) as "rotated", any other value as is."""
    if isinstance(outcome, BaseException):
        return _kind(outcome)
    return "rotated" if isinstance(outcome, tuple) else outcome


def test_two_refreshes_with_one_cookie_rotate_once_and_the_second_meets_the_sweep(postgres_engine):
    first, second, live = _race(postgres_engine, "refresh", "refresh")
    assert (_kind(first), _kind(second), live) == ("tuple", "RefreshTokenReuseError", 0)


@pytest.mark.parametrize("first,second", [("refresh", "logout_all"), ("logout_all", "refresh")])
def test_a_refresh_and_a_logout_all_leave_no_live_token(postgres_engine, first, second):
    first_outcome, second_outcome, live = _race(postgres_engine, first, second)
    refresh = first_outcome if first == "refresh" else second_outcome
    # The refresh that wins keeps its rotation until the logout-all revokes its successor; the one that
    # loses is refused, its token already revoked.
    assert _kind(refresh) == ("tuple" if first == "refresh" else "RefreshTokenError")
    assert live == 0


def test_a_refresh_after_a_logout_with_the_same_cookie_is_refused(postgres_engine):
    logout, refresh, live = _race(postgres_engine, "logout", "refresh")
    assert (logout, _kind(refresh), live) == (True, "RefreshTokenError", 0)


def test_a_logout_after_a_refresh_with_the_same_cookie_signs_out_its_successor(postgres_engine):
    """The refresh takes the lock first and rotates the cookie's token; the logout then finds that token
    rotated and revokes the successor, whose cookie may reach the browser after the logout clears it."""
    refresh, logout, live = _race(postgres_engine, "refresh", "logout")
    assert (_kind(refresh), logout, live) == ("tuple", True, 0)


@pytest.mark.parametrize("writer,result", [("refresh", "rotated"), ("logout", True), ("logout_all", 1)])
def test_an_account_deletion_waits_for_a_token_writer_holding_the_lock(postgres_engine, writer, result):
    first, deletion, live = _race(postgres_engine, writer, "delete_account", second_starts="after_first_lock")
    # Both finish, the writer first; the deletion then removes the account and every token.
    assert (_result(first), _kind(deletion), live) == (result, "NoneType", 0)


@pytest.mark.parametrize("writer,result", [("refresh", "RefreshTokenError"), ("logout", False), ("logout_all", 0)])
def test_a_token_writer_that_waits_out_an_account_deletion_writes_nothing(postgres_engine, writer, result):
    deletion, second, live = _race(postgres_engine, "delete_account", writer)
    # Its read again under the lock finds the token gone: a refusal, as for any unknown token.
    assert (_kind(deletion), _result(second), live) == ("NoneType", result, 0)

"""Real PostgreSQL races for failed-login recording; behavioral cases stay in the existing unit home.

LOGIN_CONCURRENCY_TEST_DATABASE_URL enables this required CI gate. A configured invalid or
unavailable database fails; every case owns a disposable schema and never changes public tables.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base
from app.models import LoginAttempt
from app.services import login_lockout as lockout


@pytest.fixture
def postgres_engine():
    url = os.environ.get("LOGIN_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("LOGIN_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "Login concurrency gate requires PostgreSQL"
    schema = f"login_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine, tables=[LoginAttempt.__table__])
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _seed(engine, email, scenario):
    if scenario == "absent":
        return
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(LoginAttempt(
            email_hash=lockout._email_hash(email),
            failed_count=8 if scenario == "current" else 10,
            locked_until=now - timedelta(seconds=1) if scenario == "expired_lock" else None,
            updated_at=now - timedelta(seconds=lockout.LOCKOUT_SECONDS + 1) if scenario == "stale_window" else now,
        ))
        db.commit()


@pytest.mark.parametrize("scenario", ["absent", "current", "expired_lock", "stale_window"])
def test_parallel_failures_count_every_commit_across_initial_and_reset_states(postgres_engine, scenario):
    email = f"ghost-{uuid.uuid4().hex}@example.com"
    _seed(postgres_engine, email, scenario)
    first_writes = threading.Barrier(3, timeout=5)
    local = threading.local()

    def before_write(conn, cursor, statement, parameters, context, executemany):
        if getattr(local, "first", False) and statement.startswith(("INSERT INTO login_attempts", "UPDATE login_attempts")):
            local.first = False
            first_writes.wait()

    def fail_login():
        with Session(postgres_engine) as db:
            stale = db.query(LoginAttempt).filter_by(email_hash=lockout._email_hash(email)).first()
            local.first = True
            lockout.record_failure(db, email)
            if stale is not None:
                assert stale.email_hash  # keep the old identity-map value through the write

    event.listen(postgres_engine, "before_cursor_execute", before_write)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(fail_login) for _ in range(3)]
            for future in futures:
                future.result(timeout=6)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", before_write)
    with Session(postgres_engine) as db:
        row = db.query(LoginAttempt).one()
        assert row.failed_count == (11 if scenario == "current" else 3)
        remaining = lockout.seconds_until_unlock(db, email)
        if scenario == "current":
            assert remaining is not None and 0 < remaining <= lockout.LOCKOUT_SECONDS
        else:
            assert remaining is None


@pytest.mark.parametrize("commit_clear", [True, False])
def test_failure_waiting_on_success_clear_records_against_committed_state(postgres_engine, commit_clear):
    email = f"clear-{uuid.uuid4().hex}@example.com"
    _seed(postgres_engine, email, "current")  # eight recorded failures
    entered = threading.Event()
    finished = threading.Event()

    def before_write(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith(("INSERT INTO login_attempts", "UPDATE login_attempts")):
            entered.set()

    def fail_login():
        try:
            with Session(postgres_engine) as db:
                lockout.record_failure(db, email)
        finally:
            finished.set()

    with Session(postgres_engine) as success:
        lockout.clear_failures(success, email)  # uncommitted caller-owned delete holds the key
        event.listen(postgres_engine, "before_cursor_execute", before_write)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(fail_login)
                try:
                    assert entered.wait(5), "failure did not reach its database write"
                    assert not finished.wait(0.1), "failure passed an uncommitted clear"
                finally:
                    if commit_clear:
                        success.commit()
                    else:
                        success.rollback()
                future.result(timeout=6)
        finally:
            event.remove(postgres_engine, "before_cursor_execute", before_write)
    with Session(postgres_engine) as db:
        row = db.query(LoginAttempt).one()
        # A committed clear starts a new failure history; a rolled-back success cannot erase it.
        assert row.failed_count == (1 if commit_clear else 9)
        assert lockout.seconds_until_unlock(db, email) is None

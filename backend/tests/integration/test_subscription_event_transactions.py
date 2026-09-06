"""Webhook transaction ownership plus real PostgreSQL per-account serialization.

Set STRIPE_CONCURRENCY_TEST_DATABASE_URL to an isolated PostgreSQL test database. Only the
PostgreSQL cases skip when absent; an invalid/unavailable configured database fails the gate.
Every PostgreSQL fixture owns a disposable schema and never changes public tables.
"""
import asyncio
import json
import os
import threading
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from starlette.requests import Request

from app import database
from app.database import Base
from app.models import StripeEvent, Subscription, User
from app.routers import subscriptions
from app.services import subscription_sync, subscription_webhook_service as service


TABLES = [User.__table__, Subscription.__table__, StripeEvent.__table__]


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'webhooks.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=TABLES)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_engine():
    url = os.environ.get("STRIPE_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("STRIPE_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "Concurrency gate requires PostgreSQL"
    schema = f"stripe_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine, tables=TABLES)
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture(autouse=True)
def stripe_boundary(monkeypatch):
    monkeypatch.setattr(subscriptions.stripe.Webhook, "construct_event", lambda *args: object())
    monkeypatch.setattr(service, "capture_event", lambda *args: None)


def _install_factory(monkeypatch, engine, cls=Session):
    factory = sessionmaker(bind=engine, class_=cls, autoflush=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    return factory


def _seed(engine):
    with Session(engine) as db:
        user = User(email=f"{uuid.uuid4().hex}@example.com", email_verified=True, stripe_customer_id="cus_test")
        db.add(user)
        db.commit()
        return user.id


def _event(user_id, kind="checkout.session.completed", event_id=None):
    obj = {"id": "sub_test", "customer": "cus_test", "status": "active"}
    if kind == "checkout.session.completed":
        obj = {"subscription": "sub_test", "customer": "cus_test", "metadata": {"user_id": str(user_id)}}
    return {"id": event_id or f"evt_{uuid.uuid4().hex}", "type": kind, "data": {"object": obj}}


async def _deliver(payload):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/api/subscriptions/webhook", "headers": []}, receive)
    return await subscriptions.stripe_webhook(request, stripe_signature="verified-test-signature")


def _billing(engine, user_id):
    with Session(engine) as db:
        user = db.get(User, user_id)
        sub = db.query(Subscription).filter_by(user_id=user_id).first()
        return (user.is_pro, sub.status if sub else None,
                db.query(Subscription).count(), db.query(StripeEvent).count())


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_commit", [False, True])
async def test_worker_owns_session_sql_and_cleanup(sqlite_engine, monkeypatch, fail_commit):
    user_id = _seed(sqlite_engine)
    loop_thread = threading.get_ident()
    operations = []

    class ObservedSession(Session):
        def __init__(self, *args, **kwargs):
            operations.append(("construct", threading.get_ident()))
            super().__init__(*args, **kwargs)

        def commit(self):
            operations.append(("commit", threading.get_ident()))
            if fail_commit:
                self.flush()
                raise RuntimeError("forced commit failure")
            return super().commit()

        def rollback(self):
            operations.append(("rollback", threading.get_ident()))
            return super().rollback()

        def close(self):
            operations.append(("close", threading.get_ident()))
            return super().close()

    _install_factory(monkeypatch, sqlite_engine, ObservedSession)

    def record_sql(*args):
        operations.append(("sql", threading.get_ident()))

    sqlalchemy_event.listen(sqlite_engine, "before_cursor_execute", record_sql)
    try:
        if fail_commit:
            with pytest.raises(HTTPException) as error:
                await _deliver(_event(user_id))
            assert error.value.status_code == 500
        else:
            assert await _deliver(_event(user_id)) == {"status": "success"}
    finally:
        sqlalchemy_event.remove(sqlite_engine, "before_cursor_execute", record_sql)
    names = [name for name, _ in operations]
    assert names[0] == "construct" and names[-1] == "close"
    assert "sql" in names and "commit" in names
    assert ("rollback" in names) is fail_commit
    assert len({thread for _, thread in operations}) == 1, operations
    assert all(thread != loop_thread for _, thread in operations), "webhook DB lifecycle ran on the event loop"
    assert _billing(sqlite_engine, user_id) == ((False, None, 0, 0) if fail_commit else (True, "active", 1, 1))


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_ledger", [False, True])
async def test_state_and_ledger_commit_before_analytics(sqlite_engine, monkeypatch, fail_ledger):
    user_id = _seed(sqlite_engine)
    closed = threading.Event()
    captures = []

    class ObservedSession(Session):
        def close(self):
            super().close()
            closed.set()

    _install_factory(monkeypatch, sqlite_engine, ObservedSession)

    def capture(*args):
        captures.append((closed.is_set(), _billing(sqlite_engine, user_id)))

    monkeypatch.setattr(service, "capture_event", capture)
    if fail_ledger:
        def fail(db, *_):
            db.flush()  # prove already-flushed state rolls back with the event ledger
            raise RuntimeError("forced ledger failure")
        monkeypatch.setattr(subscription_sync, "mark_event_processed", fail)
        with pytest.raises(HTTPException) as error:
            await _deliver(_event(user_id))
        assert error.value.status_code == 500
        assert _billing(sqlite_engine, user_id) == (False, None, 0, 0)
        assert captures == []
    else:
        assert await _deliver(_event(user_id)) == {"status": "success"}
        assert captures == [(True, (True, "active", 1, 1))], "analytics preceded atomic commit/session closure"


@pytest.mark.asyncio
async def test_cancelled_request_leaves_cleanup_with_running_worker(sqlite_engine, monkeypatch):
    user_id = _seed(sqlite_engine)
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    finished = threading.Event()
    operations = []

    class ObservedSession(Session):
        def __init__(self, *args, **kwargs):
            operations.append(("construct", threading.get_ident()))
            super().__init__(*args, **kwargs)

        def commit(self):
            operations.append(("commit", threading.get_ident()))
            return super().commit()

        def close(self):
            operations.append(("close", threading.get_ident()))
            super().close()
            closed.set()

    _install_factory(monkeypatch, sqlite_engine, ObservedSession)
    original = service._apply_event

    def blocked(*args):
        entered.set()
        assert release.wait(5), "test did not release webhook worker"
        return original(*args)

    monkeypatch.setattr(service, "_apply_event", blocked)

    def finish_worker(payload):
        try:
            return service.process_stripe_event(payload)
        finally:
            finished.set()

    monkeypatch.setattr(subscriptions, "process_stripe_event", finish_worker)
    task = asyncio.create_task(_deliver(_event(user_id)))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not closed.is_set(), "request cancellation closed the running worker's session"
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(finished.wait, 5)
        assert closed.is_set()
    assert [name for name, _ in operations] == ["construct", "commit", "close"]
    assert len({thread for _, thread in operations}) == 1
    assert operations[0][1] != threading.get_ident()
    assert _billing(sqlite_engine, user_id) == (True, "active", 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["checkout.session.completed", "customer.subscription.updated", "customer.subscription.deleted"])
async def test_postgres_account_contention_is_retryable_without_mutation(postgres_engine, monkeypatch, kind):
    user_id = _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    # Seed a current subscription for update/deletion; checkout explicitly covers first creation.
    if kind != "checkout.session.completed":
        await _deliver(_event(user_id))
    before = _billing(postgres_engine, user_id)
    payload = _event(user_id, kind)
    with Session(postgres_engine) as holder:
        holder.query(User).filter_by(id=user_id).with_for_update().one()
        with pytest.raises(HTTPException) as error:
            await _deliver(payload)
        assert error.value.status_code == 503
        assert _billing(postgres_engine, user_id) == before
        holder.rollback()
    assert await _deliver(payload) == {"status": "success"}
    assert _billing(postgres_engine, user_id)[3] == before[3] + 1
    # Retrying after success sees the committed ledger under the account lock.
    assert await _deliver(payload) == {"status": "success", "idempotent": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("same_event", [False, True])
async def test_postgres_concurrent_first_subscription_retries_without_duplicate_rows(postgres_engine, monkeypatch, same_event):
    user_id = _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    entered, release = threading.Event(), threading.Event()
    original = service._apply_event
    first_payload = _event(user_id)
    second_payload = first_payload if same_event else _event(user_id)

    def hold_first(*args):
        if not entered.is_set():
            entered.set()
            assert release.wait(5), "test did not release first delivery"
        return original(*args)

    monkeypatch.setattr(service, "_apply_event", hold_first)
    first = asyncio.create_task(_deliver(first_payload))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        assert _billing(postgres_engine, user_id) == (False, None, 0, 0)
        with pytest.raises(HTTPException) as error:
            await _deliver(second_payload)
        assert error.value.status_code == 503
        assert _billing(postgres_engine, user_id) == (False, None, 0, 0)
    finally:
        release.set()
        assert await first == {"status": "success"}
    expected = {"status": "success", "idempotent": True} if same_event else {"status": "success"}
    assert await _deliver(second_payload) == expected
    assert _billing(postgres_engine, user_id) == (True, "active", 1, 1 if same_event else 2)


@pytest.mark.asyncio
async def test_postgres_owner_is_rechecked_after_account_lock(postgres_engine, monkeypatch):
    user_id = _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    with Session(postgres_engine) as db:
        other = User(email="other@example.com", email_verified=True)
        db.add(other)
        db.commit()
        other_id = other.id
    original = service._event_owner_id
    changed = False

    def resolve_then_change(db, kind, obj):
        nonlocal changed
        result = original(db, kind, obj)
        if not changed:
            changed = True
            with Session(postgres_engine) as writer:
                writer.get(User, user_id).stripe_customer_id = None
                writer.get(User, other_id).stripe_customer_id = "cus_test"
                writer.commit()
        return result

    monkeypatch.setattr(service, "_event_owner_id", resolve_then_change)
    with pytest.raises(HTTPException) as error:
        await _deliver(_event(user_id, "customer.subscription.updated"))
    assert error.value.status_code == 503
    assert _billing(postgres_engine, user_id) == (False, None, 0, 0)
    assert _billing(postgres_engine, other_id) == (False, None, 0, 0)

"""Webhook transaction ownership plus real PostgreSQL per-account serialization.

Set STRIPE_CONCURRENCY_TEST_DATABASE_URL to an isolated PostgreSQL test database. Only the
PostgreSQL cases skip when absent; an invalid/unavailable configured database fails the gate.
Every PostgreSQL fixture owns a disposable schema and never changes public tables.

The PB-02 section at the end holds the complimentary Pro grant's units to the same standard on real
PostgreSQL, where SQLite renders neither their advisory lock nor their FOR NO KEY UPDATE: a grant and a
revoke of one account run one at a time, two applies racing at the cap grant one account between them,
and deleting a granted account removes its ledger row through the foreign key.
"""
import asyncio
import json
import os
import re
import threading
import time
from datetime import timedelta
from pathlib import Path
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event as sqlalchemy_event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from starlette.requests import Request

from app import database
from app.database import Base, SessionLocal
from app.models import (
    AccountAgreement, AuditLog, BillingPayment, Company, ComplimentaryAccessGrant, InviteCode, StripeEvent, Subscription,
    TrendAnalysis, User,
)
from app.routers import subscriptions
from app.services import billing_account_service, subscription_sync, subscription_webhook_service as service
from app.services import complimentary_access_service as access
from app.services.complimentary_access_manifest import email_fingerprint, load_manifest
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION
from app.utils.datetimes import utcnow
from tests.support.hang_guard import HANG_GUARD_S


TABLES = [
    User.__table__, Subscription.__table__, StripeEvent.__table__, InviteCode.__table__, BillingPayment.__table__,
    AccountAgreement.__table__, ComplimentaryAccessGrant.__table__, AuditLog.__table__, Company.__table__,
    TrendAnalysis.__table__,
]


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


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine
    or connection: an autoflushing one flushes a pending write at its next query, where production waits for
    the commit, and can serialize two requests that production does not (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


@pytest.fixture(autouse=True)
def stripe_boundary(monkeypatch):
    monkeypatch.setattr(subscriptions.stripe.Webhook, "construct_event", lambda *args: object())
    monkeypatch.setattr(service, "capture_event", lambda *args: None)


def _install_factory(monkeypatch, engine, cls=Session):
    factory = sessionmaker(**{**SessionLocal.kw, "bind": engine}, class_=cls)
    monkeypatch.setattr(database, "SessionLocal", factory)
    return factory


def _seed(engine, *, customer="cus_test"):
    with _session(engine) as db:
        user = User(email=f"{uuid.uuid4().hex}@example.com", email_verified=True, stripe_customer_id=customer)
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
    with _session(engine) as db:
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
        assert release.wait(HANG_GUARD_S), "test did not release webhook worker"
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
        assert await asyncio.to_thread(entered.wait, HANG_GUARD_S)
        task.cancel()
        await asyncio.sleep(0)
        assert not closed.is_set(), "request cancellation closed the running worker's session"
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(finished.wait, HANG_GUARD_S)
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
    if kind == "customer.subscription.updated":
        monkeypatch.setattr(service, "retrieve_subscription_snapshot", lambda *_: payload["data"]["object"])
    with _session(postgres_engine) as holder:
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
            assert release.wait(HANG_GUARD_S), "test did not release first delivery"
        return original(*args)

    monkeypatch.setattr(service, "_apply_event", hold_first)
    first = asyncio.create_task(_deliver(first_payload))
    try:
        assert await asyncio.to_thread(entered.wait, HANG_GUARD_S)
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
    with _session(postgres_engine) as db:
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
            with _session(postgres_engine) as writer:
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


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_request", [False, True])
async def test_postgres_provider_read_holds_lock_through_completion_and_retry(postgres_engine, monkeypatch, cancel_request):
    user_id = _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    await _deliver(_event(user_id))
    payload = _event(user_id, "customer.subscription.updated")
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    reads = []

    def read_current(subscription_id, customer_id):
        reads.append((subscription_id, customer_id))
        entered.set()
        assert release.wait(HANG_GUARD_S), "test did not release provider read"
        return {"id": subscription_id, "customer": customer_id, "status": "past_due"}

    def finish_worker(event):
        first_request = not entered.is_set()
        try:
            return service.process_stripe_event(event)
        finally:
            if first_request:
                finished.set()

    monkeypatch.setattr(service, "retrieve_subscription_snapshot", read_current)
    monkeypatch.setattr(subscriptions, "process_stripe_event", finish_worker)
    first = asyncio.create_task(_deliver(payload))
    try:
        assert await asyncio.to_thread(entered.wait, HANG_GUARD_S)
        with pytest.raises(HTTPException) as error:
            await _deliver(payload)
        assert error.value.status_code == 503
        assert _billing(postgres_engine, user_id) == (True, "active", 1, 1)
        if cancel_request:
            first.cancel()
            await asyncio.sleep(0)
            assert not finished.is_set(), "cancellation abandoned the running provider transaction"
    finally:
        release.set()
        if cancel_request:
            with pytest.raises(asyncio.CancelledError):
                await first
        else:
            assert await first == {"status": "success"}
        assert await asyncio.to_thread(finished.wait, HANG_GUARD_S)
    assert _billing(postgres_engine, user_id) == (False, "past_due", 1, 2)
    assert await _deliver(payload) == {"status": "success", "idempotent": True}
    assert reads == [("sub_test", "cus_test")]



@pytest.mark.asyncio
@pytest.mark.parametrize("fail_second", [False, True])
@pytest.mark.parametrize("cancel_request", [False, True])
async def test_postgres_cross_subscription_reads_hold_the_lock_and_fail_without_mutation(
        postgres_engine, monkeypatch, cancel_request, fail_second):
    """An event for another subscription reads the bound one, then its own, both under the account lock and
    before any write (E98). A concurrent delivery meets the held lock (503, nothing changed), cancelling the
    request never abandons the worker, a failed second read leaves billing and the ledger as they were, and
    the lock is released afterwards."""
    user_id = _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    await _deliver(_event(user_id))  # binds sub_test, active
    payload = _event(user_id, "customer.subscription.updated")
    payload["data"]["object"]["id"] = "sub_old"  # old sub_old's late "active" update
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    reads = []

    def read(subscription_id, customer_id, *, require_created=False):
        reads.append((subscription_id, customer_id, require_created))
        if subscription_id == "sub_test":
            entered.set()
            assert release.wait(HANG_GUARD_S), "test did not release the bound read"
            return {"id": "sub_test", "customer": "cus_test", "status": "active", "created": 2000}
        if fail_second:
            raise service.SubscriptionReconciliationUnavailable("Current Stripe subscription state is unavailable")
        return {"id": "sub_old", "customer": "cus_test", "status": "canceled", "created": 1000}

    def finish_worker(event):
        first_request = not entered.is_set()
        try:
            return service.process_stripe_event(event)
        finally:
            if first_request:
                finished.set()

    monkeypatch.setattr(service, "retrieve_subscription_snapshot", read)
    monkeypatch.setattr(subscriptions, "process_stripe_event", finish_worker)
    first = asyncio.create_task(_deliver(payload))
    try:
        assert await asyncio.to_thread(entered.wait, HANG_GUARD_S)
        with pytest.raises(HTTPException) as error:
            await _deliver(payload)
        assert error.value.status_code == 503
        assert _billing(postgres_engine, user_id) == (True, "active", 1, 1)
        if cancel_request:
            first.cancel()
            await asyncio.sleep(0)
            assert not finished.is_set(), "cancellation abandoned the running provider transaction"
    finally:
        release.set()
        if cancel_request:
            with pytest.raises(asyncio.CancelledError):
                await first
        elif fail_second:
            with pytest.raises(HTTPException) as error:
                await first
            assert error.value.status_code == 503
        else:
            assert await first == {"status": "success"}
        assert await asyncio.to_thread(finished.wait, HANG_GUARD_S)
    assert _billing(postgres_engine, user_id) == (True, "active", 1, 1 if fail_second else 2)
    with _session(postgres_engine) as db:
        assert db.get(User, user_id).stripe_subscription_id == "sub_test"
        db.query(User).filter_by(id=user_id).with_for_update(nowait=True).one()  # the lock was released
        db.rollback()
    assert reads == [("sub_test", "cus_test", True), ("sub_old", "cus_test", True)]

def _payment_event(event_id="evt_payment"):
    return {"id": event_id, "type": "invoice_payment.paid", "livemode": True,
            "data": {"object": {"id": "inpay_test", "object": "invoice_payment", "invoice": "in_test",
                                 "livemode": True, "currency": "usd", "amount_paid": 3900, "status": "paid",
                                 "payment": {"type": "payment_intent", "payment_intent": "pi_test"},
                                 "status_transitions": {"paid_at": 1788739200}}}}


def _payment_invoice():
    return {"id": "in_test", "object": "invoice", "currency": "usd", "livemode": True,
            "customer": "cus_test", "parent": {"subscription_details": {"subscription": "sub_old"}}}


def _payments(engine):
    with _session(engine) as db:
        return (db.query(BillingPayment).count(), db.query(StripeEvent).count(),
                sum(row.amount_minor for row in db.query(BillingPayment)))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "provider", "ledger"])
async def test_payment_and_event_commit_together_before_signal(sqlite_engine, monkeypatch, failure):
    _seed(sqlite_engine)
    closed, captures = threading.Event(), []

    class ObservedSession(Session):
        def close(self):
            super().close()
            closed.set()

    _install_factory(monkeypatch, sqlite_engine, ObservedSession)

    def read_invoice(_):
        if failure == "provider":
            raise service.SubscriptionReconciliationUnavailable("unavailable")
        return _payment_invoice()

    monkeypatch.setattr(service, "retrieve_invoice_snapshot", read_invoice)
    monkeypatch.setattr(service, "capture_event", lambda *args: captures.append((closed.is_set(), _payments(sqlite_engine))))
    if failure == "ledger":
        def fail(db, *_):
            db.flush()
            raise RuntimeError("forced ledger failure")
        monkeypatch.setattr(subscription_sync, "mark_event_processed", fail)
    if failure:
        with pytest.raises(HTTPException) as error:
            await _deliver(_payment_event())
        assert error.value.status_code == (503 if failure == "provider" else 500)
        assert _payments(sqlite_engine) == (0, 0, 0)
        assert captures == []
    else:
        assert await _deliver(_payment_event()) == {"status": "success"}
        assert captures == [(True, (1, 1, 3900))]
        monkeypatch.setattr(service, "retrieve_invoice_snapshot", lambda _: pytest.fail("duplicate read Stripe"))
        assert await _deliver(_payment_event()) == {"status": "success", "idempotent": True}
        assert _payments(sqlite_engine) == (1, 1, 3900)


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", [
    {"parent": []}, {"parent": {"subscription_details": "bad"}}, {"lines": "bad"},
    {"lines": {"data": "bad"}}, {"lines": {"has_more": False, "data": [{"pricing": []}]}},
    {"lines": {"has_more": False, "data": [{"pricing": {"price_details": "bad"}}]}},
])
async def test_invoice_shape_failure_is_retryable_and_preserves_evidence(sqlite_engine, monkeypatch, malformed):
    _seed(sqlite_engine)
    _install_factory(monkeypatch, sqlite_engine)
    monkeypatch.setattr(service, "retrieve_invoice_snapshot", lambda _: {**_payment_invoice(), **malformed})
    with pytest.raises(HTTPException) as error:
        await _deliver(_payment_event())
    assert error.value.status_code == 503
    assert _payments(sqlite_engine) == (0, 0, 0)
    monkeypatch.setattr(service, "retrieve_invoice_snapshot", lambda _: _payment_invoice())
    assert await _deliver(_payment_event()) == {"status": "success"}
    assert _payments(sqlite_engine) == (1, 1, 3900)


@pytest.mark.asyncio
async def test_postgres_duplicate_payment_distinct_events_count_once(postgres_engine, monkeypatch):
    _seed(postgres_engine)
    _install_factory(monkeypatch, postgres_engine)
    monkeypatch.setattr(service, "retrieve_invoice_snapshot", lambda _: _payment_invoice())
    entered, release = threading.Event(), threading.Event()
    original = service.billing_revenue_service.record_payment

    def hold_first(*args):
        if not entered.is_set():
            entered.set()
            assert release.wait(HANG_GUARD_S), "test did not release payment worker"
        return original(*args)

    monkeypatch.setattr(service.billing_revenue_service, "record_payment", hold_first)
    first = asyncio.create_task(_deliver(_payment_event()))
    try:
        assert await asyncio.to_thread(entered.wait, HANG_GUARD_S)
        with pytest.raises(HTTPException) as error:
            await _deliver(_payment_event("evt_another_payment_delivery"))
        assert error.value.status_code == 503
        assert _payments(postgres_engine) == (0, 0, 0)
    finally:
        release.set()
        assert await first == {"status": "success"}
    assert await _deliver(_payment_event("evt_another_payment_delivery")) == {"status": "success"}
    assert _payments(postgres_engine) == (1, 2, 3900)


def test_postgres_report_first_payment_insert_between_reads_uses_one_snapshot(postgres_engine):
    """A concurrent first payment must not outgrow a separate user-to-first-time dictionary."""
    from datetime import datetime, timezone
    from app.services.billing_revenue_service import payment_report

    user_id = _seed(postgres_engine)
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    until = datetime(2026, 10, 1, tzinfo=timezone.utc)
    inserted = False

    def insert_after_snapshot(conn, cursor, statement, parameters, context, executemany):
        nonlocal inserted
        if inserted or "min(" not in statement.lower() or "earningsnerd_billing_payments" not in statement:
            return
        inserted = True
        with _session(postgres_engine) as writer:
            writer.add(BillingPayment(
                stripe_payment_id="inpay_concurrent_report", livemode=True,
                stripe_invoice_id="in_concurrent_report", source_event_id="evt_concurrent_report",
                amount_minor=3900, currency="usd", payment_type="payment_intent", paid_at=since,
                subscription_invoice=True, user_id=user_id, attribution="attributed",
            ))
            writer.commit()

    sqlalchemy_event.listen(postgres_engine, "after_cursor_execute", insert_after_snapshot)
    try:
        with _session(postgres_engine) as reader:
            report = payment_report(reader, since, until)
    finally:
        sqlalchemy_event.remove(postgres_engine, "after_cursor_execute", insert_after_snapshot)
    assert inserted
    assert report["currencies"] == []
    assert report["first_observed_payment_cohorts"] == []
    # This separate coverage-metadata statement can see a newer committed observation.
    assert report["earliest_retained_observation"] is not None
    with _session(postgres_engine) as reader:
        next_report = payment_report(reader, since, until)
    assert next_report["currencies"][0]["observed_paying_users"] == 1
    assert next_report["first_observed_payment_cohorts"][0]["users"] == 1


def test_postgres_concurrent_customer_claims_keep_the_first(postgres_engine):
    """Two checkouts of one account, on two instances, each claim the account's Stripe customer after both
    loaded it with none. The first claim's write holds the row until PostgreSQL shows the second waiting for it;
    the second then finds the column set, and both return the first's customer, which the account keeps. A
    check and a write in two statements, or a blind write, lets the second write over the first, and the first
    checkout's session would name a customer the account no longer holds (E166)."""
    user_id = _seed(postgres_engine, customer=None)
    first, second = _session(postgres_engine), _session(postgres_engine)
    entered, waited, results = threading.Event(), [], {}
    try:
        # Each session holds the account as its auth lookup loaded it, with no customer.
        users = {"first": first.get(User, user_id), "second": second.get(User, user_id)}
        assert [user.stripe_customer_id for user in users.values()] == [None, None]
        second_pid = second.execute(text("SELECT pg_backend_pid()")).scalar()

        def hold_until_the_second_waits(_session):
            entered.set()
            deadline, waiting = time.monotonic() + 10, False
            with postgres_engine.connect() as watcher:
                while not waiting and time.monotonic() < deadline:
                    waiting = bool(watcher.execute(text(
                        "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": second_pid}).scalar())
                    watcher.rollback()  # pg_stat_activity is read once per transaction
                    if not waiting:
                        time.sleep(0.02)
            waited.append(waiting)

        sqlalchemy_event.listen(first, "before_commit", hold_until_the_second_waits, once=True)

        def claim(name, db, customer):
            try:
                results[name] = billing_account_service.claim_stripe_customer_id(db, users[name].id, customer)
            except Exception as error:  # reported in the assertion below
                results[name] = error

        first_claim = threading.Thread(target=claim, args=("first", first, "cus_first"))
        first_claim.start()
        assert entered.wait(10), "the first claim never reached its commit"
        second_claim = threading.Thread(target=claim, args=("second", second, "cus_second"))
        second_claim.start()
        for thread in (first_claim, second_claim):
            thread.join(30)
            assert not thread.is_alive()
        assert waited == [True], "the second claim never waited for the first's row"
        assert results == {"first": "cus_first", "second": "cus_first"}
    finally:
        first.close()
        second.close()
    with _session(postgres_engine) as reader:
        assert reader.get(User, user_id).stripe_customer_id == "cus_first"


# --------------------------------------------------------------------------- PB-02: complimentary grants


PB02_MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "20261102_earningsnerd_complimentary_access_grants.sql"
PB02_STAMP_MIGRATION = PB02_MIGRATION.with_name("20261102_trend_analysis_creator_set_null.sql")
_PB02_COLUMNS = text(
    "SELECT column_name, data_type, is_nullable, character_maximum_length FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = 'earningsnerd_complimentary_access_grants'"
    " ORDER BY ordinal_position"
)
_PB02_CONSTRAINTS = text(
    "SELECT c.contype, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid"
    " JOIN pg_namespace n ON n.oid = t.relnamespace"
    " WHERE n.nspname = :schema AND t.relname = 'earningsnerd_complimentary_access_grants' ORDER BY 1, 2"
)
# A held unit outlasts _pb02_waits_for_a_lock's poll, which the case runs while it holds, so the poll ends first.
PB02_HOLD_S = HANG_GUARD_S + 10

def _pb02_account(engine, *, admin=False):
    """An admin operator, or an invited tester who verified and confirmed their own signup."""
    now = utcnow()
    with _session(engine) as db:
        email = f"pb02-{uuid.uuid4().hex}@example.com"
        user = User(email=email, email_verified=True, is_active=True, is_beta=not admin, is_admin=admin)
        db.add(user)
        db.flush()
        if not admin:
            db.add(InviteCode(code_hash=uuid.uuid4().hex * 2, cohort="pb02", email=email, user_id=user.id,
                              used_at=now, expires_at=now + timedelta(days=7)))
            db.add(AccountAgreement(user_id=user.id, adult_eligible=True, terms_accepted=True,
                                    terms_version=TERMS_VERSION, eligibility_version=ELIGIBILITY_VERSION,
                                    accepted_at=now, source="password"))
        db.commit()
        return user.id, email


def _pb02_manifest(action, operator_id, accounts):
    payload = {"action": action, "cohort": "private-beta-2026-11", "reason": "Private beta tester",
               "operator_account_id": operator_id, "salt": "5a" * 16,  # synthetic: a real salt is secret randomness
               "accounts": [{"account_id": i, "email_sha256": email_fingerprint(e)} for i, e in accounts]}
    if action == "grant":
        payload["review_on"] = (utcnow().date() + timedelta(days=30)).isoformat()
    return load_manifest(json.dumps(payload).encode())


def _pb02_apply(engine, manifest_and_digest, pid=None):
    """Apply on a connection of its own (its backend pid recorded first), as the operator command would."""
    manifest, digest = manifest_and_digest
    with engine.connect() as conn:
        if pid is not None:
            pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar())
            conn.rollback()
        db = _session(conn)
        try:
            return access.apply(db, manifest, digest, confirm_digest=digest, today=utcnow().date())
        finally:
            db.close()


def _pb02_waits_for_a_lock(engine, pid):
    """Whether, within HANG_GUARD_S, the session whose pid ``pid`` will hold waits for a heavyweight lock."""
    deadline = time.monotonic() + HANG_GUARD_S
    with engine.connect() as watcher:
        while time.monotonic() < deadline:
            if pid:
                waiting = watcher.execute(
                    text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid[0]}
                ).scalar()
                watcher.rollback()  # pg_stat_activity is read once per transaction
                if waiting:
                    return True
            time.sleep(0.005)
    return False


def _pb02_run(results, name, *args):
    try:
        results[name] = _pb02_apply(*args)
    except Exception as error:  # reported in the case's assertions
        results[name] = error


def test_postgres_a_grant_and_a_revoke_of_one_account_run_one_at_a_time(postgres_engine, monkeypatch):
    operator_id, _ = _pb02_account(postgres_engine, admin=True)
    tester = _pb02_account(postgres_engine)
    grant = _pb02_manifest("grant", operator_id, [tester])
    revoke = _pb02_manifest("revoke", operator_id, [tester])
    locked, release, holders, results, revoke_pid = threading.Event(), threading.Event(), [], {}, []
    real_read = access._read_account

    def read_then_hold(db, account_id, *, lock):
        account = real_read(db, account_id, lock=lock)
        if lock and threading.current_thread() in holders:
            locked.set()  # the grant's unit holds the grants' lock and the account's row
            assert release.wait(PB02_HOLD_S), "the case never released the grant"
        return account

    monkeypatch.setattr(access, "_read_account", read_then_hold)
    granting = threading.Thread(target=_pb02_run, args=(results, "grant", postgres_engine, grant))
    revoking = threading.Thread(target=_pb02_run, args=(results, "revoke", postgres_engine, revoke, revoke_pid))
    holders.append(granting)
    granting.start()
    try:
        assert locked.wait(10), "the grant never reached its unit"
        revoking.start()
        assert _pb02_waits_for_a_lock(postgres_engine, revoke_pid), "the revoke did not wait for the grant's unit"
    finally:
        release.set()
        granting.join(30)
    revoking.join(30)
    assert not granting.is_alive() and not revoking.is_alive()
    # The revoke read the account after the grant committed, so it revoked what the grant gave.
    assert results["grant"].outcomes == {"granted": 1}, results
    assert results["revoke"].outcomes == {"revoked": 1}, results
    with _session(postgres_engine) as db:
        assert db.get(User, tester[0]).is_pro is False
        assert db.query(ComplimentaryAccessGrant).filter_by(user_id=tester[0]).one().revoked_at is not None
        assert [row.action for row in db.query(AuditLog).order_by(AuditLog.id)] == [access.AUDIT_GRANTED,
                                                                                   access.AUDIT_REVOKED]


def test_postgres_two_applies_racing_at_the_cap_grant_one_between_them(postgres_engine, monkeypatch):
    operator_id, _ = _pb02_account(postgres_engine, admin=True)
    granted = [_pb02_account(postgres_engine) for _ in range(access.MAX_ACTIVE_GRANTS - 1)]
    assert _pb02_apply(postgres_engine, _pb02_manifest("grant", operator_id, granted)).outcomes == {"granted": 19}
    first, second = _pb02_account(postgres_engine), _pb02_account(postgres_engine)
    counted, release, holders, results, second_pid, calls = (
        threading.Event(), threading.Event(), [], {}, [], [])
    real_count = access._active_grant_count

    def count_then_hold(db):
        active = real_count(db)
        if threading.current_thread() in holders:
            calls.append(active)
            if len(calls) == 2:  # the unit's count (its dry run counted first): 19, the grant not committed yet
                counted.set()
                assert release.wait(PB02_HOLD_S), "the case never released the first apply"
        return active

    monkeypatch.setattr(access, "_active_grant_count", count_then_hold)
    racing_first = threading.Thread(target=_pb02_run, args=(
        results, "first", postgres_engine, _pb02_manifest("grant", operator_id, [first])))
    racing_second = threading.Thread(target=_pb02_run, args=(
        results, "second", postgres_engine, _pb02_manifest("grant", operator_id, [second]), second_pid))
    holders.append(racing_first)
    racing_first.start()
    try:
        assert counted.wait(10), "the first apply never counted inside its unit"
        racing_second.start()
        assert _pb02_waits_for_a_lock(postgres_engine, second_pid), "the second apply did not wait for the first"
    finally:
        release.set()
        racing_first.join(30)
    racing_second.join(30)
    assert not racing_first.is_alive() and not racing_second.is_alive()
    assert calls[1] == access.MAX_ACTIVE_GRANTS - 1
    assert results["first"].outcomes == {"granted": 1}, results
    assert (results["second"].outcomes, results["second"].refusals) == (
        {"refused": 1}, [{"entry": 1, "codes": ["cap_reached"]}]), results
    with _session(postgres_engine) as db:
        active = db.query(ComplimentaryAccessGrant).filter(ComplimentaryAccessGrant.revoked_at.is_(None)).count()
        assert active == access.MAX_ACTIVE_GRANTS
        assert db.get(User, second[0]).is_pro is False


def test_postgres_deleting_a_granted_account_removes_its_grant_through_the_foreign_key(postgres_engine):
    operator_id, _ = _pb02_account(postgres_engine, admin=True)
    tester = _pb02_account(postgres_engine)
    assert _pb02_apply(postgres_engine, _pb02_manifest("grant", operator_id, [tester])).outcomes == {"granted": 1}
    with _session(postgres_engine) as db:
        # The ORM cascade is not in play: the database's ON DELETE CASCADE removes the ledger row, as for any
        # deletion of the account's row however it is made.
        db.execute(User.__table__.delete().where(User.__table__.c.id == tester[0]))
        db.commit()
    with _session(postgres_engine) as db:
        assert db.query(ComplimentaryAccessGrant).count() == 0
        assert [row.action for row in db.query(AuditLog)] == [access.AUDIT_GRANTED]



def test_postgres_the_migration_builds_the_ledger_the_model_maps_and_reapplies_cleanly(postgres_engine):
    """CI's migrations job seeds with create_all, which makes this file's CREATE TABLE IF NOT EXISTS skip there; this
    case applies the file itself, twice, into a schema holding only the users table, and compares what it built with
    the table the model maps (the fixture's create_all), column by column and constraint by constraint."""
    sql = PB02_MIGRATION.read_text(encoding="utf-8")
    applied = f"pb02_migration_{uuid.uuid4().hex}"
    with postgres_engine.connect() as conn:
        mapped = conn.execute(text("SELECT current_schema()")).scalar()
        conn.rollback()
        conn.execute(CreateSchema(applied))
        conn.commit()
        try:
            conn.exec_driver_sql(f"SET search_path TO {applied}")
            User.__table__.create(conn)
            conn.exec_driver_sql(sql)
            conn.exec_driver_sql(sql)  # a ledger reset or an edited file re-runs it: it must converge
            conn.commit()
            built = [tuple(row) for row in conn.execute(_PB02_COLUMNS, {"schema": applied})]
            constraints = [(kind, definition.replace(f"{applied}.", "")) for kind, definition in
                           conn.execute(_PB02_CONSTRAINTS, {"schema": applied})]
            assert built and built == [tuple(row) for row in conn.execute(_PB02_COLUMNS, {"schema": mapped})]
            assert constraints == [(kind, definition.replace(f"{mapped}.", "")) for kind, definition in
                                   conn.execute(_PB02_CONSTRAINTS, {"schema": mapped})]
            assert sorted(kind for kind, _ in constraints) == ["c", "f", "p", "u"]
        finally:
            conn.rollback()
            conn.exec_driver_sql(f"SET search_path TO {mapped}")
            conn.execute(DropSchema(applied, cascade=True))
            conn.commit()


def test_postgres_the_stamp_migration_lets_an_analyst_delete_their_account_and_reapplies_cleanly(postgres_engine):
    """A grant opens Multi-Period Analysis, whose cache row is stamped with the account that generated it. The model now
    declares the stamp ON DELETE SET NULL, so the fixture's create_all already has it: this case first rebuilds the
    reference production holds (no ON DELETE action), shows the analyst's deletion failing on it, applies the file twice,
    and deletes the analyst, whose shared analysis stays with its stamp cleared."""
    constraint = "trend_analysis_created_by_user_id_fkey"
    with postgres_engine.connect() as conn:
        conn.exec_driver_sql(f"ALTER TABLE trend_analysis DROP CONSTRAINT {constraint}")
        conn.exec_driver_sql(f"ALTER TABLE trend_analysis ADD CONSTRAINT {constraint} "
                             "FOREIGN KEY (created_by_user_id) REFERENCES users (id)")
        conn.commit()
    with _session(postgres_engine) as db:
        analyst = User(email=f"analyst-{uuid.uuid4().hex}@example.com", email_verified=True, is_pro=True)
        company = Company(cik="0000000042", ticker="STMP", name="Stamp Co")
        db.add_all([analyst, company])
        db.flush()
        db.add(TrendAnalysis(company_id=company.id, mode="annual", period_key="FY2022..FY2024", prompt_version="v",
                             dataset_fingerprint="f" * 64, dataset_json={}, narrative_md="n", citations_json=[],
                             model="m", grounded=1, created_by_user_id=analyst.id))
        db.commit()
        analyst_id = analyst.id
    delete = User.__table__.delete().where(User.__table__.c.id == analyst_id)
    with postgres_engine.connect() as conn:
        with pytest.raises(Exception, match=constraint):  # the reference production holds stops the deletion
            conn.execute(delete)
        conn.rollback()
        sql = PB02_STAMP_MIGRATION.read_text(encoding="utf-8")
        conn.exec_driver_sql(sql)
        conn.exec_driver_sql(sql)  # a ledger reset or an edited file re-runs it: it must converge
        conn.commit()
        rows = conn.execute(text(
            "SELECT conname, confdeltype, convalidated FROM pg_constraint WHERE conrelid = 'trend_analysis'::regclass"
            " AND contype = 'f' AND confrelid = 'users'::regclass")).all()
        assert [tuple(row) for row in rows] == [(constraint, "n", True)]
        conn.execute(delete)
        conn.commit()
    with _session(postgres_engine) as db:
        assert db.get(User, analyst_id) is None
        assert [row.created_by_user_id for row in db.query(TrendAnalysis)] == [None]


_PB02_HELD = text(
    "SELECT c.relname, l.mode FROM pg_locks l JOIN pg_class c ON c.oid = l.relation"
    " WHERE l.pid = pg_backend_pid() AND l.locktype = 'relation' AND l.granted"
    " AND c.relname IN ('users', 'trend_analysis') AND c.relnamespace = current_schema()::regnamespace"
)
_PB02_PROBES = {
    "read users": "SELECT 1 FROM users LIMIT 1",
    "write users": "UPDATE users SET is_active = is_active WHERE false",
    "write trend_analysis": "UPDATE trend_analysis SET grounded = grounded WHERE false",
}


def _pb02_statements(sql):
    """A migration file's top-level statements, as psql sends them: split at each semicolon outside a comment and
    outside a dollar quote."""
    statements, start, quoted = [], 0, False
    for token in re.finditer(r"--[^\n]*|\$\$|;", sql):
        if token.group() == "$$":
            quoted = not quoted
        elif token.group() == ";" and not quoted:
            statements.append(sql[start:token.end()].strip())
            start = token.end()
    assert not sql[start:].strip() and not quoted
    return statements


def _pb02_probe(engine, sql):
    """What a second session's statement meets while a migration statement's transaction is open: it runs, or
    waits past a 200 ms lock_timeout (55P03)."""
    with engine.connect() as probe:
        probe.exec_driver_sql("SET lock_timeout = '200ms'")
        try:
            probe.exec_driver_sql(sql)
            return "runs"
        except OperationalError as exc:
            return "waits" if exc.orig.pgcode == "55P03" else exc.orig.pgcode
        finally:
            probe.rollback()


def test_postgres_each_pb02_migration_statement_holds_only_the_locks_its_comments_name(postgres_engine):
    """apply_migrations.sh runs each file through psql outside a transaction block, so each top-level statement
    commits on its own. This case runs each statement of PB-02's two files in a transaction it holds open, reads the
    locks it took and probes users and trend_analysis from a second session: the ledger's CREATE holds SHARE ROW
    EXCLUSIVE on users (reads go on, writes wait); the stamp's swap holds ACCESS EXCLUSIVE on both tables (everything
    waits); its validation, a statement of its own, stops no read or write; each waits 2 s for a lock, not the
    session's 10 s; and a re-run takes no lock on either table."""
    apply_line = next(line for line in (Path(__file__).resolve().parents[2] / "scripts" / "apply_migrations.sh")
                      .read_text(encoding="utf-8").splitlines() if 'psql' in line and '-f "$f"' in line)
    assert "--single-transaction" not in apply_line and not re.search(r"\s-1\b", apply_line), apply_line
    constraint = "trend_analysis_created_by_user_id_fkey"
    with postgres_engine.connect() as conn:
        # Production's state: no ledger yet, and the stamp's reference with no ON DELETE action.
        conn.exec_driver_sql("DROP TABLE earningsnerd_complimentary_access_grants")
        conn.exec_driver_sql(f"ALTER TABLE trend_analysis DROP CONSTRAINT {constraint}")
        conn.exec_driver_sql(f"ALTER TABLE trend_analysis ADD CONSTRAINT {constraint} "
                             "FOREIGN KEY (created_by_user_id) REFERENCES users (id)")
        conn.commit()
    seen = []
    for attempt in ("first", "re-run"):
        for path in (PB02_MIGRATION, PB02_STAMP_MIGRATION):
            with postgres_engine.connect() as conn:
                for statement in _pb02_statements(path.read_text(encoding="utf-8")):
                    conn.exec_driver_sql(statement)
                    held = {}
                    for relation, mode in conn.execute(_PB02_HELD):
                        held.setdefault(relation, set()).add(mode)
                    timeout = conn.exec_driver_sql("SHOW lock_timeout").scalar()
                    probes = {name: _pb02_probe(postgres_engine, sql) for name, sql in _PB02_PROBES.items()}
                    conn.commit()
                    code = re.sub(r"--[^\n]*", "", statement)
                    kind = next((k for k in ("CREATE TABLE", "DROP CONSTRAINT", "VALIDATE CONSTRAINT") if k in code),
                                code.split()[0])
                    seen.append((attempt, path.name, kind, timeout, held, probes))
    everything_runs = dict.fromkeys(_PB02_PROBES, "runs")
    ledger, stamp = PB02_MIGRATION.name, PB02_STAMP_MIGRATION.name
    assert [entry[:3] for entry in seen] == [
        (attempt, name, kind) for attempt in ("first", "re-run") for name, kinds in (
            (ledger, ["SET", "CREATE TABLE", "RESET"]), (stamp, ["SET", "DROP CONSTRAINT", "VALIDATE CONSTRAINT", "RESET"]),
        ) for kind in kinds
    ]
    for attempt, name, kind, timeout, held, probes in seen:
        if kind in ("SET", "RESET"):
            assert (held, probes) == ({}, everything_runs), (attempt, name, kind)
            continue
        assert timeout == "2s", (name, kind)
        if attempt == "re-run":
            assert (held, probes) == ({}, everything_runs), (name, kind)
        elif kind == "CREATE TABLE":
            assert held == {"users": {"AccessShareLock", "ShareRowExclusiveLock"}}
            assert probes == {**everything_runs, "write users": "waits"}
        elif kind == "DROP CONSTRAINT":
            assert "AccessExclusiveLock" in held["users"] and "AccessExclusiveLock" in held["trend_analysis"]
            assert probes == dict.fromkeys(_PB02_PROBES, "waits")
        else:
            assert held == {"users": {"AccessShareLock", "RowShareLock"},
                            "trend_analysis": {"AccessShareLock", "ShareUpdateExclusiveLock"}}
            assert probes == everything_runs
    with postgres_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT conname, confdeltype, convalidated FROM pg_constraint WHERE conrelid = 'trend_analysis'::regclass"
            " AND contype = 'f' AND confrelid = 'users'::regclass")).all()
        assert [tuple(row) for row in rows] == [(constraint, "n", True)]
        assert conn.execute(text("SELECT to_regclass('earningsnerd_complimentary_access_grants') IS NOT NULL")).scalar()

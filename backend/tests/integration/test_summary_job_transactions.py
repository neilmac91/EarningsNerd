"""Real PostgreSQL ownership, fencing and account/receipt races with independent sessions.

SUMMARY_JOB_TEST_DATABASE_URL points only to a disposable test database. Each case
creates and drops its own UUID schema; no production schema or network provider is used.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app import database
from app.config import settings
from app.models import Company, Filing, Summary, SummaryJob, SummaryPreparationBudget, User, UserUsage
from app.services import summary_job_store as store, subscription_service as usage
from app.utils.datetimes import utcnow


@pytest.fixture
def postgres_engine():
    url = os.environ.get("SUMMARY_JOB_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SUMMARY_JOB_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql"
    schema = f"summary_jobs_{uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        database.Base.metadata.create_all(engine)
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def factory(postgres_engine, monkeypatch):
    factory = sessionmaker(**{**database.SessionLocal.kw, "bind": postgres_engine})
    monkeypatch.setattr(store, "SessionLocal", factory)
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    return factory


@pytest.fixture
def seeded(factory):
    with factory() as db:
        user = User(email="owner@example.test")
        company = Company(cik="0000872589", ticker="REGN", name="Regeneron")
        db.add_all([user, company])
        db.flush()
        filing = Filing(company_id=company.id, accession_number="0000872589-26-000034", filing_type="10-Q",
                        filing_date=utcnow(), document_url="https://example.test/exact.htm",
                        sec_url="https://example.test/exact/")
        db.add(filing)
        db.commit()
        return user.id, filing.id


def _race(call, count=4):
    barrier = Barrier(count)
    def worker():
        barrier.wait(timeout=5)
        return call()
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(lambda _: worker(), range(count)))


def test_simultaneous_instances_create_one_job_and_claim_one_owner(factory, seeded):
    user_id, filing_id = seeded
    views = _race(lambda: store.ensure_job(filing_id, user_id))
    assert sum(view.created for view in views) == 1
    assert len({view.job_id for view in views}) == 1
    leases = _race(lambda: store.claim_job(views[0].job_id, views[0].generation))
    assert sum(lease is not None for lease in leases) == 1
    with factory() as db:
        assert db.query(SummaryJob).filter_by(filing_id=filing_id).count() == 1


def test_account_backlog_limit_serializes_different_filings(factory, seeded, monkeypatch):
    user_id, filing_id = seeded
    monkeypatch.setattr(settings, "SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT", 1)
    with factory() as db:
        first = db.get(Filing, filing_id)
        second = Filing(company_id=first.company_id, accession_number="0000872589-26-000032", filing_type="8-K",
                        filing_date=utcnow(), document_url="https://example.test/8k.htm", sec_url="https://example.test/8k/")
        db.add(second)
        db.commit()
        other_id = second.id
    barrier = Barrier(2)
    def create(filing):
        barrier.wait(timeout=5)
        try:
            return store.ensure_job(filing, user_id)
        except store.SummaryJobUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, [filing_id, other_id]))
    assert sum(result is not None for result in results) == 1


def test_concurrent_charge_converts_exactly_once_and_crash_reuses_receipt(factory, seeded):
    user_id, filing_id = seeded
    view = store.ensure_job(filing_id, user_id)
    lease = store.claim_job(view.job_id, view.generation)
    store.reserve_job_usage(lease)
    months = _race(lambda: store.charge_job_usage(lease))
    assert len(set(months)) == 1
    with factory() as db:
        assert db.query(UserUsage).filter_by(user_id=user_id).one().summary_count == 1
        db.get(SummaryJob, view.job_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    replacement = store.claim_job(view.job_id, view.generation)
    store.reserve_job_usage(replacement)
    store.charge_job_usage(replacement)
    with factory() as db:
        assert db.query(UserUsage).filter_by(user_id=user_id).one().summary_count == 1
    _race(lambda: store.refund_job_usage(replacement))
    with factory() as db:
        assert db.query(UserUsage).filter_by(user_id=user_id).one().summary_count == 0


def test_old_version_owner_cannot_publish_after_reclaim(factory, seeded):
    user_id, filing_id = seeded
    view = store.ensure_job(filing_id, user_id)
    old = store.claim_job(view.job_id, view.generation)
    with factory() as db:
        row = db.get(SummaryJob, view.job_id)
        row.lease_until = utcnow() - timedelta(seconds=1)
        row.prompt_version = "next-prompt-version"
        db.commit()
    replacement = store.claim_job(view.job_id, view.generation)
    assert replacement.token != old.token
    with factory() as db, pytest.raises(store.SummaryJobLeaseLost):
        store.lock_job_for_result(db, old)
        db.add(Summary(filing_id=filing_id, business_overview="stale overwrite"))
        db.commit()
    with factory() as db:
        row = store.lock_job_for_result(db, replacement)
        summary = Summary(filing_id=filing_id, business_overview="current owner")
        db.add(summary)
        db.flush()
        store.settle_job_result(row, summary.id, "complete")
        db.commit()
    assert store.claim_job(view.job_id, view.generation) is None
    with factory() as db:
        assert db.query(Summary).one().business_overview == "current owner"


def test_result_transaction_blocks_reclaim_until_atomic_terminal_commit(factory, seeded, monkeypatch):
    user_id, filing_id = seeded
    view = store.ensure_job(filing_id, user_id)
    lease = store.claim_job(view.job_id, view.generation)
    started = Event()
    with factory() as writer:
        row = store.lock_job_for_result(writer, lease)
        # Clock moves past the lease after the finalizer takes the lock. Reclaim
        # must wait for this transaction and then observe its terminal receipt.
        monkeypatch.setattr(store, "utcnow", lambda: utcnow() + timedelta(seconds=200))
        def reclaim():
            started.set()
            return store.claim_job(view.job_id, view.generation)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reclaim)
            assert started.wait(timeout=2)
            summary = Summary(filing_id=filing_id, business_overview="committed result")
            writer.add(summary)
            writer.flush()
            store.settle_job_result(row, summary.id, "complete")
            writer.commit()
            assert future.result(timeout=5) is None
    assert store.read_job(view.job_id, view.generation).status == "complete"


def test_postgres_charge_rollback_has_no_half_receipt(factory, seeded, monkeypatch):
    user_id, filing_id = seeded
    view = store.ensure_job(filing_id, user_id)
    lease = store.claim_job(view.job_id, view.generation)
    store.reserve_job_usage(lease)
    original = usage.increment_user_usage
    def fail_after_counter(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated crash before commit")
    monkeypatch.setattr(usage, "increment_user_usage", fail_after_counter)
    with pytest.raises(RuntimeError):
        store.charge_job_usage(lease)
    with factory() as db:
        row = db.get(SummaryJob, view.job_id)
        assert row.charge_state == "reserved" and row.reservation_token
        assert db.query(UserUsage).filter_by(user_id=user_id).count() == 0


def test_system_daily_budget_serializes_fleet_admissions(factory, seeded, monkeypatch):
    _, filing_id = seeded
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_SCAN", 2)
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_DAY", 1)
    with factory() as db:
        first = db.get(Filing, filing_id)
        second = Filing(company_id=first.company_id, accession_number="0000872589-26-000032", filing_type="8-K",
                        filing_date=utcnow(), document_url="https://example.test/8k.htm", sec_url="https://example.test/8k/")
        db.add(second)
        db.commit()
        other_id = second.id
    barrier = Barrier(2)
    def create(filing):
        barrier.wait(timeout=5)
        try:
            return store.ensure_job(filing, None, system=True)
        except store.SummaryJobUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, [filing_id, other_id]))
    assert sum(result is not None for result in results) == 1
    with factory() as db:
        assert db.query(SummaryPreparationBudget).one().admissions == 1
        assert db.query(SummaryJob).count() == 1


def test_join_during_final_result_commit_neither_deadlocks_nor_creates_second_job(postgres_engine, factory, seeded):
    """A job waiter must allow the finalizer's FK lock and read readiness after its commit."""
    from sqlalchemy import event
    user_id, filing_id = seeded
    view = store.ensure_job(filing_id, user_id)
    lease = store.claim_job(view.job_id, view.generation)
    waiting_for_job = Event()
    with factory() as writer:
        row = store.lock_job_for_result(writer, lease)
        def before(conn, cursor, statement, parameters, context, executemany):
            if "FROM earningsnerd_summary_jobs" in statement and "FOR UPDATE" in statement:
                # ensure_job has already acquired its filing lock before this SELECT.
                waiting_for_job.set()
        event.listen(postgres_engine, "before_cursor_execute", before)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                joining = pool.submit(store.ensure_job, filing_id, user_id)
                assert waiting_for_job.wait(timeout=2)
                try:
                    summary = Summary(filing_id=filing_id, business_overview="Current committed summary.")
                    writer.add(summary)
                    writer.flush()  # obtains the FK's KEY SHARE on filings while holding the job lock
                    store.settle_job_result(row, summary.id, "complete")
                    writer.commit()
                except BaseException:
                    writer.rollback()  # release the job lock before joining the thread on test failure
                    raise
                observed = joining.result(timeout=5)
                assert observed.status == "complete" and observed.summary_id == summary.id
                assert not observed.created
        finally:
            event.remove(postgres_engine, "before_cursor_execute", before)
    with factory() as db:
        assert db.get(SummaryJob, view.job_id).generation == 1

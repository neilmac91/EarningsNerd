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


def _ops_reader():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "ops/summary_readout/readout.py"
    spec = importlib.util.spec_from_file_location("summary_ops_pg_reader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ops_snapshot(postgres_engine, *, before_rollback=None):
    """Execute the committed SQL with the real driver; psql itself is stubbed only in unit cases."""
    reader = _ops_reader()
    connection = postgres_engine.raw_connection()
    connection.driver_connection.autocommit = True
    result = None
    try:
        with connection.cursor() as cursor:
            for statement in reader.SQL_FILE.read_text().split(";"):
                if not statement.strip():
                    continue
                if statement.strip() == "ROLLBACK" and before_rollback is not None:
                    before_rollback(cursor)
                cursor.execute(statement)
                if cursor.description:
                    result = cursor.fetchone()[0]
        return reader.normalize_snapshot(result)
    finally:
        connection.rollback()
        connection.driver_connection.autocommit = False
        connection.close()


def _ops_filings(factory):
    with factory() as db:
        company = Company(cik="0000872589", ticker="REGN", name="Regeneron")
        db.add(company)
        db.flush()
        for identity, accession, form in ((45003, "0000872589-26-000034", "10-Q"),
                                           (45004, "0000872589-26-000032", "8-K")):
            db.add(Filing(id=identity, company_id=company.id, accession_number=accession, filing_type=form,
                          filing_date=utcnow(), document_url="https://example.test/filing.htm",
                          sec_url="https://example.test/filing/"))
        db.commit()


def test_ops_snapshot_reads_actual_receipts_without_private_values(postgres_engine, factory):
    import json
    from app.models import UsageReservation
    from app.models.sec_request_gate import SECRequestGate
    _ops_filings(factory)
    now = utcnow()
    private = "private@audit.invalid"
    lease_token, reservation_token, job_id = uuid4().hex, str(uuid4()), uuid4().hex
    with factory() as db:
        user = User(email=private)
        db.add(user)
        db.flush()
        result = Summary(filing_id=45004, business_overview=private)
        db.add(result)
        db.flush()
        db.add(UsageReservation(user_id=user.id, month=now.strftime("%Y-%m"), kind="summary",
                                token=reservation_token, created_at=now, expires_at=now + timedelta(seconds=120)))
        db.add(SummaryJob(id=job_id, filing_id=45003, generation=2, prompt_version=private,
                          status="running", user_id=user.id, system_funded=False, stage=private,
                          lease_token=lease_token, lease_until=now + timedelta(seconds=90), attempts=1,  # gitleaks:allow runtime-generated synthetic UUID fixture
                          next_attempt_at=now, dispatch_token=uuid4().hex, last_dispatched_at=now,
                          summary_id=result.id, reservation_token=reservation_token, charge_state="reserved",
                          created_at=now - timedelta(seconds=600), updated_at=now, error_code=private))
        db.add(SECRequestGate(id=1, next_admission_at=now + timedelta(seconds=1),
                             cooldown_until=now + timedelta(seconds=60)))
        db.commit()
    receipt = _ops_snapshot(postgres_engine)
    encoded = json.dumps(receipt)
    for withheld in (private, lease_token, reservation_token, job_id):
        assert withheld not in encoded
    observed = receipt["filings"][0]
    assert observed["active_owner"] and observed["lease_state"] == "live"
    assert observed["stage"] == "unknown" and observed["error_recorded"]
    assert observed["result_reference"] == "wrong_filing"
    assert observed["reservation_reference"] == "live"
    assert observed["generation"] == 2 and observed["attempts"] == 1
    assert receipt["filings"][1]["job_present"] is False
    assert receipt["active_jobs"]["retained"] == 1
    assert receipt["sec_coordinator"]["times"]["cooldown"]["seconds_from_snapshot"] > 0
    with factory() as db:
        db.query(UsageReservation).filter_by(token=reservation_token).one().kind = "qa"
        db.get(SummaryJob, job_id).charge_state = "charged"
        db.commit()
    inconsistent = _ops_snapshot(postgres_engine)["filings"][0]
    assert inconsistent["reservation_reference"] == "wrong_owner_or_kind"
    assert inconsistent["observations"] == ["charge_month_unresolved", "reservation_remains_after_charge_or_refund"]


def test_ops_snapshot_preserves_holds_and_terminal_stale_lease_semantics(postgres_engine, factory):
    from datetime import datetime, timezone
    from app.models.sec_request_gate import SECRequestGate
    _ops_filings(factory)
    now = utcnow()
    with factory() as db:
        db.add(SummaryJob(id=uuid4().hex, filing_id=45003, generation=3, prompt_version="v1",
                          status="failed", system_funded=True, stage="error", lease_token=uuid4().hex,
                          lease_until=now + timedelta(seconds=60), attempts=4,
                          next_attempt_at=datetime.max.replace(tzinfo=timezone.utc), dispatch_token=uuid4().hex,
                          charge_state="unreserved", created_at=now - timedelta(seconds=4000), updated_at=now))
        db.add(SECRequestGate(id=1, next_admission_at=now, cooldown_until=now))
        db.commit()
    with postgres_engine.begin() as conn:
        conn.exec_driver_sql("UPDATE earningsnerd_sec_request_gate SET cooldown_until = 'infinity'::timestamptz")
    receipt = _ops_snapshot(postgres_engine)
    assert receipt["filings"][0]["lease_state"] == "live"
    assert receipt["filings"][0]["active_owner"] is False
    assert receipt["filings"][0]["times"]["next_attempt"]["state"] == "future_bound"
    assert receipt["sec_coordinator"]["times"]["cooldown"] == {"state": "nonfinite", "seconds_from_snapshot": None}
    assert receipt["active_jobs"]["retained"] == 0


def test_ops_snapshot_caps_global_sample_and_verifies_fixed_identity(postgres_engine, factory):
    _ops_filings(factory)
    now = utcnow()
    with factory() as db:
        first = db.get(Filing, 45003)
        first.accession_number = "0000872589-26-999999"
        for offset in range(1001):
            filing = Filing(id=50000 + offset, company_id=first.company_id,
                            accession_number=f"0000872589-26-{100000 + offset:06d}", filing_type="10-Q",
                            filing_date=now, document_url="https://example.test/filing.htm", sec_url="https://example.test/filing/")
            db.add(filing)
        db.flush()
        for offset in range(1001):
            db.add(SummaryJob(id=uuid4().hex, filing_id=50000 + offset, generation=1, prompt_version="v1",
                              status="queued", system_funded=True, stage="queued", attempts=0,
                              next_attempt_at=now, dispatch_token=uuid4().hex, charge_state="unreserved",
                              created_at=now - timedelta(seconds=4000 + offset), updated_at=now))
        db.commit()
    receipt = _ops_snapshot(postgres_engine)
    assert receipt["filings"][0]["identity"] == "identity_mismatch"
    assert receipt["filings"][0]["job_present"] is False
    assert receipt["active_jobs"]["retained"] == 1000 and receipt["active_jobs"]["truncated"]
    assert receipt["active_jobs"]["queued"] == 1000
    assert receipt["active_jobs"]["unacknowledged"] == 1000
    assert receipt["active_jobs"]["older_than_3600s"] == 1000
    assert receipt["active_jobs"]["oldest_age_seconds_capped"] >= 5000


def test_ops_snapshot_transaction_refuses_writes_and_releases_itself(postgres_engine, factory):
    import psycopg2
    _ops_filings(factory)
    def write_is_refused(cursor):
        cursor.execute("SHOW statement_timeout")
        assert cursor.fetchone()[0] == "15s"
        cursor.execute("SHOW lock_timeout")
        assert cursor.fetchone()[0] == "2s"
        with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
            cursor.execute("DELETE FROM earningsnerd_sec_request_gate")
    receipt = _ops_snapshot(postgres_engine, before_rollback=write_is_refused)
    assert receipt["read_only"] is True and receipt["isolation"] == "repeatable read"
    with postgres_engine.connect() as conn:
        assert conn.exec_driver_sql("SHOW transaction_read_only").scalar() == "off"


def test_ops_readout_actual_psql_client_writes_only_normalized_receipt(postgres_engine, factory, tmp_path):
    import json
    import re
    import shutil
    import subprocess
    import sys
    assert shutil.which("psql"), "The configured PostgreSQL gate requires its real psql client"
    _ops_filings(factory)
    with postgres_engine.connect() as connection:
        schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    assert re.fullmatch(r"summary_jobs_[a-f0-9]{32}", schema)
    url = make_url(postgres_engine.url)
    env = {**os.environ, "PGHOST": url.host or "127.0.0.1", "PGPORT": str(url.port or 5432),
           "PGUSER": url.username or "postgres", "PGPASSWORD": url.password or "", "PGDATABASE": url.database,
           "PGOPTIONS": f"-c search_path={schema}", "PGSSLMODE": "disable"}
    reader = _ops_reader()
    completed = subprocess.run([sys.executable, str(reader.SQL_FILE.with_name("readout.py"))],
                               cwd=tmp_path, env=env, capture_output=True, text=True, timeout=35, check=False)
    assert completed.returncode == 0, "The real psql reader did not produce a verified snapshot"
    receipt_path = tmp_path / reader.OUTPUT_FILE
    receipt = json.loads(receipt_path.read_text())
    assert receipt == json.loads(completed.stdout)
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert receipt["read_only"] and receipt["isolation"] == "repeatable read"
    assert [row["identity"] for row in receipt["filings"]] == ["matched", "matched"]
    assert all(row["job_present"] is False for row in receipt["filings"])
    assert receipt["active_jobs"]["retained"] == 0
    assert completed.stderr == ""

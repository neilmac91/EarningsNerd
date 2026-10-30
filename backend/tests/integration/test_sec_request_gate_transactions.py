"""SEC fleet admission uses committed PostgreSQL time across independent processes.

SEC_ADMISSION_TEST_DATABASE_URL must name a disposable PostgreSQL database. Every
case applies the real migration in its own UUID schema, which is the only schema
the case drops. The child processes create independent pools in that same schema;
they never issue SEC or model requests. These checks establish request admission
spacing, not the timing of socket writes after a caller receives its grant.
"""
from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.services.sec_request_gate import PostgresRequestGate, SECAdmissionUnavailable


MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "20261030_earningsnerd_sec_request_gate.sql"
MIN_SPACING_SECONDS = 0.125


@pytest.fixture
def postgres_engine():
    url = os.environ.get("SEC_ADMISSION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SEC_ADMISSION_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql"
    schema = f"sec_request_gate_{uuid4().hex}"
    engine = create_engine(
        url, pool_size=2, max_overflow=0,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"},
    )
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(MIGRATION.read_text(encoding="utf-8"))
    try:
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _table(engine):
    return Table("earningsnerd_sec_request_gate", MetaData(), autoload_with=engine)


def _state(engine):
    table = _table(engine)
    with engine.connect() as conn:
        return conn.execute(select(table.c.next_admission_at).where(table.c.id == 1)).scalar_one()


def _process_worker(url, schema, ready, start, answers, count, single_probe=False):
    """Each process owns a fresh pool; credentials travel in memory, never output."""
    engine = create_engine(
        url, pool_size=1, max_overflow=0,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"},
    )
    try:
        gate = PostgresRequestGate(engine)
        ready.put(True)
        if not start.wait(timeout=20):
            answers.put(("error", "start signal timed out"))
            return
        decisions = []
        stop_at = time.monotonic() + 20  # Hang guard, not an elapsed-time assertion.
        while len(decisions) < count and time.monotonic() < stop_at:
            decision = gate.try_grant()
            if single_probe:
                answers.put(("probe", decision.wait_seconds, decision.granted_at))
                return
            if decision.granted_at is not None:
                assert decision.wait_seconds == 0
                decisions.append(decision.granted_at)
            else:
                assert decision.wait_seconds > 0
                time.sleep(min(decision.wait_seconds, MIN_SPACING_SECONDS))
        answers.put(("grants", decisions))
    except Exception as exc:  # Report only the class: a DB error can contain connection details.
        answers.put(("error", type(exc).__name__))
    finally:
        engine.dispose()


def _run_processes(engine, *, workers=4, count=3, single_probe=False):
    with engine.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
    # spawn prevents child processes from inheriting SQLAlchemy connections or
    # in-memory limiter state from the pytest process.
    context = multiprocessing.get_context("spawn")
    ready, answers, start = context.Queue(), context.Queue(), context.Event()
    processes = [
        context.Process(
            target=_process_worker,
            args=(engine.url.render_as_string(hide_password=False), schema, ready, start, answers, count, single_probe),
        )
        for _ in range(workers)
    ]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            assert ready.get(timeout=30) is True
        start.set()
        results = [answers.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert all(result[0] != "error" for result in results), results
        return results
    finally:
        start.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=5)
        ready.close()
        answers.close()
        ready.join_thread()
        answers.join_thread()


def test_independent_processes_share_one_non_bursting_admission_budget(postgres_engine):
    results = _run_processes(postgres_engine)
    assert all(result[0] == "grants" and len(result[1]) == 3 for result in results)
    grants = sorted(grant for _, process_grants in results for grant in process_grants)
    assert len(grants) == 12
    assert all(grant.tzinfo is not None for grant in grants)
    # The timestamp is returned from the committed DB decision. Process scheduling
    # or delayed message delivery cannot make an unsafe grant look properly spaced.
    gaps = [(second - first).total_seconds() for first, second in zip(grants, grants[1:])]
    assert min(gaps) >= MIN_SPACING_SECONDS
    assert (_state(postgres_engine) - grants[-1]).total_seconds() == MIN_SPACING_SECONDS


def test_restart_and_replayed_migration_preserve_existing_cooldown(postgres_engine):
    table = _table(postgres_engine)
    with postgres_engine.begin() as conn:
        expected = conn.execute(
            table.update().where(table.c.id == 1)
            .values(next_admission_at=text("clock_timestamp() + INTERVAL '10 minutes'"))
            .returning(table.c.next_admission_at)
        ).scalar_one()
        conn.exec_driver_sql(MIGRATION.read_text(encoding="utf-8"))
    assert _state(postgres_engine) == expected
    # A fresh process represents both a newly scaled instance and a restarted job.
    result, = _run_processes(postgres_engine, workers=1, count=1, single_probe=True)
    assert result[0] == "probe" and result[1] > 0 and result[2] is None
    assert _state(postgres_engine) == expected


def test_locked_row_denies_without_queuing_a_future_grant(postgres_engine):
    gate, table = PostgresRequestGate(postgres_engine), _table(postgres_engine)
    before = _state(postgres_engine)
    with postgres_engine.begin() as holder:
        holder.execute(select(table.c.id).where(table.c.id == 1).with_for_update()).scalar_one()
        decision = gate.try_grant()
        assert decision.granted_at is None and decision.wait_seconds > 0
    assert _state(postgres_engine) == before
    assert gate.try_grant().granted_at is not None


@pytest.mark.parametrize("missing", ["row", "table"])
def test_missing_coordinator_state_fails_closed(postgres_engine, missing):
    table = _table(postgres_engine)
    with postgres_engine.begin() as conn:
        if missing == "row":
            conn.execute(table.delete())
        else:
            table.drop(conn)
    with pytest.raises(SECAdmissionUnavailable):
        PostgresRequestGate(postgres_engine).try_grant()


def test_failed_grant_transaction_does_not_advance_state(postgres_engine):
    before = _state(postgres_engine)
    # A test-only constraint fails the actual UPDATE after the row is locked.
    # PostgreSQL must roll back that transaction; returning a permit is forbidden.
    with postgres_engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE earningsnerd_sec_request_gate ADD CONSTRAINT reject_test_grants "
            "CHECK (next_admission_at < TIMESTAMPTZ '2000-01-01 00:00:00+00')"
        )
    with pytest.raises(SECAdmissionUnavailable):
        PostgresRequestGate(postgres_engine).try_grant()
    assert _state(postgres_engine) == before

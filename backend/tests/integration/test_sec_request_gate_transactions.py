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
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, Table, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.services.sec_request_gate import PostgresRequestGate, SECAdmissionUnavailable


MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "20261030_earningsnerd_sec_request_gate.sql"
COOLDOWN_MIGRATION = MIGRATION.with_name("20261030_earningsnerd_sec_request_cooldown.sql")
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
        conn.exec_driver_sql(COOLDOWN_MIGRATION.read_text(encoding="utf-8"))
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


def _feedback_worker(url, schema, ready, start, answers, action, transport_kind, status, retry_after):
    """Exercise both HTTP owners in a fresh process; fake only the terminal send."""
    import asyncio

    import httpx

    from app.services import sec_request_gate as gate_module

    engine = create_engine(
        url, pool_size=1, max_overflow=0,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"},
    )
    decisions = []

    class ObservedGate(PostgresRequestGate):
        def try_grant(self):
            decision = super().try_grant()
            decisions.append((decision.wait_seconds, decision.granted_at is not None))
            return decision

    gate_module._gate = ObservedGate(engine)
    gate_module.settings.SEC_DISTRIBUTED_LIMIT_ENABLED = True
    gate_module.settings.SEC_DISTRIBUTED_WAIT_SECONDS = 10.0
    if action == "receive":
        real_delay = gate_module._delay

        def expire_after_shared_denial(decision, deadline):
            # End the caller's wait only after PostgreSQL has denied the request
            # under the shared embargo. Do not race a tiny real-time deadline.
            if decision.wait_seconds > 30:
                raise SECAdmissionUnavailable("Synthetic caller deadline expired")
            return real_delay(decision, deadline)

        gate_module._delay = expire_after_shared_denial
    sends = []

    async def own_request():
        def send(request):
            sends.append(request.url.path)
            return httpx.Response(status, headers={"Retry-After": retry_after}, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(send), **gate_module.sec_request_options(),
        ) as client:
            return (await client.get("https://fixture.invalid/shared-cooldown")).status_code

    def edgar_request():
        from edgar import httpclient
        from httpxthrottlecache._compat import httpx as edgar_httpx

        from app.services.edgar.sec_admission import install_edgar_admission

        install_edgar_admission()

        def send(self, request, **kwargs):
            sends.append(request.url.path)
            return edgar_httpx.Response(status, headers={"Retry-After": retry_after}, request=request)

        async def send_async(self, request, **kwargs):
            return send(self, request, **kwargs)

        async def run_async():
            async with httpclient.async_http_client(bypass_cache=True) as client:
                return (await client.get("https://fixture.invalid/shared-cooldown")).status_code

        with patch.object(edgar_httpx.HTTPTransport, "handle_request", send), patch.object(
            edgar_httpx.AsyncHTTPTransport, "handle_async_request", send_async,
        ):
            if transport_kind == "edgar_async":
                return asyncio.run(run_async())
            with httpclient.http_client(bypass_cache=True) as client:
                return client.get("https://fixture.invalid/shared-cooldown").status_code

    try:
        ready.put(True)
        if not start.wait(timeout=20):
            answers.put(("error", "start signal timed out"))
            return
        if action == "write":
            if transport_kind == "own":
                asyncio.run(gate_module.record_response_async(status, retry_after))
            else:
                gate_module.record_response_sync(status, retry_after)
            answers.put(("written",))
            return
        try:
            result = asyncio.run(own_request()) if transport_kind == "own" else edgar_request()
        except SECAdmissionUnavailable:
            answers.put(("denied", len(sends), decisions))
        else:
            answers.put(("response", result, len(sends), decisions))
    except Exception as exc:
        answers.put(("error", type(exc).__name__))
    finally:
        # No HTTP is ever sent by this executor. Drain any shielded feedback write
        # before disposing its engine or letting the child process exit.
        if gate_module._executor is not None:
            gate_module._executor.shutdown(wait=True)
        engine.dispose()


def _run_feedback_processes(engine, jobs):
    with engine.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar_one()
    context = multiprocessing.get_context("spawn")
    ready, answers, start = context.Queue(), context.Queue(), context.Event()
    processes = [
        context.Process(
            target=_feedback_worker,
            args=(engine.url.render_as_string(hide_password=False), schema, ready, start, answers, *job),
        )
        for job in jobs
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


def _cooldown_state(engine):
    table = _table(engine)
    with engine.connect() as conn:
        return conn.execute(select(table.c.cooldown_until).where(table.c.id == 1)).scalar_one()


@pytest.mark.parametrize("sender,receiver,status", [
    ("own", "edgar_sync", 429),
    ("own", "edgar_async", 503),
    ("edgar_sync", "own", 429),
    ("edgar_async", "own", 503),
])
def test_response_cooldown_blocks_other_process_transport(postgres_engine, sender, receiver, status):
    sent, = _run_feedback_processes(postgres_engine, [("request", sender, status, "60")])
    assert sent[0] == "response" and sent[1] == status and sent[2] == 1
    denied, = _run_feedback_processes(postgres_engine, [("receive", receiver, 200, "0")])
    assert denied[0] == "denied" and denied[1] == 0
    # This proves the receiver reached the persisted shared embargo, not merely
    # an unrelated local timeout before its first DB decision.
    assert any(wait_seconds > 30 and not granted for wait_seconds, granted in denied[2])


def test_competing_feedback_and_migration_replay_cannot_shorten_cooldown(postgres_engine):
    result, = _run_feedback_processes(postgres_engine, [("write", "own", 429, "3600")])
    assert result == ("written",)
    expected = _cooldown_state(postgres_engine)
    results = _run_feedback_processes(postgres_engine, [
        ("write", "own", 429, "1"),
        ("write", "edgar_sync", 503, "2"),
    ])
    assert results == [("written",), ("written",)]
    assert _cooldown_state(postgres_engine) == expected
    with postgres_engine.begin() as conn:
        conn.exec_driver_sql(COOLDOWN_MIGRATION.read_text(encoding="utf-8"))
    assert _cooldown_state(postgres_engine) == expected


def test_extreme_valid_retry_after_persists_server_infinity_without_integer_cap(postgres_engine):
    result, = _run_feedback_processes(postgres_engine, [("write", "own", 429, "9" * 5000)])
    assert result == ("written",)
    table = _table(postgres_engine)
    with postgres_engine.connect() as conn:
        # PostgreSQL infinity, rather than a finite Python datetime cap, preserves
        # an unrepresentable but valid positive server delay conservatively.
        assert conn.execute(select(func.isfinite(table.c.cooldown_until)).where(table.c.id == 1)).scalar_one() is False
    result, = _run_feedback_processes(postgres_engine, [("write", "edgar_sync", 503, "1")])
    assert result == ("written",)
    with postgres_engine.connect() as conn:
        assert conn.execute(select(func.isfinite(table.c.cooldown_until)).where(table.c.id == 1)).scalar_one() is False
    decision = PostgresRequestGate(postgres_engine).try_grant()
    assert decision.granted_at is None and decision.wait_seconds > 3600

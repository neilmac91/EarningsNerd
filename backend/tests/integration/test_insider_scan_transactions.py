"""The insider scan on PostgreSQL (ADR 0009): one claim wins a race, a step runs, the migration matches the models.

INSIDER_SCAN_TEST_DATABASE_URL arms the required CI gate. Each test owns a disposable schema and uses production
SessionLocal settings. The race holds the first claim's commit until PostgreSQL shows the second one waiting on
the scan row, rather than trusting a scheduling sleep. SQLite, which the unit tests use, proves none of this: it
has no row lock, no time zone on a stored time and no NULLS LAST.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models.insider import InsiderFiling, InsiderScan, InsiderTransaction
from app.services import insider_scan_service as scan_service
from app.services.insider_scan_service import LEASE, ListedFiling, run_scan_step
from tests.support.form4_documents import form4, trade
from tests.support.hang_guard import HANG_GUARD_S

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
CIK = "999999"
TABLES = ("earningsnerd_insider_filings", "earningsnerd_insider_transactions", "earningsnerd_insider_scans")
MIGRATION = Path(__file__).resolve().parents[2] / "migrations/20261114_earningsnerd_insider_tables.sql"


@pytest.fixture
def postgres_engine():
    url = os.environ.get("INSIDER_SCAN_TEST_DATABASE_URL")
    if not url:
        pytest.skip("INSIDER_SCAN_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql"
    schema = "insider_scan_" + uuid4().hex
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(engine):
    return sessionmaker(**{**SessionLocal.kw, "bind": engine})()


def test_two_steps_claiming_one_scan_at_once_leave_exactly_one_owner(postgres_engine):
    with _session(postgres_engine) as db:
        scan_service.get_or_create_scan(db, CIK, NOW)
    held, release, second_started = threading.Event(), threading.Event(), threading.Event()
    second_pid = []

    def first():
        with _session(postgres_engine) as db:
            def before_commit(_):
                held.set()
                assert release.wait(HANG_GUARD_S), "The contender never reached the scan row"
            event.listen(db, "before_commit", before_commit, once=True)
            return scan_service._claim(db, CIK, "first", NOW)

    def second():
        assert held.wait(HANG_GUARD_S)
        with _session(postgres_engine) as db:
            second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            second_started.set()
            return scan_service._claim(db, CIK, "second", NOW)

    with ThreadPoolExecutor(max_workers=2) as executor:
        leader, follower = executor.submit(first), executor.submit(second)
        try:
            assert second_started.wait(HANG_GUARD_S)
            deadline, blocked = time.monotonic() + HANG_GUARD_S, False
            with postgres_engine.connect() as observer:
                while not follower.done() and time.monotonic() < deadline:
                    observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    wait = observer.execute(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                                            {"pid": second_pid[0]}).scalar_one_or_none()
                    observer.commit()
                    if wait == "Lock":
                        blocked = True
                        break
            assert blocked, "The second claim did not wait on the scan row"
        finally:
            release.set()
        assert (leader.result(timeout=HANG_GUARD_S), follower.result(timeout=HANG_GUARD_S)) == (True, False)

    with _session(postgres_engine) as db:
        scan = db.query(InsiderScan).one()
        assert (scan.lease_token, scan.lease_until) == ("first", NOW + LEASE)
        # The loser's fenced writes change nothing; the owner's do.
        assert scan_service._write_scan(db, CIK, "second", NOW, error_code="x") is False
        assert scan_service._write_scan(db, CIK, "first", NOW, error_code="mine") is True
        db.commit()
        assert db.query(InsiderScan).one().error_code == "mine"


def test_two_first_requests_for_an_issuer_create_one_scan_row(postgres_engine):
    start = threading.Barrier(2)

    def create():
        with _session(postgres_engine) as db:
            start.wait(HANG_GUARD_S)
            return scan_service.get_or_create_scan(db, CIK, NOW).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = [future.result(timeout=HANG_GUARD_S) for future in (executor.submit(create), executor.submit(create))]
    assert ids[0] == ids[1]
    with _session(postgres_engine) as db:
        assert db.query(InsiderScan).count() == 1


@pytest.mark.asyncio
async def test_a_scan_runs_to_the_end_and_waits_out_a_pause_on_postgres(postgres_engine):
    listed = [ListedFiling(f"0000999999-26-{n:06d}", date(2026, 10, n) if n > 1 else None, "xslF345X05/form4.xml")
              for n in (3, 2, 1)]
    fetched = []

    async def list_filings(cik):
        return listed

    async def fetch(url):
        fetched.append(url)
        if len(fetched) == 2:
            from app.services.edgar.exceptions import EdgarRateLimitError

            raise EdgarRateLimitError(retry_after=1200)
        return form4(trades=[trade("P", "100", "10.50", "2026-10-01")])

    with _session(postgres_engine) as db:
        first = await run_scan_step(db, CIK, now=NOW, list_filings=list_filings, fetch_document=fetch)
        assert (first.stored, first.stopped, first.remaining) == (1, "sec_429", 2)
        scan = db.query(InsiderScan).one()
        assert (scan.status, scan.paused_until, scan.lease_token) == ("paused", NOW + timedelta(minutes=20), None)

        waiting = await run_scan_step(db, CIK, now=NOW + timedelta(minutes=19), list_filings=list_filings, fetch_document=fetch)
        assert (waiting.outcome, waiting.requests, len(fetched)) == ("paused", 0, 2)

        done = await run_scan_step(db, CIK, now=NOW + timedelta(minutes=20), list_filings=list_filings, fetch_document=fetch)
        assert (done.outcome, done.stored, done.remaining) == ("ran", 2, 0)
        db.expire_all()
        assert db.query(InsiderScan).one().status == "idle"
        # A filing with no date sorts after the dated ones: it was the last one fetched.
        assert fetched[-1].endswith("/000099999926000001/form4.xml")
        row = db.query(InsiderTransaction).filter_by(accession="0000999999-26-000003").one()
        assert (row.transaction_date, row.filed_date, row.price, row.is_10b5_1) == (date(2026, 10, 1), date(2026, 10, 3), 10.5, False)
        assert {filing.status for filing in db.query(InsiderFiling)} == {"ok"}


def _schema_contract(engine):
    inspector = inspect(engine)
    return {
        name: {
            "columns": [(row["name"], str(row["type"]), row["nullable"], row["default"]) for row in inspector.get_columns(name)],
            "primary_key": inspector.get_pk_constraint(name)["constrained_columns"],
            "unique": sorted((row["name"], tuple(row["column_names"])) for row in inspector.get_unique_constraints(name)),
            "checks": sorted(row["sqltext"] for row in inspector.get_check_constraints(name)),
            "foreign_keys": inspector.get_foreign_keys(name),
            "indexes": sorted((row["name"], tuple(row["column_names"]), row["unique"]) for row in inspector.get_indexes(name)),
        }
        for name in TABLES
    }


def test_the_migration_builds_what_the_models_build_and_replays_over_stored_rows(postgres_engine):
    from_models = _schema_contract(postgres_engine)
    assert all(from_models[name]["columns"] for name in TABLES)
    with _session(postgres_engine) as db:
        db.add(InsiderFiling(accession="0000999999-26-000001", issuer_cik=CIK, status="listed", created_at=NOW, updated_at=NOW))
        db.commit()

    for _ in range(3):   # production replays a file after a ledger reset: nothing changes, no row is lost
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(MIGRATION.read_text())
    assert _schema_contract(postgres_engine) == from_models
    with _session(postgres_engine) as db:
        assert db.query(InsiderFiling).count() == 1

    # Production gets these tables from the migration alone, never from create_all.
    with postgres_engine.begin() as connection:
        for table in (InsiderTransaction.__table__, InsiderFiling.__table__, InsiderScan.__table__):
            table.drop(connection)
        connection.exec_driver_sql(MIGRATION.read_text())
    assert _schema_contract(postgres_engine) == from_models
    with _session(postgres_engine) as db:
        scan = scan_service.get_or_create_scan(db, CIK, NOW)
        assert (scan.pauses, scan.steps) == (0, 0)

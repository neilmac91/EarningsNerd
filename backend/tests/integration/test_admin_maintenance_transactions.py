"""E171: the admin maintenance lock on PostgreSQL. The summary delete, the XBRL clear, the filing reset, the stale-XBRL
bulk reset and the summaries' reset-all run one at a time, so a reset-all and a summary delete of one of its filings
no longer deadlock, and two of them never both report the rows one deleted.

Since E171's admin slice the admin router runs each of these in the thread pool, so on one instance they overlap, as
they always could across the API's two. A reset-all deletes progress rows before summaries, and a summary delete or
filing reset deletes the summary first; overlapping, they deadlocked, and two resets each reported, and a reset-all
audited, rows the other had deleted. ``admin_filing_service.lock_maintenance`` takes one transaction-level advisory
lock before each write's first read. The cases:

- the control: without the lock, a summary delete waiting for its summary row, which another transaction holds, and
  a reset-all that arrives behind it deadlock, so the case after it is not passing on writers that never met;
- each write waits for the lock while another transaction holds it, and the dry runs and the stale-XBRL audit, which
  only read, do not;
- with the lock, the control's summary delete and reset-all both succeed, the reset-all after the delete;
- two reset-alls at once: one deletes every summary and its plan counts them, and the other's plan is empty;
- two of one write at once, for the summary delete, the XBRL clear, the filing reset and the bulk reset: one reports
  what it deleted or cleared, and the other finds nothing. A write that read before it took the lock would read what
  the first then deleted, and both would report it.

The cases that race two writers start both while another transaction holds the lock, and assert that both waited for
it, so a case whose writers never met there fails rather than passes. Every case takes the same lock key in one
database, and a run under pytest.ini's ``-n auto``, the default for a run by hand, runs the cases at once on its
workers (CI's step runs them one at a time), so a wait counts only the case's own sessions, which name themselves after
its schema (``application_name``). ADMIN_MAINTENANCE_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI ("Verify
admin maintenance concurrency on PostgreSQL"); each case owns a disposable schema, and without the variable they skip.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import bindparam, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import Company, Filing, FilingContentCache, Summary, SummaryGenerationProgress
from app.services import admin_filing_service, admin_summary_service
from app.utils.datetimes import utcnow

ACTOR = SimpleNamespace(id=0)  # the admin a write logs; nothing reads the account
# "MAINTAIN" in ASCII, pinned here rather than read from the module under test, so a changed key fails: a write that
# took another key, another lock's among them, would not wait for this one.
MAINTENANCE_LOCK_KEY = int.from_bytes(b"MAINTAIN", "big")
# The case's other sessions waiting for a heavyweight lock of one kind: "advisory" for the maintenance lock, a row's
# "transactionid" or "tuple" for a row another transaction holds. The checking connection is the case's own, so its
# application_name is the case's schema.
WAITING = text(
    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND wait_event IN :events"
    " AND application_name = current_setting('application_name') AND pid <> pg_backend_pid()"
).bindparams(bindparam("events", expanding=True))
ADVISORY = ("advisory",)
ROW = ("transactionid", "tuple")


@pytest.fixture
def postgres_engine():
    url = os.environ.get("ADMIN_MAINTENANCE_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ADMIN_MAINTENANCE_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "The admin maintenance gate requires PostgreSQL"
    schema = f"admin_maintenance_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=30000",
                                              "application_name": schema})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        with _session(engine) as db:
            company = Company(cik="5", ticker="ADMT", name="Admin maintenance")
            db.add(company)
            db.flush()
            for index in range(3):
                # Each filing's XBRL trails its period by ten years, so the bulk reset finds all three.
                filing = Filing(company_id=company.id, accession_number=f"0000000005-26-00000{index}",
                                filing_type="10-K", filing_date=utcnow(), period_end_date=utcnow(),
                                sec_url=f"https://example.test/admt/{index}/",
                                document_url=f"https://example.test/admt/{index}.htm",
                                xbrl_data={"revenue": [{"period": "2015-12-31", "value": 1}]})
                db.add(filing)
                db.flush()
                db.add(Summary(filing_id=filing.id, business_overview="# Summary", raw_summary={}))
                db.add(SummaryGenerationProgress(filing_id=filing.id, stage="completed", started_at=utcnow(),
                                                 updated_at=utcnow()))
                db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="Revenue was $1.0 million."))
            db.commit()
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


def _filing_ids(engine) -> list[int]:
    with _session(engine) as db:
        return [filing_id for (filing_id,) in db.query(Filing.id).order_by(Filing.id)]


def _summaries(engine) -> int:
    with _session(engine) as db:
        return db.query(Summary).count()


def _reset_all(db: Session) -> admin_summary_service.ResetAllPlan:
    """The reset-all route's unit without its audit row: the plan, read under the lock, then its delete."""
    plan = admin_summary_service.select_reset_candidates(db, filing_type=None, include_saved=False, for_delete=True)
    if plan.delete_ids:
        admin_summary_service.delete_summaries(db, plan)
    return plan


def _summary_delete(filing_id: int):
    def write(db: Session) -> bool:
        return admin_filing_service.delete_filing_summary(db, filing_id, actor=ACTOR)
    return write


def _run(engine, write):
    """Runs one write on a session of its own; returns (its result, None) or (None, the error it raised)."""
    try:
        with _session(engine) as db:
            return write(db), None
    except Exception as exc:  # noqa: BLE001 - the case asserts on what each write raised
        return None, exc


def _waiting(engine, events: tuple[str, ...], sessions: int) -> bool:
    """Whether, within 5 s, at least ``sessions`` of the case's other sessions wait for a lock of ``events``."""
    deadline = time.monotonic() + 5
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(WAITING, {"events": list(events)}).scalar()
            conn.rollback()  # PostgreSQL reads pg_stat_activity once a transaction: each poll reads it afresh
            if waiting >= sessions:
                return True
            time.sleep(0.002)
    return False


class _Holder:
    """Another transaction holding a lock, on a thread of its own, until ``release``: the maintenance lock, or one
    filing's summary row (``SELECT ... FOR UPDATE``). A case enters it after its thread pool, so a failed assertion
    releases it before the pool waits for writes that wait for it."""

    def __init__(self, engine, summary_of_filing: int | None = None):
        self.engine = engine
        self.summary_of_filing = summary_of_filing
        self.held = threading.Event()
        self.released = threading.Event()
        self.thread = threading.Thread(target=self._hold)

    def _hold(self) -> None:
        with self.engine.connect() as conn:
            with conn.begin():
                if self.summary_of_filing is None:
                    conn.execute(select(func.pg_advisory_xact_lock(MAINTENANCE_LOCK_KEY)))
                else:
                    conn.execute(text("SELECT id FROM summaries WHERE filing_id = :filing FOR UPDATE"),
                                 {"filing": self.summary_of_filing})
                self.held.set()
                self.released.wait(timeout=30)

    def __enter__(self) -> "_Holder":
        self.thread.start()
        assert self.held.wait(timeout=5), "the holder must take its lock"
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def release(self) -> None:
        self.released.set()
        self.thread.join(timeout=30)


def _two_writes_behind_the_lock(engine, first, second) -> tuple[list, list]:
    """Starts both writes while another transaction holds the maintenance lock, asserts both wait for it, releases it;
    returns each write's result and error."""
    with ThreadPoolExecutor(max_workers=2) as pool, _Holder(engine) as holder:
        futures = [pool.submit(_run, engine, first), pool.submit(_run, engine, second)]
        waited = _waiting(engine, ADVISORY, 2)
        holder.release()
        outcomes = [future.result(timeout=60) for future in futures]
    assert waited, "both writes must wait for the maintenance lock while another transaction holds it"
    return [result for result, _ in outcomes], [error for _, error in outcomes]


def _summary_delete_then_reset_all(engine) -> tuple[list, list]:
    """A summary delete of the first filing waits for its summary row, which another transaction holds; a reset-all
    arrives behind it, and the row is released once the reset-all waits too (for the maintenance lock, or, without
    it, for the same row). Returns each write's result and error."""
    first = _filing_ids(engine)[0]
    with ThreadPoolExecutor(max_workers=2) as pool, _Holder(engine, summary_of_filing=first) as holder:
        delete = pool.submit(_run, engine, _summary_delete(first))
        assert _waiting(engine, ROW, 1), "the summary delete must wait for the held summary row"
        reset_all = pool.submit(_run, engine, _reset_all)
        assert _waiting(engine, ADVISORY + ROW, 2), "the reset-all must wait behind the summary delete"
        holder.release()
        outcomes = [delete.result(timeout=60), reset_all.result(timeout=60)]
    return [result for result, _ in outcomes], [error for _, error in outcomes]


def test_without_the_lock_a_summary_delete_and_a_reset_all_deadlock(postgres_engine, monkeypatch):
    """The control: with no lock, the reset-all deletes the filings' progress rows, the summary delete's among them,
    then waits for the summary row the summary delete is waiting for; once the row is released, the summary delete
    deletes it and waits for its progress row, and PostgreSQL ends one of the two (40P01)."""
    monkeypatch.setattr(admin_filing_service, "lock_maintenance", lambda db: None)
    _, errors = _summary_delete_then_reset_all(postgres_engine)
    failed = [error for error in errors if error is not None]
    assert len(failed) == 1 and isinstance(failed[0], OperationalError), errors
    assert failed[0].orig.pgcode == "40P01", repr(failed[0].orig)


WRITES = {
    "summary delete": lambda ids: _summary_delete(ids[0]),
    "XBRL clear": lambda ids: lambda db: admin_filing_service.clear_filing_xbrl(db, ids[0]),
    "filing reset": lambda ids: lambda db: admin_filing_service.reset_filing(db, ids[0]),
    "bulk reset": lambda ids: lambda db: admin_filing_service.bulk_reset_stale_xbrl(
        db, year_threshold=1, dry_run=False, actor=ACTOR),
    "reset-all": lambda ids: _reset_all,
}
READS = {
    "bulk reset dry run": lambda db: admin_filing_service.bulk_reset_stale_xbrl(
        db, year_threshold=1, dry_run=True, actor=ACTOR),
    "reset-all dry run": lambda db: admin_summary_service.select_reset_candidates(
        db, filing_type=None, include_saved=False),
    "stale-XBRL audit": lambda db: admin_filing_service.audit_stale_xbrl(db, year_threshold=1),
}


@pytest.mark.parametrize("write", sorted(WRITES))
def test_each_maintenance_write_waits_for_the_lock(postgres_engine, write):
    """The write starts while another transaction holds the maintenance lock, waits for it, and finishes once it is
    released."""
    run = WRITES[write](_filing_ids(postgres_engine))
    with ThreadPoolExecutor(max_workers=1) as pool, _Holder(postgres_engine) as holder:
        future = pool.submit(_run, postgres_engine, run)
        waited = _waiting(postgres_engine, ADVISORY, 1)
        finished_while_held = future.done()
        holder.release()
        _, error = future.result(timeout=60)
    assert waited and not finished_while_held, f"the {write} must wait for the maintenance lock"
    assert error is None, error


@pytest.mark.parametrize("read", sorted(READS))
def test_the_dry_runs_and_the_audit_take_no_lock(postgres_engine, read):
    """A read finishes while another transaction holds the maintenance lock."""
    with ThreadPoolExecutor(max_workers=1) as pool, _Holder(postgres_engine):
        _, error = pool.submit(_run, postgres_engine, READS[read]).result(timeout=10)
    assert error is None, error


def test_with_the_lock_a_summary_delete_and_a_reset_all_both_succeed(postgres_engine):
    """The control's two writes: the reset-all waits for the lock the summary delete holds, then plans the two
    summaries left and deletes them."""
    ids = _filing_ids(postgres_engine)
    results, errors = _summary_delete_then_reset_all(postgres_engine)
    assert errors == [None, None], errors
    deleted, plan = results
    assert deleted is True
    assert plan.delete_filing_ids == ids[1:], plan
    assert _summaries(postgres_engine) == 0


def test_two_reset_alls_count_their_deletes_once(postgres_engine):
    """The second reset-all plans after the first's delete has committed, finds nothing and deletes nothing, so the
    route answers and audits each summary once."""
    results, errors = _two_writes_behind_the_lock(postgres_engine, _reset_all, _reset_all)
    assert errors == [None, None], errors
    assert sorted(len(plan.delete_ids) for plan in results) == [0, 3], results
    assert _summaries(postgres_engine) == 0


# Each write that reports what it found, and how its report says it found something.
REPORTED = {
    "summary delete": (lambda ids: _summary_delete(ids[0]), lambda deleted: deleted),
    "XBRL clear": (lambda ids: lambda db: admin_filing_service.clear_filing_xbrl(db, ids[0]), lambda had: had),
    "filing reset": (lambda ids: lambda db: admin_filing_service.reset_filing(db, ids[0]),
                     lambda deleted: deleted["summary"]),
    "bulk reset": (lambda ids: lambda db: admin_filing_service.bulk_reset_stale_xbrl(
        db, year_threshold=1, dry_run=False, actor=ACTOR), lambda affected: affected),
}


@pytest.mark.parametrize("write", sorted(REPORTED))
def test_two_of_one_write_at_once_report_what_they_found_once(postgres_engine, write):
    """The second reads after the first's commit and finds nothing to delete or clear, so only one reports it."""
    make, found = REPORTED[write]
    run = make(_filing_ids(postgres_engine))
    results, errors = _two_writes_behind_the_lock(postgres_engine, run, run)
    assert errors == [None, None], errors
    assert sorted(bool(found(result)) for result in results) == [False, True], results

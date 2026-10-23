"""E161: E153's filing-insert lock on PostgreSQL. Two companies' writers of the same co-registrant filings, each held
after its check until the other has checked too, keep both their batches and store each filing once.

A co-registrant filing is one accession listed under two companies' CIKs. Each company's writers serialize on its row
lock (``lock_company_filings``, E123), so the two companies' writers check under two locks and can both find the
accession missing. ``filing_amendment_service.existing_filings_for_insert`` then has a writer with anything to insert
take one transaction-level advisory lock and read the missing accessions again: the second writer waits there, sees the
first one's commit (READ COMMITTED) and inserts only what is still missing. ``test_filing_inserts_lock_across_companies.py``
holds each writer's statements against a stand-in for the lock; this home holds what PostgreSQL does with them. The
hold picks which writer takes the insert lock first and keeps it there, the lock granted, until PostgreSQL shows the
other writer waiting for it, so each race runs with either writer holding the lock:

- the control: with the read every writer made before E153 (no lock, no second read), both writers still find the
  accession missing when they are held, and the second one's batch fails the unique accession, so the other cases are
  not passing on writers that never met;
- two companies' writers of two co-registrant accessions, listed in opposite orders, each with a filing of its own
  beside them, the scan's against the scan's and the live listing's against the scan's: both succeed, and each shared
  filing is stored once, under the company whose writer held the lock;
- a backfill-sized batch carrying a shared accession against a one-row writer of it: both succeed, every row stored.

Each race case also asserts that both writers found the accessions missing at their check, and that the other writer
waited at the insert lock while the holder held it, so a case whose writers did not meet there fails rather than
passes. FILING_INSERT_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI ("Verify filing insert concurrency on
PostgreSQL"); each case owns a disposable schema, and without the variable they skip.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import Company, Filing
from app.services import filing_amendment_service, filing_list_service
from app.services.filing_scan_service import upsert_filings

PARENT, SUBSIDIARY = "XPAR", "YSUB"  # two registrants of one combined filing
# A session waiting for the filing-insert lock. PostgreSQL lists a one-bigint advisory key as its high and low halves.
WAITING_FOR_THE_INSERT_LOCK = text(
    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted AND objsubid = 1"
    " AND database = (SELECT oid FROM pg_database WHERE datname = current_database())"
    " AND classid::bigint = :high AND objid::bigint = :low"
)


@pytest.fixture
def postgres_engine():
    url = os.environ.get("FILING_INSERT_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("FILING_INSERT_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "The filing insert gate requires PostgreSQL"
    schema = f"filing_insert_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=30000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        with _session(engine) as db:
            db.add_all([Company(cik="1", ticker=PARENT, name="X Parent"),
                        Company(cik="2", ticker=SUBSIDIARY, name="Y Subsidiary")])
            db.commit()
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


def _row(accession: str, form: str = "10-K") -> dict:
    """One filing as an SEC listing gives it."""
    return {"accession_number": accession, "filing_type": form, "filing_date": "2026-01-15",
            "report_date": "2025-12-31", "sec_url": f"https://sec.example/{accession}/",
            "document_url": f"https://sec.example/{accession}/a.htm"}


def _scan(ticker: str, rows: list[dict]):
    """The scan's writer, ``upsert_filings``, which the list's background refresh, the history backfill and the durable
    worker write through."""
    def write(db: Session) -> None:
        upsert_filings(db, db.query(Company).filter_by(ticker=ticker).one(), rows)
    return write


def _live_listing(ticker: str, rows: list[dict]):
    """The live listing's writer, ``persist_live_filings``."""
    def write(db: Session) -> None:
        company = db.query(Company).filter_by(ticker=ticker).one()
        filing_list_service.persist_live_filings(
            db, ticker, ["10-K"], company.id, rows, None, lambda filing: filing.accession_number,
        )
    return write


class _HoldAfterCheck:
    """Holds each writer's thread after its check, its first read of filings by accession once it has locked its
    company, until every writer has made its own or 5 s pass, so each checks before any inserts, and records how many
    of its accessions each check found stored. At the insert lock it lets the holder take the lock first, then keeps
    the holder there, the lock granted, until PostgreSQL shows another session waiting for it or 5 s pass, and records
    whether one did. With no holder, it leaves the insert lock alone."""

    def __init__(self, engine, writers: int, holder: int | None):
        self.engine = engine
        self.holder = holder
        self.barrier = threading.Barrier(writers, timeout=5)
        self.holder_locked = threading.Event()
        self.local = threading.local()
        self.found: list[int] = []
        self.waited = False

    def __call__(self, state):
        sql = str(state.statement.compile(dialect=state.session.get_bind().dialect))
        if "pg_advisory_xact_lock" in sql and self.holder is not None:
            if self.local.index != self.holder:
                self.holder_locked.wait(timeout=5)  # the holder takes the lock first
                return None
            granted = state.invoke_statement().freeze()
            self.holder_locked.set()
            self.waited = self._a_session_waits_for_the_insert_lock()
            return granted()
        if "FROM companies" in sql and "FOR NO KEY UPDATE" in sql:
            self.local.locked = True
            return None
        if (state.is_select and "WHERE filings.accession_number" in sql
                and getattr(self.local, "locked", False) and not getattr(self.local, "held", False)):
            self.local.held = True
            result = state.invoke_statement().freeze()
            self.found.append(len(result().all()))
            try:
                self.barrier.wait()
            except threading.BrokenBarrierError:
                pass  # the other writer never checked; the case's assertion on `found` fails it
            return result()
        return None

    def _a_session_waits_for_the_insert_lock(self) -> bool:
        key = filing_amendment_service.FILING_INSERT_LOCK_KEY
        deadline = time.monotonic() + 5
        with self.engine.connect() as conn:
            while time.monotonic() < deadline:
                if conn.execute(WAITING_FOR_THE_INSERT_LOCK, {"high": key >> 32, "low": key & 0xFFFFFFFF}).scalar():
                    return True
                time.sleep(0.002)
        return False


def _write(engine, hold: _HoldAfterCheck, index: int, writer):
    """Runs one writer, the hold's writer ``index``, on a session of its own; returns the error it raised, or None."""
    hold.local.index = index
    try:
        with _session(engine) as db:
            writer(db)
    except Exception as exc:  # noqa: BLE001 - the case asserts on what each writer raised
        return exc
    return None


def _race(engine, writers: list, holder: int | None) -> tuple[list[int], list, bool]:
    """Runs the writers at once, one thread and session each, each held after its check, ``writers[holder]`` taking the
    insert lock first; returns what each check found stored, each writer's error, and whether another session waited
    for the insert lock while the holder held it."""
    hold = _HoldAfterCheck(engine, len(writers), holder)
    event.listen(Session, "do_orm_execute", hold)
    try:
        with ThreadPoolExecutor(max_workers=len(writers)) as pool:
            futures = [pool.submit(_write, engine, hold, index, writer) for index, writer in enumerate(writers)]
            errors = [future.result(timeout=60) for future in futures]
    finally:
        event.remove(Session, "do_orm_execute", hold)
    return hold.found, errors, hold.waited


def _stored(engine) -> dict[str, str]:
    """Each stored filing's accession, with the ticker of the company it is stored under."""
    with _session(engine) as db:
        return dict(db.query(Filing.accession_number, Company.ticker).join(Company, Filing.company_id == Company.id))


def test_without_the_lock_the_second_writer_fails_its_batch(postgres_engine, monkeypatch):
    """The control: the writers' read before E153, which neither locks nor reads again. Both writers find the shared
    accession missing when they are held, and the second insert fails the unique accession, rolling back its batch, so
    the race cases below are not passing on writers that never met. It shares one accession: two shared in opposite
    orders can deadlock without the lock, rather than fail the unique accession."""
    def read_without_the_lock(db, accessions):
        found = db.query(Filing).filter(Filing.accession_number.in_(accessions)).all() if accessions else []
        return {filing.accession_number: filing for filing in found}

    monkeypatch.setattr(filing_amendment_service, "existing_filings_for_insert", read_without_the_lock)
    found, errors, _ = _race(
        postgres_engine,
        [_scan(PARENT, [_row("shared"), _row("parent-own")]),
         _scan(SUBSIDIARY, [_row("shared"), _row("subsidiary-own")])],
        holder=None,
    )
    assert found == [0, 0], found
    assert [type(error) for error in errors].count(IntegrityError) == 1, errors
    assert "UniqueViolation" in repr([error for error in errors if error is not None][0].orig)
    assert len(_stored(postgres_engine)) == 2, "the failed writer's own filing was rolled back with the shared one"


@pytest.mark.parametrize("holder", [0, 1], ids=["the parent holds the lock", "the subsidiary holds the lock"])
@pytest.mark.parametrize("first", [_scan, _live_listing], ids=["the scan", "the live listing"])
def test_two_companies_writers_of_co_registrant_filings_keep_both_batches(
        postgres_engine, monkeypatch, first, holder):
    """The writers list the two shared accessions in opposite orders, so a writer whose second read kept fewer than
    every stored one would insert one again."""
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})  # the live listing stamps its listing fresh
    found, errors, waited = _race(
        postgres_engine,
        [first(PARENT, [_row("shared"), _row("also-shared"), _row("parent-own")]),
         _scan(SUBSIDIARY, [_row("also-shared"), _row("shared"), _row("subsidiary-own")])],
        holder,
    )
    assert found == [0, 0], f"both writers must check before either inserts: {found}"
    assert waited, "the other writer must wait at the insert lock while the holder holds it"
    assert errors == [None, None], errors
    shared_under = (PARENT, SUBSIDIARY)[holder]
    assert _stored(postgres_engine) == {"shared": shared_under, "also-shared": shared_under,
                                        "parent-own": PARENT, "subsidiary-own": SUBSIDIARY}


@pytest.mark.parametrize("holder", [0, 1], ids=["the batch holds the lock", "the one-row writer holds the lock"])
def test_a_backfill_sized_batch_and_a_one_row_writer_of_its_shared_filing_both_succeed(postgres_engine, holder):
    """A history backfill or a first listing inserts hundreds of filings in one transaction, under the one insert lock.
    With the batch holding it, the one-row writer waits out the whole batch, finds its filing stored and inserts
    nothing, and its session's close ends its transaction."""
    batch = [_row(f"backfill-{index:04d}", "8-K") for index in range(1000)] + [_row("shared")]
    found, errors, waited = _race(postgres_engine, [_scan(PARENT, batch), _scan(SUBSIDIARY, [_row("shared")])], holder)
    assert found == [0, 0], f"both writers must check before either inserts: {found}"
    assert waited, "the other writer must wait at the insert lock while the holder holds it"
    assert errors == [None, None], errors
    stored = _stored(postgres_engine)
    assert len(stored) == 1001 and stored["shared"] == (PARENT, SUBSIDIARY)[holder], (len(stored), stored.get("shared"))

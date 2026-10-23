"""E161: E153's filing-insert lock on PostgreSQL. Two companies' writers of one co-registrant filing, each held after
its check until the other has checked too, keep both their batches and store the filing once.

A co-registrant filing is one accession listed under two companies' CIKs. Each company's writers serialize on its row
lock (``lock_company_filings``, E123), so the two companies' writers check under two locks and can both find the
accession missing. ``filing_amendment_service.existing_filings_for_insert`` then has a writer with anything to insert
take one transaction-level advisory lock and read the missing accessions again: the second writer waits there, sees the
first one's commit (READ COMMITTED) and inserts only what is still missing. ``test_filing_inserts_lock_across_companies.py``
holds each writer's statements against a stand-in for the lock; this home holds what PostgreSQL does with them:

- the control: with the read every writer made before E153 (no lock, no second read), both writers still find the
  accession missing when they are held, and the second one's batch fails the unique accession, so the other cases are
  not passing on writers that never met;
- two companies' writers of one co-registrant accession, each with a filing of its own beside it, the scan's against
  the scan's and the live listing's against the scan's: both succeed, and the shared filing is stored once;
- a backfill-sized batch carrying the shared accession against a one-row writer of it: both succeed, every row stored.

Each race case also asserts that both writers found the accessions missing at their check, so a case whose writers did
not meet fails rather than passes. FILING_INSERT_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI ("Verify filing insert concurrency
on PostgreSQL"); each case owns a disposable schema, and without the variable they skip.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import Company, Filing
from app.services import filing_amendment_service, filing_list_service
from app.services.filing_scan_service import upsert_filings

PARENT, SUBSIDIARY = "XPAR", "YSUB"  # two registrants of one combined filing


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
    company, until every writer has made its own or 5 s pass, so each checks before any inserts. Records how many of
    its accessions each check found stored."""

    def __init__(self, writers: int):
        self.barrier = threading.Barrier(writers, timeout=5)
        self.local = threading.local()
        self.found: list[int] = []

    def __call__(self, state):
        sql = str(state.statement.compile(dialect=state.session.get_bind().dialect))
        if "FROM companies" in sql and "FOR NO KEY UPDATE" in sql:
            self.local.locked = True
            return None
        if (state.is_select and "FROM filings" in sql and "accession_number" in sql
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


def _write(engine, writer):
    """Runs one writer on a session of its own; returns the error it raised, or None."""
    try:
        with _session(engine) as db:
            writer(db)
    except Exception as exc:  # noqa: BLE001 - the case asserts on what each writer raised
        return exc
    return None


def _race(engine, *writers) -> tuple[list[int], list]:
    """Runs the writers at once, one thread and session each, each held after its check; returns what each check found
    stored and each writer's error."""
    hold = _HoldAfterCheck(len(writers))
    event.listen(Session, "do_orm_execute", hold)
    try:
        with ThreadPoolExecutor(max_workers=len(writers)) as pool:
            errors = [future.result(timeout=60) for future in [pool.submit(_write, engine, w) for w in writers]]
    finally:
        event.remove(Session, "do_orm_execute", hold)
    return hold.found, errors


def _stored(engine) -> dict[str, str]:
    """Each stored filing's accession, with the ticker of the company it is stored under."""
    with _session(engine) as db:
        return dict(db.query(Filing.accession_number, Company.ticker).join(Company, Filing.company_id == Company.id))


def test_without_the_lock_the_second_writer_fails_its_batch(postgres_engine, monkeypatch):
    """The control: the writers' read before E153, which neither locks nor reads again. Both writers find the shared
    accession missing when they are held, and the second insert fails the unique accession, rolling back its batch, so
    the race cases below are not passing on writers that never met."""
    def read_without_the_lock(db, accessions):
        found = db.query(Filing).filter(Filing.accession_number.in_(accessions)).all() if accessions else []
        return {filing.accession_number: filing for filing in found}

    monkeypatch.setattr(filing_amendment_service, "existing_filings_for_insert", read_without_the_lock)
    found, errors = _race(
        postgres_engine,
        _scan(PARENT, [_row("shared"), _row("parent-own")]),
        _scan(SUBSIDIARY, [_row("shared"), _row("subsidiary-own")]),
    )
    assert found == [0, 0], found
    assert [type(error) for error in errors].count(IntegrityError) == 1, errors
    assert "UniqueViolation" in repr([error for error in errors if error is not None][0].orig)
    assert len(_stored(postgres_engine)) == 2, "the failed writer's own filing was rolled back with the shared one"


@pytest.mark.parametrize("first", [_scan, _live_listing], ids=["the scan", "the live listing"])
def test_two_companies_writers_of_one_co_registrant_filing_keep_both_batches(postgres_engine, monkeypatch, first):
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})  # the live listing stamps its listing fresh
    found, errors = _race(
        postgres_engine,
        first(PARENT, [_row("shared"), _row("parent-own")]),
        _scan(SUBSIDIARY, [_row("shared"), _row("subsidiary-own")]),
    )
    assert found == [0, 0], f"both writers must check before either inserts: {found}"
    assert errors == [None, None], errors
    stored = _stored(postgres_engine)
    assert sorted(stored) == ["parent-own", "shared", "subsidiary-own"], stored
    assert (stored["parent-own"], stored["subsidiary-own"]) == (PARENT, SUBSIDIARY)


def test_a_backfill_sized_batch_and_a_one_row_writer_of_its_shared_filing_both_succeed(postgres_engine):
    """A history backfill or a first listing inserts hundreds of filings in one transaction, under the one insert lock."""
    batch = [_row(f"backfill-{index:04d}", "8-K") for index in range(1000)] + [_row("shared")]
    found, errors = _race(postgres_engine, _scan(PARENT, batch), _scan(SUBSIDIARY, [_row("shared")]))
    assert found == [0, 0], f"both writers must check before either inserts: {found}"
    assert errors == [None, None], errors
    stored = _stored(postgres_engine)
    assert len(stored) == 1001 and "shared" in stored, len(stored)

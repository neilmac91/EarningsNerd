"""E123's review: every writer of a company's filing rows takes the company's row lock before it reads which
of those rows exist (``filing_amendment_service.lock_company_filings``).

Read first, two writers of one company can both find a filing missing, and the second insert fails the unique
accession and rolls back its whole batch. The lock used to come after that read, so it serialized the inserts
but not the check. Since E123 the company list's background refresh and history backfill write in the thread
pool, beside the live listing's unit (E94), so the event loop no longer runs them one at a time within the
process; the row lock serializes them in every process and instance. SQLite omits ``FOR UPDATE``, so each case
reads the order of the statements its writer's session runs, compiled for PostgreSQL.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company


def _listing(accession: str) -> dict:
    return {
        "accession_number": accession, "filing_type": "10-K",
        "filing_date": "2026-01-15", "report_date": "2025-12-31",
        "sec_url": f"https://sec.example/{accession}/", "document_url": f"https://sec.example/{accession}/a.htm",
    }


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'filing-writers.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(**{**database.SessionLocal.kw, "bind": engine})
    monkeypatch.setattr(database, "SessionLocal", factory)
    with factory() as db:
        db.add(Company(cik="1", ticker="LOCKD", name="Lock Corp"))
        db.commit()
    yield factory
    engine.dispose()


def _recorded(session, statements: list[str]):
    """``session``, recording each ORM statement it runs, compiled for PostgreSQL, and each end of a transaction."""
    event.listen(session, "do_orm_execute",
                 lambda state: statements.append(str(state.statement.compile(dialect=postgresql.dialect()))))
    event.listen(session, "after_commit", lambda _session: statements.append("-- commit"))
    event.listen(session, "after_rollback", lambda _session: statements.append("-- rollback"))
    return session


def _assert_locks_before_it_checks(statements: list[str]) -> None:
    """The first read of filings follows a lock on the company that waits (no SKIP LOCKED, no NOWAIT), and no end
    of a transaction between them releases it."""
    locks = [i for i, sql in enumerate(statements)
             if "FROM companies" in sql and sql.rstrip().endswith("FOR NO KEY UPDATE")]
    checks = [i for i, sql in enumerate(statements) if "FROM filings" in sql]
    assert locks and checks and locks[0] < checks[0], "\n".join(statements)
    assert not any(sql.startswith("-- ") for sql in statements[locks[0]:checks[0]]), "\n".join(statements)


def test_the_scan_upsert_locks_before_it_checks(sessions):
    """``upsert_filings``: the filing scan, the history backfill, the list's background refresh and the
    durable worker's refresh write through it."""
    from app.services.filing_scan_service import upsert_filings

    statements: list[str] = []
    with _recorded(sessions(), statements) as db:
        company = db.query(Company).filter_by(ticker="LOCKD").one()
        upsert_filings(db, company, [_listing("lock-scan")])
    _assert_locks_before_it_checks(statements)


def test_the_live_listing_locks_before_it_checks(sessions, monkeypatch):
    from app.services import filing_list_service

    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    statements: list[str] = []
    with _recorded(sessions(), statements) as db:
        company = db.query(Company).filter_by(ticker="LOCKD").one()
        filing_list_service.persist_live_filings(
            db, "LOCKD", ["10-K"], company.id, [_listing("lock-list")], None, lambda filing: filing,
        )
    _assert_locks_before_it_checks(statements)


def test_precompute_locks_before_it_checks(sessions, monkeypatch):
    """Its write session, the one that takes the lock: its earlier read session takes none and writes nothing."""
    from app.services.edgar.compat import sec_edgar_service
    from app.services.precompute_service import precompute_one

    by_session: list[list[str]] = []

    def recording_factory():
        by_session.append([])
        return _recorded(sessions(), by_session[-1])

    monkeypatch.setattr(database, "SessionLocal", recording_factory)
    monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=[_listing("lock-precompute")]))
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", AsyncMock())
    assert asyncio.run(precompute_one("LOCKD", "10-K"))["filing_id"] is not None
    writers = [statements for statements in by_session if any("FOR NO KEY UPDATE" in sql for sql in statements)]
    assert len(writers) == 1, by_session
    _assert_locks_before_it_checks(writers[0])

"""E153: a writer of a company's filings that finds an accession missing takes the filing-insert lock
(``filing_amendment_service.existing_filings_for_insert``, a transaction-level advisory lock) after its company's row
lock, and reads the missing accessions again before it inserts, holding the lock to the commit that carries the insert.

The company row lock (``test_filing_writers_lock_before_they_check.py``) serializes one company's writers, but a
co-registrant filing, one accession listed under two companies' CIKs, is checked under two of them: two writers of the
two companies could both find it missing, and the second insert failed the unique accession and rolled back its batch.

- Each writer (the scan's ``upsert_filings``, which the list's background refresh, the history backfill and the durable
  worker write through; the live listing's ``persist_live_filings``; ``precompute_one``) takes the lock, one that
  waits, after its company lock and its check, then reads the missing accessions again, inserts and commits, with no
  end of a transaction between.
- A writer whose accessions are all stored takes no lock.
- The race, in one thread: a writer of the other company commits the accession just after a writer's check, as one that
  held the lock first would. The writer stores no second row and lists the other company's, where main's failed the
  unique accession.
- Off PostgreSQL no advisory lock is taken.
- Every function under ``app/`` that builds a filing row, by ``Filing(...)`` or by handing the model to an insert, is one
  of those three writers, so a fourth fails here until it reads through the helper and joins them. E123's gate, which
  names the same three, has no census of its own.

SQLite has no advisory locks, so the lock cases run on an engine whose dialect calls itself PostgreSQL, with a stand-in
for ``pg_advisory_xact_lock``, and read the statements each writer's session runs, compiled for PostgreSQL.
``tests/integration/test_filing_insert_transactions.py`` races two companies' writers on PostgreSQL (E161).
"""
import ast
import asyncio
from pathlib import Path
from typing import NamedTuple
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing
from app.services import filing_list_service
from app.services.filing_scan_service import upsert_filings
from app.utils.datetimes import utc_from_iso

# "FILINGS_" in ASCII, pinned here rather than read from the module under test, so a changed key fails.
INSERT_LOCK_KEY = int.from_bytes(b"FILINGS_", "big")
WRITERS = ("upsert_filings", "persist_live_filings", "precompute_one")
# Where each writer lives, under backend/: the census below holds every builder of a filing row to these.
WRITER_SITES = {
    ("app/services/filing_scan_service.py", "upsert_filings"),
    ("app/services/filing_list_service.py", "persist_live_filings"),
    ("app/services/precompute_service.py", "precompute_one"),
}
BACKEND = Path(__file__).resolve().parents[2]


class Recorded(NamedTuple):
    """One statement the session ran, compiled for PostgreSQL, with its parameters, or a ``-- flush`` (its params name
    the models it inserts), ``-- commit`` or ``-- rollback`` marker."""
    sql: str
    params: dict


def _listing(accession: str) -> dict:
    return {
        "accession_number": accession, "filing_type": "10-K",
        "filing_date": "2026-01-15", "report_date": "2025-12-31",
        "sec_url": f"https://sec.example/{accession}/", "document_url": f"https://sec.example/{accession}/a.htm",
    }


def _stored(company_id: int, accession: str) -> Filing:
    listing = _listing(accession)
    return Filing(
        company_id=company_id, accession_number=accession, filing_type=listing["filing_type"],
        filing_date=utc_from_iso(listing["filing_date"]), period_end_date=utc_from_iso(listing["report_date"]),
        sec_url=listing["sec_url"], document_url=listing["document_url"],
    )


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'filing-inserts.sqlite'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add_all([Company(cik="1", ticker="PARENT", name="Parent Corp"),
                    Company(cik="2", ticker="SUBSID", name="Subsidiary Corp")])
        db.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_named(engine):
    """``engine``, with a dialect that calls itself PostgreSQL, the name ``existing_filings_for_insert`` reads, and a
    stand-in for ``pg_advisory_xact_lock`` that SQLite runs and that returns nothing."""
    event.listen(engine, "connect",
                 lambda connection, _record: connection.create_function("pg_advisory_xact_lock", 1, lambda key: None))
    engine.dispose()  # the connections the fixture pooled have no stand-in
    engine.dialect.name = "postgresql"
    return engine


@pytest.fixture
def sessions(engine, monkeypatch):
    factory = sessionmaker(**{**database.SessionLocal.kw, "bind": engine})
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(filing_list_service, "_filings_synced_at", {})
    return factory


def _company_id(sessions, ticker: str) -> int:
    with sessions() as db:
        return db.query(Company.id).filter_by(ticker=ticker).scalar()


def _store(sessions, ticker: str, accession: str) -> int:
    with sessions() as db:
        filing = _stored(_company_id(sessions, ticker), accession)
        db.add(filing)
        db.commit()
        return filing.id


def _recorded(session, statements: list[Recorded]):
    """``session``, recording each ORM statement it runs with its parameters, each flush with the models it inserts,
    and each end of a transaction."""
    def record(state) -> None:
        compiled = state.statement.compile(dialect=postgresql.dialect())
        statements.append(Recorded(str(compiled), {**compiled.params, **(state.parameters or {})}))

    event.listen(session, "do_orm_execute", record)
    event.listen(session, "before_flush", lambda flushed, _context, _instances: statements.append(
        Recorded("-- flush", {"new": {type(instance).__name__ for instance in flushed.new}})))
    event.listen(session, "after_commit", lambda _session: statements.append(Recorded("-- commit", {})))
    event.listen(session, "after_rollback", lambda _session: statements.append(Recorded("-- rollback", {})))
    return session


def _write(writer: str, sessions, monkeypatch, accessions: list[str], *, hook=None):
    """Run ``writer`` for PARENT's listing of ``accessions`` (``precompute_one`` takes the first, as its latest
    filing); return what it returned and the statements of its session that locks the company. ``hook``, if given,
    is a ``do_orm_execute`` listener on each of the writer's sessions."""
    by_session: list[list[Recorded]] = []

    def recording_session():
        by_session.append([])
        session = _recorded(sessions(), by_session[-1])
        if hook is not None:
            event.listen(session, "do_orm_execute", hook)
        return session

    listings = [_listing(accession) for accession in accessions]
    if writer == "precompute_one":
        from app.services.edgar.compat import sec_edgar_service
        from app.services.precompute_service import precompute_one

        monkeypatch.setattr(database, "SessionLocal", recording_session)
        monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=listings[:1]))
        monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", AsyncMock())
        returned = asyncio.run(precompute_one("PARENT", "10-K"))["filing_id"]
    else:
        with recording_session() as db:
            company = db.query(Company).filter_by(ticker="PARENT").one()
            if writer == "upsert_filings":
                returned = [filing.id for filing in upsert_filings(db, company, listings)]
            else:
                returned = filing_list_service.persist_live_filings(
                    db, "PARENT", ["10-K"], company.id, listings, None, lambda filing: filing.id,
                )
    writing = [statements for statements in by_session if any(_company_lock(s) for s in statements)]
    assert len(writing) == 1, by_session
    return returned, writing[0]


def _company_lock(s: Recorded) -> bool:
    """The company's row lock, FOR NO KEY UPDATE and waiting for its holder (no SKIP LOCKED, no NOWAIT)."""
    return "FROM companies" in s.sql and s.sql.rstrip().endswith("FOR NO KEY UPDATE")


def _reads_by_accession(s: Recorded) -> bool:
    """A read of filings by their accession: a writer's check, or its second read of the missing ones."""
    return "FROM filings" in s.sql and "WHERE filings.accession_number" in s.sql


def _insert_lock(s: Recorded) -> bool:
    """The filing-insert lock: the transaction-level advisory lock that waits for its holder, not the session-level
    one, which a pooled connection would keep past the writer, and not a try that gives up, taken on its key."""
    return "pg_advisory_xact_lock(" in s.sql and "pg_try_" not in s.sql and INSERT_LOCK_KEY in s.params.values()


def _asked_for(s: Recorded) -> list[str]:
    """The accessions a read by accession asks for."""
    return sorted(value for param in s.params.values() for value in (param if isinstance(param, list) else [param])
                  if isinstance(value, str))


def _shown(statements: list[Recorded]) -> str:
    return "\n".join(f"{s.sql} {s.params}" for s in statements)


@pytest.mark.parametrize("writer", WRITERS)
def test_a_writer_locks_after_its_check_and_reads_the_missing_again_before_it_inserts(
    writer, postgres_named, sessions, monkeypatch,
):
    """The company lock, the check, the insert lock, a second read of the missing accessions only, then the insert and
    the commit, with no end of a transaction from the company lock to that commit. ``precompute_one`` checks its one
    filing, so it reads only that one twice."""
    stored = _store(sessions, "PARENT", "kept")
    accessions = ["new"] if writer == "precompute_one" else ["kept", "new"]
    returned, statements = _write(writer, sessions, monkeypatch, accessions)
    shown = _shown(statements)
    company = next(i for i, s in enumerate(statements) if _company_lock(s))
    reads = [i for i, s in enumerate(statements) if _reads_by_accession(s)]
    locks = [i for i, s in enumerate(statements) if "advisory" in s.sql]
    assert len(reads) == 2 and len(locks) == 1 and _insert_lock(statements[locks[0]]), shown
    assert company < reads[0] < locks[0] < reads[1], shown
    assert _asked_for(statements[reads[0]]) == sorted(accessions), shown
    assert _asked_for(statements[reads[1]]) == ["new"], shown
    end = next(i for i, s in enumerate(statements) if i > company and s.sql in ("-- commit", "-- rollback"))
    assert statements[end].sql == "-- commit", shown
    assert any(s.sql == "-- flush" and "Filing" in s.params["new"] for s in statements[locks[0]:end]), shown
    with sessions() as db:
        assert db.query(Filing.accession_number).order_by(Filing.accession_number).all() == [("kept",), ("new",)]
    if writer != "precompute_one":
        assert returned[0] == stored and len(returned) == 2


@pytest.mark.parametrize("writer", WRITERS[:2])
def test_a_writer_with_nothing_to_insert_takes_no_lock(writer, postgres_named, sessions, monkeypatch):
    """``precompute_one`` opens its write session only for a filing its read found missing."""
    _store(sessions, "SUBSID", "listed-twice")  # stored under the other company: a co-registrant filing
    _store(sessions, "PARENT", "kept")
    _returned, statements = _write(writer, sessions, monkeypatch, ["kept", "listed-twice"])
    assert not any("advisory" in s.sql for s in statements), _shown(statements)
    assert len([s for s in statements if _reads_by_accession(s)]) == 1, _shown(statements)


@pytest.mark.parametrize("writer", WRITERS)
def test_a_writer_that_meets_the_other_companys_commit_inserts_only_what_is_still_missing(
    writer, postgres_named, sessions, monkeypatch,
):
    """The race in one thread: just after the writer's check finds the accession missing, a writer of the other company
    commits it, as one that held the insert lock first would. The writer stores no second row, fails nothing, and
    lists the other company's row; on main the insert failed the unique accession and rolled back the batch."""
    competitor: dict = {}

    def the_other_company_commits_after_the_check(state):
        if _company_lock(Recorded(str(state.statement.compile(dialect=postgresql.dialect())), {})):
            state.session.info["company_locked"] = True
            return None
        sql = str(state.statement.compile(dialect=postgresql.dialect()))
        if competitor or not state.session.info.get("company_locked") or "WHERE filings.accession_number" not in sql:
            return None
        checked = state.invoke_statement().freeze()
        competitor["id"] = _store(sessions, "SUBSID", "listed-twice")
        return checked()

    returned, _statements = _write(writer, sessions, monkeypatch, ["listed-twice"],
                                   hook=the_other_company_commits_after_the_check)
    assert competitor, "the writer never checked the accession under its company's lock"
    assert returned == (competitor["id"] if writer == "precompute_one" else [competitor["id"]])
    with sessions() as db:
        assert db.query(Filing.id, Filing.company_id).filter_by(accession_number="listed-twice").all() == [
            (competitor["id"], _company_id(sessions, "SUBSID")),
        ]


def test_off_postgresql_a_writer_takes_no_advisory_lock(sessions, monkeypatch):
    """SQLite has no advisory locks: a writer inserts with the company lock alone, which SQLite omits too."""
    _returned, statements = _write("upsert_filings", sessions, monkeypatch, ["new"])
    assert not any("advisory" in s.sql for s in statements), _shown(statements)
    with sessions() as db:
        assert db.query(Filing.accession_number).all() == [("new",)]


def _dotted(node: ast.AST) -> str | None:
    """``a.b.c`` for a chain of names and attributes, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def _filing_builders(path: Path) -> set[str]:
    """The functions of ``path`` (by qualified name) that build an ``app.models`` Filing: they call the model, hand it
    to an insert (``insert(Filing)``, ``bulk_insert_mappings(Filing, ...)``) or call its table's ``insert()``. The model
    is reached by a name an import from ``app.models`` binds, or through the module (``models.Filing``,
    ``app.models.Filing``); the edgar layer's and edgartools' own ``Filing`` are other classes."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    model = {"app.models.Filing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "app.models" or node.module.startswith("app.models."):
                model.update(alias.asname or alias.name for alias in node.names if alias.name == "Filing")
            elif node.module == "app":
                model.update(f"{alias.asname or alias.name}.Filing" for alias in node.names if alias.name == "models")
        elif isinstance(node, ast.Import):
            model.update(f"{alias.asname}.Filing" for alias in node.names if alias.name == "app.models" and alias.asname)

    def is_model(node: ast.AST) -> bool:
        return _dotted(node) in model

    builders: set[str] = set()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = (*scope, node.name)
        if isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if (is_model(func)
                    or (called in ("insert", "bulk_insert_mappings") and any(is_model(arg) for arg in node.args))
                    or (called == "insert" and isinstance(func, ast.Attribute)
                        and any(is_model(inner) for inner in ast.walk(func.value)))):
                builders.add(".".join(scope) or "<module>")
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, ())
    return builders


def test_the_census_finds_each_way_to_build_a_filing_row(tmp_path):
    """The census's own reach, on planted source: each form it counts, and the other ``Filing`` classes it leaves."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from app.models import Filing, Company\n"
        "from app.models import Filing as Row\n"
        "from app import models\n"
        "import app.models as m\n"
        "from app.services.edgar.models import Filing as EdgarFiling\n"
        "from sqlalchemy import insert\n"
        "def built(): return Filing(accession_number='a')\n"
        "def aliased(): return Row(accession_number='a')\n"
        "def through_the_module(): return models.Filing(accession_number='a')\n"
        "def through_an_alias(): return m.Filing(accession_number='a')\n"
        "def core(db): db.execute(insert(Filing).values(accession_number='a'))\n"
        "def bulk(db): db.bulk_insert_mappings(Filing, [{}])\n"
        "def table(db): db.execute(Filing.__table__.insert())\n"
        "class Writer:\n"
        "    def write(self): return Filing()\n"
        "def edgar(): return EdgarFiling()\n"
        "def read(db): return db.query(Filing).filter(Filing.accession_number.in_(['a'])).all()\n"
        "def company(): return Company()\n",
        encoding="utf-8",
    )
    assert _filing_builders(planted) == {
        "built", "aliased", "through_the_module", "through_an_alias", "core", "bulk", "table", "Writer.write",
    }


def test_every_builder_of_a_filing_row_is_one_of_the_three_writers():
    """A function under ``app/`` that builds a filing row and is not one of the writers above inserts without the
    filing-insert lock (and without E123's company lock): read through ``existing_filings_for_insert`` after
    ``lock_company_filings``, then add it to ``WRITERS`` and ``WRITER_SITES`` with its cases here and in E123's gate."""
    found = {
        (str(path.relative_to(BACKEND)), function)
        for path in sorted((BACKEND / "app").rglob("*.py"))
        for function in _filing_builders(path)
    }
    assert found == WRITER_SITES, sorted(found ^ WRITER_SITES)

"""E151 on PostgreSQL: every session of the app's engine runs at UTC, whatever zone the server or the role would start it
in (``database._set_session_time_zone_utc``, a ``connect`` listener).

PostgreSQL binds a naive datetime, and renders each ``timestamptz`` it returns, in the session's ``TimeZone``. Under
America/Los_Angeles a filing stored at its true instant, the 15th at midnight UTC, read back as the 14th at 16:00 -08:00,
and its page showed the 14th. Each case's engine starts its sessions at America/Los_Angeles, as a server or role default
would (``-c TimeZone`` at connect), and the control case shows that start holds without the listener, so the other cases
are not passing on a server that already runs at UTC:

- a session reads UTC, and a stored instant comes back on its own day at +00:00, through production's sessions;
- the zone holds after a rollback and on each of the pool's connections, which a SET inside a transaction would not;
- the engine production's ``database.py`` builds pins it too, under ``PGTZ`` (libpq's default zone for a session).
  ``PGTZ`` is a client-side start that outranks even a startup ``options`` setting, so that case also holds that the
  pin is a statement run after the session starts, not a setting sent with the startup;
- that engine, under the relabel dry run's guards in ``PGOPTIONS``, keeps each of them beside the pin, its
  transactions read-only included: the pin sets nothing the Ops steps set.

SQLite has no session time zone, so the fast lane skips these cases; CI's "Verify the session time zone on PostgreSQL"
step runs them.
"""
import importlib
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app import database
from app.database import Base, SessionLocal
from app.models import Company, Filing

ELSEWHERE = "America/Los_Angeles"  # a zone eight hours from UTC in January, so a date shifts a day


def _url() -> str:
    url = os.environ.get("SESSION_TIME_ZONE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SESSION_TIME_ZONE_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "The session time zone gate requires PostgreSQL"
    return url


def _engine(url: str, schema: str, *, pinned: bool):
    """An engine whose sessions start at ``ELSEWHERE`` in ``schema``, with database.py's listener when ``pinned``."""
    engine = create_engine(
        url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000 -cTimeZone={ELSEWHERE}"},
    )
    if pinned:
        event.listen(engine, "connect", database._set_session_time_zone_utc)
    return engine


@pytest.fixture
def postgres_engine():
    url = _url()
    schema = f"session_time_zone_{uuid.uuid4().hex}"
    engine = _engine(url, schema, pinned=True)
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


def _session(bind):
    """A session with production's settings (``SessionLocal``'s) on this case's engine (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


def _zone(connection) -> str:
    return connection.execute(text("SHOW TimeZone")).scalar()


def test_without_the_listener_a_session_starts_elsewhere(postgres_engine):
    """The control: the start the other cases override holds on this server, so none of them passes vacuously."""
    control = _engine(_url(), f"session_time_zone_control_{uuid.uuid4().hex}", pinned=False)
    try:
        with control.connect() as connection:
            assert _zone(connection) == ELSEWHERE
    finally:
        control.dispose()


def test_a_session_runs_at_utc_and_a_stored_instant_reads_back_on_its_own_day(postgres_engine):
    filed = datetime(2026, 1, 15, tzinfo=timezone.utc)
    with _session(postgres_engine) as db:
        assert db.execute(text("SHOW TimeZone")).scalar() == "UTC"
        company = Company(cik="1", ticker="ZONE", name="Zone Corp")
        db.add(company)
        db.flush()
        db.add(Filing(
            company_id=company.id, accession_number="0000000001-26-000001", filing_type="10-K",
            filing_date=filed, period_end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
            sec_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/",
            document_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/a.htm",
        ))
        db.commit()
    with _session(postgres_engine) as db:
        stored = db.query(Filing.filing_date).scalar()
    assert stored == filed
    assert stored.utcoffset().total_seconds() == 0 and stored.date().isoformat() == "2026-01-15", stored.isoformat()


def test_the_zone_holds_after_a_rollback_and_on_each_pooled_connection(postgres_engine):
    """A SET made inside the transaction psycopg2 opens would be undone by a rollback, the pool's own when the connection
    comes back included; the listener's runs with autocommit on, so it holds for the connection's life. The case starts
    from connections opened afresh: the fixture's DDL committed on the pool's first one, and that commit would have kept
    a SET made inside its transaction."""
    postgres_engine.dispose()
    with postgres_engine.connect() as connection:
        assert _zone(connection) == "UTC"
        connection.rollback()
        assert _zone(connection) == "UTC"
    # The first back from the pool after its reset (a rollback), the second opened afresh and rolled back.
    with postgres_engine.connect() as first, postgres_engine.connect() as second:
        assert _zone(first) == "UTC"
        assert _zone(second) == "UTC"
        second.rollback()
        assert _zone(second) == "UTC"


def _fresh_database(monkeypatch):
    """Production's own engine, built by importing a fresh ``app.database`` with this gate's URL; the suite's module
    comes back when ``monkeypatch`` undoes."""
    from app import config

    monkeypatch.setattr(config.settings, "DATABASE_URL", _url())
    app_package = importlib.import_module("app")
    monkeypatch.setattr(app_package, "database", getattr(app_package, "database", None), raising=False)
    monkeypatch.delitem(sys.modules, "app.database", raising=False)
    return importlib.import_module("app.database")


def test_the_engine_database_py_builds_runs_its_sessions_at_utc(postgres_engine, monkeypatch):
    """Production's own engine, under ``PGTZ``, which libpq sends as a session's starting zone; a plain engine shows
    that start holds without the listener."""
    monkeypatch.setenv("PGTZ", ELSEWHERE)
    plain = create_engine(_url())
    try:
        with plain.connect() as connection:
            assert _zone(connection) == ELSEWHERE
    finally:
        plain.dispose()
    fresh = _fresh_database(monkeypatch)
    try:
        with fresh.engine.connect() as first, fresh.engine.connect() as second:  # each connection, not the first alone
            for connection in (first, second):
                assert _zone(connection) == "UTC"
                connection.rollback()
                assert _zone(connection) == "UTC"
    finally:
        fresh.engine.dispose()


# The relabel dry run's guards (.github/workflows/ops.yml), which reach its script's sessions only through PGOPTIONS.
OPS_GUARDS = "-c lock_timeout=10s -c statement_timeout=120s -c default_transaction_read_only=on"


def test_the_pin_keeps_the_guards_pgoptions_gives_a_session(postgres_engine, monkeypatch):
    """The Ops steps run production's engine with their guards in ``PGOPTIONS`` (``test_ops_workflow_wiring.py``): under
    the relabel dry run's, each session runs at UTC and keeps them, its transactions read-only. The environment is
    undone before the fixture drops its schema, so no connection it opens then is read-only."""
    with monkeypatch.context() as patch:
        patch.setenv("PGTZ", ELSEWHERE)
        patch.setenv("PGOPTIONS", OPS_GUARDS)
        fresh = _fresh_database(patch)
        try:
            with fresh.engine.connect() as first, fresh.engine.connect() as second:
                for connection in (first, second):
                    settings = connection.execute(text(
                        "SELECT current_setting('TimeZone'), current_setting('transaction_read_only'),"
                        " current_setting('lock_timeout'), current_setting('statement_timeout')"
                    )).one()
                    assert tuple(settings) == ("UTC", "on", "10s", "2min")
        finally:
            fresh.engine.dispose()

"""E151: database.py's PostgreSQL engine runs each new session at UTC (``_set_session_time_zone_utc``, a ``connect``
listener). The listener's SET runs with autocommit on, so no rollback undoes it, and hands the connection its own
autocommit back, after an error too; a connection that died before the SET keeps the server's error rather than raise
its own at the give-back. The SQLite engine takes no listener: SQLite has no session time zone, and the listener on it
would break every connection of this suite.

What PostgreSQL then reads is the PostgreSQL gate's (``tests/integration/test_session_time_zone.py``, run by CI's "Verify
the session time zone on PostgreSQL" step): this lane holds the wiring and the listener's mechanics.
"""
import importlib
import sys

import pytest
from sqlalchemy import event

from app import database


def _import_database(monkeypatch, url: str):
    """A fresh ``app.database`` built for ``url``; the suite's module comes back at teardown. Building an engine
    connects nowhere."""
    from app import config

    monkeypatch.setattr(config.settings, "DATABASE_URL", url)
    app_package = importlib.import_module("app")
    monkeypatch.setattr(app_package, "database", getattr(app_package, "database", None), raising=False)
    monkeypatch.delitem(sys.modules, "app.database", raising=False)
    return importlib.import_module("app.database")


def test_the_postgresql_engine_pins_each_session_to_utc(monkeypatch):
    fresh = _import_database(monkeypatch, "postgresql://app:not-a-secret@db.invalid:5432/app")
    try:
        assert fresh.engine.dialect.name == "postgresql"
        assert event.contains(fresh.engine, "connect", fresh._set_session_time_zone_utc)
    finally:
        fresh.engine.dispose()


class _ConnectionClosed(Exception):
    """psycopg2's InterfaceError for a connection already closed."""


class _Connection:
    """A DBAPI connection that records each statement with the autocommit it ran under, and can refuse it, or die
    before it (then, as psycopg2's does, it refuses to have its autocommit set)."""

    def __init__(self, autocommit: bool, refuse: bool = False, dies: bool = False):
        self._autocommit = autocommit
        self.refuse = refuse
        self.dies = dies
        self.closed = 0
        self.ran: list[tuple[str, bool]] = []

    @property
    def autocommit(self) -> bool:
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        if self.closed:
            raise _ConnectionClosed("connection already closed")
        self._autocommit = value

    def cursor(self):
        connection = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def execute(self, sql):
                connection.ran.append((sql, connection.autocommit))
                if connection.dies:
                    connection.closed = 1
                    raise RuntimeError("SSL connection has been closed unexpectedly")
                if connection.refuse:
                    raise RuntimeError("the server refused the SET")

        return _Cursor()


@pytest.mark.parametrize("autocommit", [False, True])
def test_the_listener_sets_utc_outside_a_transaction_and_gives_autocommit_back(autocommit):
    connection = _Connection(autocommit)
    database._set_session_time_zone_utc(connection, None)
    assert connection.ran == [("SET TIME ZONE 'UTC'", True)]
    assert connection.autocommit is autocommit


def test_the_listener_gives_autocommit_back_when_the_set_fails():
    connection = _Connection(False, refuse=True)
    with pytest.raises(RuntimeError, match="refused"):
        database._set_session_time_zone_utc(connection, None)
    assert connection.autocommit is False


def test_a_connection_that_died_before_the_set_keeps_the_servers_error():
    """Giving autocommit back to a closed psycopg2 connection raises "connection already closed", which would stand in
    for the error that closed it; the give-back is skipped there."""
    connection = _Connection(False, dies=True)
    with pytest.raises(RuntimeError, match="closed unexpectedly"):
        database._set_session_time_zone_utc(connection, None)

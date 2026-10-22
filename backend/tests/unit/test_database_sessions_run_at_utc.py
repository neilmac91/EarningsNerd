"""E151: database.py's PostgreSQL engine runs each new session at UTC (``_set_session_time_zone_utc``, a ``connect``
listener), and its SQLite engine carries no such listener, since SQLite has no session time zone. The listener's SET runs
with autocommit on, so no rollback undoes it, and hands the connection its own autocommit back, after an error too.

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


def test_the_sqlite_engine_has_no_session_time_zone_to_pin():
    assert database.engine.dialect.name == "sqlite"
    assert not event.contains(database.engine, "connect", database._set_session_time_zone_utc)


class _Connection:
    """A DBAPI connection that records each statement with the autocommit it ran under, and can refuse it."""

    def __init__(self, autocommit: bool, refuse: bool = False):
        self.autocommit = autocommit
        self.refuse = refuse
        self.ran: list[tuple[str, bool]] = []

    def cursor(self):
        connection = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def execute(self, sql):
                connection.ran.append((sql, connection.autocommit))
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

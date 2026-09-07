"""Startup self-heal for post-CREATE additive columns (database.ensure_additive_columns).

create_all() never ALTERs an existing table, so additive columns introduced after the original
CREATE (e.g. the FPI alert prefs notify_20f/notify_6k) are applied at startup. Idempotent and
non-fatal by construction.
"""
from sqlalchemy import create_engine, inspect, text

from app.database import _ADDITIVE_COLUMNS, ensure_additive_columns


def test_adds_missing_column_and_is_idempotent():
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))

    spec = [("t", "flag", "BOOLEAN NOT NULL DEFAULT TRUE")]
    ensure_additive_columns(bind=eng, specs=spec)
    assert "flag" in {col["name"] for col in inspect(eng).get_columns("t")}

    # Second run is a no-op (column already present) — must not raise.
    ensure_additive_columns(bind=eng, specs=spec)
    assert "flag" in {col["name"] for col in inspect(eng).get_columns("t")}


def test_missing_table_is_skipped_not_raised():
    eng = create_engine("sqlite://")
    # No such table — must be a quiet no-op, never raise (startup must not be blocked).
    ensure_additive_columns(bind=eng, specs=[("nope", "x", "BOOLEAN NOT NULL DEFAULT FALSE")])


def test_default_specs_target_fpi_pref_columns():
    cols = {(t, c) for t, c, _ in _ADDITIVE_COLUMNS}
    assert ("notification_preferences", "notify_20f") in cols
    assert ("notification_preferences", "notify_6k") in cols


def test_postgres_alter_waits_under_a_transaction_local_lock_timeout(monkeypatch):
    """E12b: on PostgreSQL every additive ALTER is preceded by SET LOCAL lock_timeout, so a
    rolling deploy's draining revision (share locks on the hot table) cannot hang the start;
    the ALTER fails inside the deadline and is logged, never raised."""
    from unittest.mock import MagicMock

    from app import database

    executed: list[str] = []
    conn = MagicMock()
    conn.dialect.name = "postgresql"
    conn.execute.side_effect = lambda clause: executed.append(str(clause))
    bind = MagicMock()
    bind.begin.return_value.__enter__.return_value = conn
    inspector = MagicMock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = []
    monkeypatch.setattr(database, "sa_inspect", lambda _bind: inspector)

    ensure_additive_columns(bind, specs=[("watchlist", "earnings_alert", "BOOLEAN NOT NULL DEFAULT FALSE")])
    assert executed == [
        f"SET LOCAL lock_timeout = '{database._ADDITIVE_LOCK_TIMEOUT_MS}ms'",
        "ALTER TABLE watchlist ADD COLUMN earnings_alert BOOLEAN NOT NULL DEFAULT FALSE",
    ]
    assert 0 < database._ADDITIVE_LOCK_TIMEOUT_MS <= 10_000


def test_sqlite_alter_has_no_lock_timeout_statement():
    # SQLite knows no lock_timeout; the ALTER runs bare (the existing behaviour, still idempotent).
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
    ensure_additive_columns(engine, specs=[("t", "flag", "BOOLEAN NOT NULL DEFAULT FALSE")])
    assert "flag" in {c["name"] for c in inspect(engine).get_columns("t")}

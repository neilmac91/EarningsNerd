"""Tests for the idempotent startup SQL-migration runner (app.db_migrations).

The runner executes Postgres-specific .sql; on SQLite (dev/tests) it must be a strict no-op so it
never breaks local startup or this suite. Postgres execution itself is exercised on deploy (the
files are all idempotent), not here.
"""
from pathlib import Path

from sqlalchemy import create_engine, text

from app.db_migrations import (
    _MIGRATIONS_DIR,
    _discover_migrations,
    apply_pending_migrations,
)


def test_sqlite_engine_is_a_noop():
    """On a non-Postgres engine the runner returns early and creates no ledger table."""
    engine = create_engine("sqlite://")
    apply_pending_migrations(engine)  # must not raise
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
        ).fetchall()
    assert rows == []  # ledger table was never created


def test_discover_migrations_sorted_and_real_files_present():
    """The real migrations dir is discovered, chronologically sorted, and includes the beta files."""
    files = _discover_migrations(_MIGRATIONS_DIR)
    assert files == sorted(files)  # date-prefixed names → chronological
    assert "20260624_add_is_beta_to_users.sql" in files
    assert "20260624_create_invite_codes.sql" in files
    assert all(f.endswith(".sql") for f in files)


def test_discover_migrations_missing_dir_returns_empty(tmp_path: Path):
    assert _discover_migrations(tmp_path / "does-not-exist") == []

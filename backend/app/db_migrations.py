"""Idempotent startup SQL-migration runner (Postgres only).

`Base.metadata.create_all()` creates MISSING TABLES from the ORM models but never ALTERs existing
ones, so a schema change to an existing table (e.g. adding a column) does not reach an existing
production database on deploy. This module applies the hand-written ``migrations/*.sql`` files at
startup so a deploy is self-sufficient — no manual `psql` step, no broken prod between deploy and
migration.

Scope — Postgres only. On SQLite (local/dev/tests) ``create_all()`` already builds the full schema
from the ORM models, and these ``.sql`` files use Postgres-specific DDL (``SERIAL`` / ``TIMESTAMPTZ``
/ ``NOW()``), so the runner deliberately no-ops there.

Safety — every migration in ``migrations/`` is idempotent (``IF [NOT] EXISTS`` /
``ON CONFLICT DO NOTHING``), so re-running an already-applied file is harmless. A ``schema_migrations``
ledger records what has run so files are not re-applied on every boot. On error the exception
propagates and startup fails fast — Cloud Run then keeps the previous (healthy) revision serving
rather than going live on a half-migrated schema.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# backend/app/db_migrations.py -> backend/migrations/
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _discover_migrations(migrations_dir: Path) -> list[str]:
    """Migration filenames in chronological order (names are date-prefixed ``YYYYMMDD_*``)."""
    if not migrations_dir.is_dir():
        return []
    return sorted(p.name for p in migrations_dir.glob("*.sql"))


def apply_pending_migrations(engine, migrations_dir: Optional[Path] = None) -> None:
    """Apply any ``migrations/*.sql`` not yet recorded in ``schema_migrations`` (Postgres only)."""
    if engine.dialect.name != "postgresql":
        # SQLite / others: create_all() is authoritative; the PG-specific .sql would not parse.
        return

    migrations_dir = migrations_dir or _MIGRATIONS_DIR
    files = _discover_migrations(migrations_dir)
    if not files:
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        applied = {row[0] for row in conn.exec_driver_sql("SELECT filename FROM schema_migrations")}

    pending = [f for f in files if f not in applied]
    if not pending:
        return

    for name in pending:
        sql = (migrations_dir / name).read_text()
        logger.info("Applying SQL migration: %s", name)
        # AUTOCOMMIT so each file's own BEGIN;/COMMIT; governs its atomicity; record it in the ledger
        # immediately after so a successful migration is never re-run.
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.exec_driver_sql(sql)
            conn.exec_driver_sql(
                "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT (filename) DO NOTHING",
                (name,),
            )

    logger.info("Applied %d pending SQL migration(s).", len(pending))

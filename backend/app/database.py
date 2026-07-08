import logging
import os

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# Connection pool configuration (configurable via environment variables)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
# Recycle connections after 1 hour to prevent stale connection errors
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
# Connection timeout in seconds (prevents hanging on network issues)
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

# SQLite requires check_same_thread=False for async operations
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_recycle=DB_POOL_RECYCLE,
        connect_args={"connect_timeout": DB_CONNECT_TIMEOUT},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns introduced after a table's original CREATE. `Base.metadata.create_all()` never ALTERs an
# existing table, and this project applies SQL migrations in migrations/ by hand — but the prod DB
# can't always be migrated manually in lockstep with a deploy, so these small ADDITIVE, defaulted
# columns are self-applied at startup to keep the deployed code and schema in sync (the FPI alert
# prefs from migrations/20260628_fpi_alert_prefs.sql would otherwise 500 the prefs API until the
# manual SQL ran). Additive + defaulted ONLY — never destructive; see ensure_additive_columns.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("notification_preferences", "notify_20f", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("notification_preferences", "notify_6k", "BOOLEAN NOT NULL DEFAULT FALSE"),
    # Per-company earnings-day alert opt-in (strategy §3.7). Prod has no Alembic, so an existing
    # watchlist table gets this column added at startup (create_all won't ALTER it).
    ("watchlist", "earnings_alert", "BOOLEAN NOT NULL DEFAULT FALSE"),
    # Deep filing-history backfill stamp (P1-6): an existing companies table self-heals this
    # column at startup so the on-visit backfill guard works before the migration runs.
    ("companies", "history_backfilled_at", "TIMESTAMPTZ"),
]


def ensure_additive_columns(bind=None, specs: list[tuple[str, str, str]] | None = None) -> None:
    """Idempotently add post-CREATE additive columns that ``create_all`` won't.

    For each ``(table, column, column_ddl)`` the column is added only when the table exists and the
    column is absent (inspector check), so this is a no-op once applied and on fresh DBs where
    ``create_all`` already created it. Failures are logged, never raised — a migration hiccup must
    not block app startup. Restricted to additive, defaulted columns by construction.
    """
    bind = bind if bind is not None else engine
    specs = specs if specs is not None else _ADDITIVE_COLUMNS
    try:
        inspector = sa_inspect(bind)
    except Exception as e:  # noqa: BLE001
        logger.warning("schema inspect failed; skipping additive migrations: %s", e)
        return
    for table, column, column_ddl in specs:
        try:
            if not inspector.has_table(table):
                continue
            if column in {c["name"] for c in inspector.get_columns(table)}:
                continue
            with bind.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_ddl}"))
            logger.info("ensure_additive_columns: added %s.%s", table, column)
        except Exception as e:  # noqa: BLE001 — never block startup on a single column
            logger.warning("ensure_additive_columns: could not add %s.%s: %s", table, column, e)


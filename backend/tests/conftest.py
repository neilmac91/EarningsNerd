"""
Pytest configuration for EarningsNerd backend tests.

Provides shared fixtures and markers for all test suites.
"""

import os
import shutil
import tempfile

# Every pytest process owns a private SQLite database in a fresh temp directory: one per session,
# and under pytest-xdist one per worker (each worker is its own process and imports this file).
# Set before any app import, so Settings reads it and app.database binds its engine to it. No test
# touches backend/earningsnerd.db (the dev server's default), two runs in one worktree never share
# a file, and every run starts from the current schema (create_all never ALTERs a stale file).
# Unconditional like the keys below: a developer's own DATABASE_URL must never reach the suite.
# Removed in pytest_unconfigure. Gate: tests/unit/test_test_database_isolation.py.
_TEST_DB_DIR = tempfile.mkdtemp(prefix=f"earningsnerd-tests-{os.environ.get('PYTEST_XDIST_WORKER', 'main')}-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_DB_DIR, "earningsnerd.db")

# Set mock environment variables for all tests at module level to avoid Pydantic validation errors at import time
os.environ["SECRET_KEY"] = "test-secret-key-must-be-long-enough-123"
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock_stripe_key_12345"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_mock_stripe_webhook_12345"

# Skip Redis initialization in tests - prevents 3+ second timeout per test
os.environ["SKIP_REDIS_INIT"] = "true"

# Disable the HaveIBeenPwned network call in tests so the suite stays hermetic and offline.
os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"

# NOTE: custom markers are registered in backend/pytest.ini (single source of test config).
# Shared fixtures are added below as the Wave 0 characterization anchors are written and a
# fixture is repeated across ≥2 of them.



import pytest  # noqa: E402
from sqlalchemy import Table, event  # noqa: E402


@event.listens_for(Table, "before_create")
def _sqlite_never_reuses_ids(table, connection, **kw):
    """Every SQLite table the suite creates gets AUTOINCREMENT ids, as PostgreSQL sequences behave.

    Without it SQLite hands out max(rowid)+1, so deleting a test's newest parent frees its id for the
    next test. SQLite here enforces no foreign keys, so a child row the first test left behind (a
    ``filing_content_cache`` row for its filing, say) then belongs to the next test's new filing and
    silently reroutes that test. Covers the shared engine and every engine a test creates; a no-op
    for composite and non-integer keys.
    """
    if connection.dialect.name == "sqlite":
        table.dialect_options["sqlite"]["autoincrement"] = True


def pytest_unconfigure(config):
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_delivery_ownership():
    """Durable delivery ownership rows (E11b-1) must not leak between tests.

    SQLite enforces no foreign keys here and reuses deleted integer ids, while several existing
    scenarios bulk-delete their users and filings in teardown; an orphaned
    ``earningsnerd_delivery_items`` row would then claim ownership of the next test's (reused)
    user/filing pair. PostgreSQL cascades these rows, so this is a test-isolation concern only.
    """
    from sqlalchemy import inspect, text

    from app.database import engine

    names = ("earningsnerd_delivery_items", "earningsnerd_delivery_batches", "earningsnerd_usage_reservations")
    present = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for name in names:  # admission leases (E07b) are keyed by reused user ids too
            if name in present:
                conn.execute(text(f"DELETE FROM {name}"))  # nosec B608 - fixed table names
    yield


@pytest.fixture(autouse=True)
def _isolate_ai_call_trigger():
    """The ``ai_call`` trigger label must not leak between tests.

    Script entrypoints (``python -m evals.runner``, the weekly readouts, the Cloud Run job scripts)
    set it for their whole process and never reset it, and some tests execute those entrypoints
    in-process. Without this, every later test's calls log as ``eval``/``job``, and tests that
    assert the default pass or fail by collection order. Each test starts from the default and
    nothing it sets survives; the probe pair in ``tests/unit/test_ai_metrics.py`` pins this.
    """
    from app.services import ai_metrics

    token = ai_metrics.set_trigger("user")
    yield
    ai_metrics.reset_trigger(token)

"""
Pytest configuration for EarningsNerd backend tests.

Provides shared fixtures and markers for all test suites.
"""

import os

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

    names = {"earningsnerd_delivery_items", "earningsnerd_delivery_batches"}
    if names.issubset(set(inspect(engine).get_table_names())):
        with engine.begin() as conn:
            for name in ("earningsnerd_delivery_items", "earningsnerd_delivery_batches"):
                conn.execute(text(f"DELETE FROM {name}"))  # nosec B608 - fixed table names
    yield

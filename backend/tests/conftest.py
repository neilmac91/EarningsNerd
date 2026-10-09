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

# A developer's backend/.env can carry live provider keys (telemetry, email, market data, bot checks);
# pinned empty here (env beats .env in Settings), Sentry's sender, PostHog, Resend, Alpha Vantage and
# Turnstile stay off in tests and never trip the network gate below or fail a request on a real key. A
# test that needs a key patches `settings`, as before. The list is kept by hand: pin a key here when a
# development .env value changes a test's outcome.
os.environ["SENTRY_DSN"] = ""
os.environ["POSTHOG_API_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["ALPHA_VANTAGE_API_KEY"] = ""
os.environ["TURNSTILE_SECRET_KEY"] = ""

# Outbound-network gate (rule 12): any attempt to reach a non-loopback host fails the test that
# made it, or the session when no running test owns it. Pinned by tests/unit/test_network_gate.py.
pytest_plugins = ("tests.support.network_gate",)

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


# Stream tests that drive the real ``stream_filing_summary`` with a mocked 10-K (CIK 1234567890)
# but patch only the document fetch and the AI call. The pipeline also starts its two
# edgartools-backed enrichment seams, and offline those reached data.sec.gov / www.sec.gov
# (submissions JSON, companyfacts fallback). These tests time heartbeats and fetch latency, not
# enrichment, so stub exactly those seams, as tests/support/summary_stream_harness.py does for the
# anchors. The list is explicit so no test that exercises enrichment is silently stubbed; the files
# themselves stay unedited.
_OFFLINE_ENRICHMENT_FILES = frozenset({
    "integration/test_summary_stream_heartbeat.py",
    "integration/test_stream_latency.py",
    "performance/test_concurrent_streams.py",
})


@pytest.fixture(autouse=True)
def _offline_stream_enrichment(request):
    if f"{request.path.parent.name}/{request.path.name}" not in _OFFLINE_ENRICHMENT_FILES:
        yield
        return
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, patch

    from app.services import summary_pipeline

    with ExitStack() as stack:
        for seam in ("get_xbrl_data", "get_filing_sections"):
            # patch.object (not monkeypatch) deletes the instance attribute on exit, so nothing
            # is left behind on the shared xbrl_service singleton.
            stack.enter_context(patch.object(summary_pipeline.xbrl_service, seam, AsyncMock(return_value=None)))
        yield

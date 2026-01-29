"""
Pytest configuration for EarningsNerd backend tests.

Provides shared fixtures and markers for all test suites.
"""

import os
import pytest

# Set mock environment variables for all tests at module level to avoid Pydantic validation errors at import time
os.environ["SECRET_KEY"] = "test-secret-key-must-be-long-enough-123"
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock_stripe_key_12345"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_mock_stripe_webhook_12345"

# Skip Redis initialization in tests - prevents 3+ second timeout per test
os.environ["SKIP_REDIS_INIT"] = "true"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "smoke: mark test as a smoke test (critical path validation)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring database (skips gracefully if not available)"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )


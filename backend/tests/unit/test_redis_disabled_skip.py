"""Redis L2 short-circuit when Redis is disabled (SKIP_REDIS_INIT=true).

In production the two-tier cache runs L1-only (Redis off). Before this guard, every cache op
still tried to build the default redis://localhost pool lazily and paid the 2s
CACHE_OPERATION_TIMEOUT before falling back — ~4s wasted per XBRL fetch (one get + one set).

conftest.py sets SKIP_REDIS_INIT=true, so these run under the disabled configuration.
"""
import time

import pytest

from app.config import settings
from app.services import redis_service


@pytest.mark.asyncio
async def test_pool_and_client_return_none_when_disabled():
    # Guard precondition: the suite runs with Redis disabled (conftest default).
    assert settings.SKIP_REDIS_INIT is True
    # Pre-fix these returned a real pool/client pointing at localhost; now they short-circuit.
    assert await redis_service.get_redis_pool() is None
    assert await redis_service.get_redis_client() is None


@pytest.mark.asyncio
async def test_cache_ops_are_fast_no_op_when_disabled():
    misses_before = redis_service._cache_stats.misses
    start = time.perf_counter()
    assert await redis_service.cache_get("any-key") is None
    assert await redis_service.cache_set("any-key", {"a": 1}) is False
    elapsed = time.perf_counter() - start
    # No per-op acquisition timeout: well under a single CACHE_OPERATION_TIMEOUT (2s).
    assert elapsed < 0.5, f"cache ops took {elapsed:.2f}s — expected instant when Redis disabled"
    # A disabled-Redis read must NOT register as a cache miss (would pollute the hit-rate metric).
    assert redis_service._cache_stats.misses == misses_before


@pytest.mark.asyncio
async def test_health_reports_disabled_not_unhealthy():
    health = await redis_service.check_redis_health()
    # Healthy-but-disabled so /health/detailed + /metrics don't flap to "degraded".
    assert health.get("healthy") is True
    assert health.get("disabled") is True

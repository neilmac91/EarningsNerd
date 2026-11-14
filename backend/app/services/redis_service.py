"""
Redis Service - Connection management and caching for EarningsNerd.

Provides:
- Connection pooling for Redis
- Health check functionality
- Graceful degradation when Redis is unavailable
- Thread-safe lazy initialization with asyncio.Lock
- Typed caching helpers with TTL configuration
- Cache metrics tracking
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, TypeVar
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from app.config import settings

# Connection pool configuration (configurable via environment variables)
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheTTL(int, Enum):
    """
    TTL configuration for different cache types.

    Values are in seconds. These are tuned for EarningsNerd's use cases:
    - XBRL data changes rarely, so long TTL (24h)
    - Filing metadata changes moderately, medium TTL (6h)
    - SEC's ticker map is semi-dynamic, shorter TTL (1h)
    """

    # Long-lived data (24 hours)
    XBRL_DATA = 86400

    # Medium-lived data (6 hours)
    FILING_METADATA = 21600

    # Short-lived data (1 hour)
    SEC_TICKERS = 3600


@dataclass
class CacheStats:
    """Statistics for cache monitoring."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    sets: int = 0
    deletes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert stats to dictionary for monitoring."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "sets": self.sets,
            "deletes": self.deletes,
            "hit_rate": round(self.hit_rate, 2),
        }


# Global cache statistics
_cache_stats = CacheStats()


def get_cache_stats() -> dict:
    """Get cache statistics for monitoring endpoints."""
    return _cache_stats.to_dict()


# Global connection pool (initialized lazily with lock protection)
# WHY track _init_lock_loop: asyncio objects (Lock, connections) are bound to the
# event loop they were created in. In production, there's typically one loop.
# In tests (especially with Starlette TestClient), each test module may create
# a new event loop. Using objects from a dead/different loop causes hangs or errors.
# By tracking which loop created our objects, we can detect loop changes and reset.
_pool: Optional[ConnectionPool] = None
_client: Optional[aioredis.Redis] = None
_init_lock: asyncio.Lock | None = None
_init_lock_loop: Optional[asyncio.AbstractEventLoop] = None


def _reset_on_loop_change() -> bool:
    """
    Detect event loop change and reset all Redis globals if needed.

    This handles the case where tests run in different event loops
    (e.g., Starlette TestClient creates a new loop per test module).
    Old pool/client objects bound to a dead loop would hang indefinitely.

    WHY this is needed: asyncio objects like Lock and Redis connections are
    bound to the event loop that created them. If the loop changes (common in
    tests), operations on these stale objects will hang forever waiting on a
    dead loop. By detecting loop changes and resetting state, we ensure
    connections are always bound to the current, running loop.

    Returns True if reset was performed, False otherwise.
    """
    global _pool, _client, _init_lock, _init_lock_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - nothing to check
        return False

    # If loop changed, reset everything to avoid using stale connections
    if _init_lock_loop is not None and _init_lock_loop is not current_loop:
        logger.debug("Event loop change detected, resetting Redis connections")
        _pool = None
        _client = None
        _init_lock = None
        _init_lock_loop = None
        return True

    return False


async def _get_init_lock() -> asyncio.Lock:
    """
    Get or create the initialization lock in async context (thread-safe).

    Handles event loop changes (e.g., during tests) by recreating the lock
    when the current event loop differs from the one the lock was created on.
    """
    global _init_lock, _init_lock_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - create lock without tracking
        if _init_lock is None:
            _init_lock = asyncio.Lock()
        return _init_lock

    # Check if lock exists and is bound to current loop
    if _init_lock is not None and _init_lock_loop is current_loop:
        return _init_lock

    # Create new lock for current loop (handles loop changes during tests)
    _init_lock = asyncio.Lock()
    _init_lock_loop = current_loop
    return _init_lock


async def get_redis_pool() -> Optional[ConnectionPool]:
    """
    Get or create the Redis connection pool.

    Thread-safe lazy initialization using asyncio.Lock to prevent
    race conditions when multiple coroutines attempt initialization.
    """
    global _pool

    # Redis intentionally disabled (prod runs the two-tier cache L1-only). Never attempt a
    # connection — otherwise the default redis://localhost pool is built lazily and every cache
    # op pays the full CACHE_OPERATION_TIMEOUT before falling back.
    if settings.SKIP_REDIS_INIT:
        return None

    # Reset if event loop changed (prevents hanging on stale connections)
    _reset_on_loop_change()

    if _pool is not None:
        return _pool

    async with await _get_init_lock():
        # Double-check after acquiring lock
        if _pool is not None:
            return _pool
        try:
            _pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            logger.info(f"Redis connection pool created (max_connections={REDIS_MAX_CONNECTIONS})")  # not the URL: it carries the password
        except RedisError as e:
            logger.warning(f"Failed to create Redis connection pool (Redis error): {e}")
            return None
        except ValueError as e:
            # The type only: a URL missing its `@host` puts the password where the port goes, and the port parse
            # quotes it.
            logger.warning(f"Failed to create Redis connection pool: REDIS_URL is malformed ({type(e).__name__})")
            return None
    return _pool


async def get_redis_client() -> Optional[aioredis.Redis]:
    """
    Get a Redis client from the connection pool.

    Thread-safe lazy initialization using asyncio.Lock.
    """
    global _client

    # Short-circuit when Redis is disabled so cache ops don't pay the acquisition timeout.
    if settings.SKIP_REDIS_INIT:
        return None

    # Reset if event loop changed (prevents hanging on stale connections)
    _reset_on_loop_change()

    if _client is not None:
        return _client

    # Resolve the pool before taking the init lock: get_redis_pool takes the same lock, and
    # asyncio.Lock is not reentrant.
    pool = await get_redis_pool()
    if pool is None:
        return None

    async with await _get_init_lock():
        # Double-check after acquiring lock
        if _client is not None:
            return _client
        _client = aioredis.Redis(connection_pool=pool)
    return _client


async def check_redis_health() -> dict:
    """
    Check Redis connectivity and return health status.

    Returns:
        dict with keys:
        - healthy: bool indicating if Redis is accessible
        - latency_ms: float ping latency in milliseconds (if healthy)
        - error: str error message (if unhealthy)
    """
    import time

    # Redis intentionally disabled — report healthy-but-disabled so /health/detailed and
    # /metrics don't flap to "degraded" for an expected configuration (both gate on "healthy").
    if settings.SKIP_REDIS_INIT:
        return {"healthy": True, "disabled": True, "latency_ms": 0.0}

    # Fast timeout to prevent hanging in CI/test environments without Redis
    HEALTH_CHECK_TIMEOUT = 2.0

    try:
        client = await asyncio.wait_for(get_redis_client(), timeout=HEALTH_CHECK_TIMEOUT)
        if client is None:
            return {
                "healthy": False,
                "error": "Redis client not initialized"
            }

        start = time.perf_counter()
        pong = await asyncio.wait_for(client.ping(), timeout=HEALTH_CHECK_TIMEOUT)
        latency_ms = (time.perf_counter() - start) * 1000

        if pong:
            return {
                "healthy": True,
                "latency_ms": round(latency_ms, 2)
            }
        else:
            return {
                "healthy": False,
                "error": "Redis ping returned False"
            }
    except asyncio.TimeoutError:
        logger.warning("Redis health check timed out")
        return {
            "healthy": False,
            "error": "Health check timed out (Redis may not be running)"
        }
    except RedisConnectionError as e:
        logger.warning(f"Redis connection error: {e}")
        return {
            "healthy": False,
            "error": f"Connection error: {str(e)}"
        }
    except aioredis.TimeoutError as e:
        logger.warning(f"Redis timeout: {e}")
        return {
            "healthy": False,
            "error": f"Timeout: {str(e)}"
        }
    except RedisError as e:
        logger.error(f"Redis health check failed (Redis error): {e}")
        return {
            "healthy": False,
            "error": f"Redis error: {str(e)}"
        }
    except OSError as e:
        # Handle connection refused, network unreachable, etc.
        logger.warning(f"Redis connection failed (OS error): {e}")
        return {
            "healthy": False,
            "error": f"Connection failed: {str(e)}"
        }


async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global _pool, _client, _init_lock, _init_lock_loop
    async with await _get_init_lock():
        if _client is not None:
            try:
                await _client.close()
            except RedisError as e:
                logger.warning(f"Error closing Redis client: {e}")
            _client = None
        if _pool is not None:
            try:
                await _pool.disconnect()
            except RedisError as e:
                logger.warning(f"Error disconnecting Redis pool: {e}")
            _pool = None
            logger.info("Redis connection pool closed")


# =============================================================================
# Cache Helper Functions
# =============================================================================


# Timeout for cache operations to prevent hanging in degraded scenarios
CACHE_OPERATION_TIMEOUT = 2.0


async def cache_get(key: str) -> Optional[Any]:
    """
    Get a value from cache.

    Returns None if key doesn't exist or Redis is unavailable.
    Automatically deserializes JSON values.
    Has a 2-second timeout to prevent hanging.
    """
    global _cache_stats

    # Redis disabled: skip without touching stats — counting these as misses would otherwise
    # pollute the hit-rate metric on every call.
    if settings.SKIP_REDIS_INIT:
        return None

    try:
        client = await asyncio.wait_for(
            get_redis_client(),
            timeout=CACHE_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Redis client acquisition timed out for cache_get({key})")
        _cache_stats.errors += 1
        return None

    if client is None:
        _cache_stats.misses += 1
        return None

    try:
        value = await asyncio.wait_for(
            client.get(key),
            timeout=CACHE_OPERATION_TIMEOUT
        )
        if value is None:
            _cache_stats.misses += 1
            return None

        _cache_stats.hits += 1

        # Try to deserialize JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    except asyncio.TimeoutError:
        logger.warning(f"Redis get timed out for key {key}")
        _cache_stats.errors += 1
        return None
    except RedisError as e:
        logger.warning(f"Redis get error for key {key}: {e}")
        _cache_stats.errors += 1
        return None


async def cache_set(
    key: str,
    value: Any,
    ttl: int = CacheTTL.FILING_METADATA,
) -> bool:
    """
    Set a value in cache with TTL.

    Automatically serializes non-string values to JSON.
    Returns True if successful, False otherwise.
    Has a 2-second timeout to prevent hanging.
    """
    global _cache_stats

    if settings.SKIP_REDIS_INIT:
        return False

    try:
        client = await asyncio.wait_for(
            get_redis_client(),
            timeout=CACHE_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Redis client acquisition timed out for cache_set({key})")
        _cache_stats.errors += 1
        return False

    if client is None:
        return False

    try:
        # Serialize non-string values to JSON
        if not isinstance(value, str):
            value = json.dumps(value)

        await asyncio.wait_for(
            client.setex(key, ttl, value),
            timeout=CACHE_OPERATION_TIMEOUT
        )
        _cache_stats.sets += 1
        return True

    except asyncio.TimeoutError:
        logger.warning(f"Redis set timed out for key {key}")
        _cache_stats.errors += 1
        return False
    except RedisError as e:
        logger.warning(f"Redis set error for key {key}: {e}")
        _cache_stats.errors += 1
        return False

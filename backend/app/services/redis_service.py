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
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TypeVar, Generic
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheTTL(int, Enum):
    """
    TTL configuration for different cache types.

    Values are in seconds. These are tuned for EarningsNerd's use cases:
    - XBRL data changes rarely, so long TTL (24h)
    - Filing metadata changes moderately, medium TTL (6h)
    - Company search is semi-dynamic, shorter TTL (1h)
    - Session data needs to be fresh, short TTL (30m)
    """

    # Long-lived data (24 hours)
    XBRL_DATA = 86400
    FILING_CONTENT = 86400
    MARKDOWN_CACHE = 86400

    # Medium-lived data (6 hours)
    FILING_METADATA = 21600
    COMPANY_INFO = 21600

    # Short-lived data (1 hour)
    COMPANY_SEARCH = 3600
    SEC_TICKERS = 3600

    # Very short-lived data (30 minutes)
    SESSION = 1800
    RATE_LIMIT = 1800

    # Ephemeral data (5 minutes)
    HOT_FILINGS = 300
    TRENDING = 300


class CacheNamespace(str, Enum):
    """
    Cache key namespaces to prevent collisions and enable bulk operations.
    """

    XBRL = "xbrl"
    FILING = "filing"
    COMPANY = "company"
    SEARCH = "search"
    SESSION = "session"
    RATE_LIMIT = "rl"
    METRICS = "metrics"


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


def reset_cache_stats() -> None:
    """Reset cache statistics (mainly for testing)."""
    global _cache_stats
    _cache_stats = CacheStats()


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
                max_connections=10,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            logger.info(f"Redis connection pool created for {settings.REDIS_URL}")
        except RedisError as e:
            logger.warning(f"Failed to create Redis connection pool (Redis error): {e}")
            return None
        except ValueError as e:
            logger.warning(f"Failed to create Redis connection pool (invalid URL): {e}")
            return None
    return _pool


async def get_redis_client() -> Optional[aioredis.Redis]:
    """
    Get a Redis client from the connection pool.

    Thread-safe lazy initialization using asyncio.Lock.
    """
    global _client

    # Reset if event loop changed (prevents hanging on stale connections)
    _reset_on_loop_change()

    if _client is not None:
        return _client

    async with await _get_init_lock():
        # Double-check after acquiring lock
        if _client is not None:
            return _client
        pool = await get_redis_pool()
        if pool is None:
            return None
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


def make_cache_key(namespace: CacheNamespace, *parts: str) -> str:
    """
    Build a cache key with namespace prefix.

    Example:
        make_cache_key(CacheNamespace.XBRL, "AAPL", "0000320193-24-000077")
        # Returns: "xbrl:AAPL:0000320193-24-000077"
    """
    return f"{namespace.value}:{':'.join(str(p) for p in parts)}"


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


async def cache_delete(key: str) -> bool:
    """
    Delete a key from cache.

    Returns True if key was deleted, False otherwise.
    Has a 2-second timeout to prevent hanging.
    """
    global _cache_stats

    try:
        client = await asyncio.wait_for(
            get_redis_client(),
            timeout=CACHE_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Redis client acquisition timed out for cache_delete({key})")
        _cache_stats.errors += 1
        return False

    if client is None:
        return False

    try:
        result = await client.delete(key)
        if result > 0:
            _cache_stats.deletes += 1
        return result > 0

    except RedisError as e:
        logger.warning(f"Redis delete error for key {key}: {e}")
        _cache_stats.errors += 1
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.

    Use with caution - this scans the keyspace.
    Returns number of keys deleted.

    Example:
        # Delete all XBRL cache entries
        await cache_delete_pattern("xbrl:*")
    """
    global _cache_stats

    client = await get_redis_client()
    if client is None:
        return 0

    try:
        deleted = 0
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1

        if deleted > 0:
            _cache_stats.deletes += deleted
            logger.info(f"Deleted {deleted} keys matching pattern {pattern}")

        return deleted

    except RedisError as e:
        logger.warning(f"Redis delete pattern error for {pattern}: {e}")
        _cache_stats.errors += 1
        return 0


async def cache_get_or_set(
    key: str,
    factory: callable,
    ttl: int = CacheTTL.FILING_METADATA,
) -> Optional[Any]:
    """
    Get a value from cache, or compute and cache it if missing.

    This is a convenience method for the common cache-aside pattern.

    Args:
        key: Cache key
        factory: Async function to compute the value if not cached
        ttl: Time to live in seconds

    Returns:
        Cached or computed value, or None if computation fails
    """
    # Try to get from cache first
    cached = await cache_get(key)
    if cached is not None:
        return cached

    # Compute the value
    try:
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        if value is not None:
            await cache_set(key, value, ttl)

        return value

    except Exception as e:
        logger.warning(f"Cache factory error for key {key}: {e}")
        return None


async def cache_exists(key: str) -> bool:
    """Check if a key exists in cache."""
    client = await get_redis_client()
    if client is None:
        return False

    try:
        return await client.exists(key) > 0
    except RedisError as e:
        logger.warning(f"Redis exists error for key {key}: {e}")
        return False


async def cache_ttl(key: str) -> Optional[int]:
    """
    Get remaining TTL for a key in seconds.

    Returns None if key doesn't exist or Redis is unavailable.
    Returns -1 if key has no TTL (persistent).
    Returns -2 if key doesn't exist.
    """
    client = await get_redis_client()
    if client is None:
        return None

    try:
        return await client.ttl(key)
    except RedisError as e:
        logger.warning(f"Redis TTL error for key {key}: {e}")
        return None

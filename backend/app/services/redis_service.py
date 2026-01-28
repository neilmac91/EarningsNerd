"""
Redis Service - Connection management and validation for EarningsNerd.

Provides:
- Connection pooling for Redis
- Health check functionality
- Graceful degradation when Redis is unavailable
- Thread-safe lazy initialization with asyncio.Lock
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from app.config import settings

logger = logging.getLogger(__name__)

# Global connection pool (initialized lazily with lock protection)
_pool: Optional[ConnectionPool] = None
_client: Optional[aioredis.Redis] = None
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    """Get or create the initialization lock (must be created in async context)."""
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def get_redis_pool() -> Optional[ConnectionPool]:
    """
    Get or create the Redis connection pool.

    Thread-safe lazy initialization using asyncio.Lock to prevent
    race conditions when multiple coroutines attempt initialization.
    """
    global _pool
    if _pool is not None:
        return _pool

    async with _get_init_lock():
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
    if _client is not None:
        return _client

    async with _get_init_lock():
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
    global _pool, _client, _init_lock
    async with _get_init_lock():
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

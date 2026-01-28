"""
Redis Service - Connection management and validation for EarningsNerd.

Provides:
- Connection pooling for Redis
- Health check functionality
- Graceful degradation when Redis is unavailable
"""

import logging
from typing import Optional
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from app.config import settings

logger = logging.getLogger(__name__)

# Global connection pool (initialized lazily)
_pool: Optional[ConnectionPool] = None
_client: Optional[redis.Redis] = None


async def get_redis_pool() -> Optional[ConnectionPool]:
    """Get or create the Redis connection pool."""
    global _pool
    if _pool is None:
        try:
            _pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=10,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            logger.info(f"Redis connection pool created for {settings.REDIS_URL}")
        except Exception as e:
            logger.warning(f"Failed to create Redis connection pool: {e}")
            return None
    return _pool


async def get_redis_client() -> Optional[redis.Redis]:
    """Get a Redis client from the connection pool."""
    global _client
    if _client is None:
        pool = await get_redis_pool()
        if pool is None:
            return None
        _client = redis.Redis(connection_pool=pool)
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

    try:
        client = await get_redis_client()
        if client is None:
            return {
                "healthy": False,
                "error": "Redis client not initialized"
            }

        start = time.perf_counter()
        pong = await client.ping()
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
    except redis.ConnectionError as e:
        logger.warning(f"Redis connection error: {e}")
        return {
            "healthy": False,
            "error": f"Connection error: {str(e)}"
        }
    except redis.TimeoutError as e:
        logger.warning(f"Redis timeout: {e}")
        return {
            "healthy": False,
            "error": f"Timeout: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }


async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global _pool, _client
    if _client is not None:
        await _client.close()
        _client = None
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("Redis connection pool closed")

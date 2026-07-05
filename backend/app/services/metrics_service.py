"""
Metrics Service for EarningsNerd.

Provides application metrics for monitoring dashboards.
Aggregates metrics from various services:
- Circuit breaker status
- Cache statistics
- Database connection pool stats
- Request counts and latencies

Usage:
    from app.services.metrics_service import get_all_metrics

    metrics = await get_all_metrics()
"""

import asyncio
import time
from typing import Dict, Any
import logging

from app.config import APP_VERSION

logger = logging.getLogger(__name__)



async def get_all_metrics() -> Dict[str, Any]:
    """
    Collect and return all application metrics.

    Returns a dictionary with metrics from all services:
    - app: Application-level metrics (uptime, version)
    - requests: HTTP request metrics
    - circuit_breaker: SEC EDGAR circuit breaker status
    - cache: Redis cache statistics
    - database: Database connection pool stats
    """
    import sys
    from datetime import datetime

    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "app": {
            "name": "EarningsNerd API",
            "version": APP_VERSION,
            "python_version": sys.version.split()[0],
            "environment": _get_environment(),
        },
    }

    # Circuit breaker metrics
    try:
        from app.services.edgar.circuit_breaker import edgar_circuit_breaker
        cb_status = edgar_circuit_breaker.get_status()
        metrics["circuit_breaker"] = {
            "sec_edgar": {
                "state": cb_status["state"],
                "stats": cb_status["stats"],
            }
        }
    except ImportError:
        metrics["circuit_breaker"] = {"error": "Not available"}

    # Cache metrics (L2 Redis + L1 in-memory)
    try:
        from app.services.redis_service import get_cache_stats, check_redis_health

        cache_stats = get_cache_stats()
        redis_health = await check_redis_health()

        metrics["cache"] = {
            "redis": {
                "healthy": redis_health.get("healthy", False),
                "latency_ms": redis_health.get("latency_ms"),
                **cache_stats,
            }
        }

        # Add L1 (in-memory) XBRL cache stats
        try:
            from app.services.edgar.xbrl_service import get_xbrl_cache_stats
            xbrl_stats = get_xbrl_cache_stats()
            l1_stats_map = {
                "total_entries": ("l1_total_entries", 0),
                "valid_entries": ("l1_valid_entries", 0),
                "expired_entries": ("l1_expired_entries", 0),
                "max_size": ("l1_max_size", 1000),
                "utilization_percent": ("l1_utilization_percent", 0),
                "ttl_hours": ("cache_ttl_hours", 24),
                "hits": ("l1_hits", 0),
                "misses": ("l1_misses", 0),
                "hit_rate": ("l1_hit_rate", 0),
                "evictions": ("l1_evictions", 0),
            }
            metrics["cache"]["xbrl_l1"] = {
                dest_key: xbrl_stats.get(src_key, default)
                for dest_key, (src_key, default) in l1_stats_map.items()
            }
        except ImportError:
            pass

    except ImportError:
        metrics["cache"] = {"error": "Not available"}

    # Database metrics
    try:
        from app.database import engine
        pool = engine.pool

        metrics["database"] = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as e:
        metrics["database"] = {"error": str(e)}

    # Thread pool metrics (EdgarTools executor)
    try:
        from app.services.edgar.async_executor import get_executor_stats
        executor_stats = get_executor_stats()
        metrics["thread_pool"] = {
            "edgar": {
                "max_workers": executor_stats.get("max_workers", 0),
                "threads_created": executor_stats.get("threads_created", 0),
            }
        }
    except ImportError:
        metrics["thread_pool"] = {"error": "Not available"}

    return metrics


def _get_environment() -> str:
    """Get the current environment name."""
    import os
    return os.environ.get("ENVIRONMENT", "development")


async def get_health_summary() -> Dict[str, Any]:
    """
    Get a summary health status for monitoring dashboards.

    Returns overall status and component health.
    """
    status = "healthy"
    components = {}

    # Check circuit breaker
    try:
        from app.services.edgar.circuit_breaker import edgar_circuit_breaker
        cb_state = edgar_circuit_breaker.state.value
        components["sec_edgar_circuit"] = {
            "healthy": cb_state != "open",
            "state": cb_state,
        }
        if cb_state == "open":
            status = "degraded"
    except ImportError:
        pass

    # Check Redis
    try:
        from app.services.redis_service import check_redis_health
        redis_health = await check_redis_health()
        components["redis"] = redis_health
        if not redis_health.get("healthy"):
            if status == "healthy":
                status = "degraded"
    except ImportError:
        pass

    # Check database (using async to avoid blocking event loop)
    try:
        from sqlalchemy import text
        from app.database import engine

        start = time.perf_counter()

        # Run sync DB check in thread pool to avoid blocking event loop
        def _sync_db_check():
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True

        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _sync_db_check),
            timeout=2.0
        )
        latency_ms = (time.perf_counter() - start) * 1000
        components["database"] = {
            "healthy": True,
            "latency_ms": round(latency_ms, 2),
        }
    except asyncio.TimeoutError:
        components["database"] = {
            "healthy": False,
            "error": "Database health check timed out",
        }
        status = "unhealthy"
    except Exception as e:
        components["database"] = {
            "healthy": False,
            "error": str(e),
        }
        status = "unhealthy"

    return {
        "status": status,
        "components": components,
    }

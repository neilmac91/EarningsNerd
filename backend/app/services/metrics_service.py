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

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for HTTP request tracking."""

    total_requests: int = 0
    successful_requests: int = 0  # 2xx responses
    client_errors: int = 0  # 4xx responses
    server_errors: int = 0  # 5xx responses
    total_latency_ms: float = 0.0

    # Per-endpoint tracking (top endpoints)
    endpoint_counts: Dict[str, int] = field(default_factory=dict)

    # Recent request timestamps for rate calculation
    _recent_timestamps: list = field(default_factory=list)

    @property
    def average_latency_ms(self) -> float:
        """Calculate average request latency."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def error_rate(self) -> float:
        """Calculate error rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        errors = self.client_errors + self.server_errors
        return errors / self.total_requests * 100

    @property
    def requests_per_minute(self) -> float:
        """Calculate recent requests per minute."""
        now = time.time()
        cutoff = now - 60  # Last minute

        # Clean old timestamps
        self._recent_timestamps = [
            ts for ts in self._recent_timestamps if ts > cutoff
        ]

        return len(self._recent_timestamps)

    def record_request(
        self,
        endpoint: str,
        status_code: int,
        latency_ms: float,
    ) -> None:
        """Record a completed request."""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        self._recent_timestamps.append(time.time())

        # Categorize by status code
        if 200 <= status_code < 300:
            self.successful_requests += 1
        elif 400 <= status_code < 500:
            self.client_errors += 1
        elif status_code >= 500:
            self.server_errors += 1

        # Track top endpoints
        if endpoint not in self.endpoint_counts:
            self.endpoint_counts[endpoint] = 0
        self.endpoint_counts[endpoint] += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        # Get top 10 endpoints by request count
        top_endpoints = sorted(
            self.endpoint_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "client_errors": self.client_errors,
            "server_errors": self.server_errors,
            "average_latency_ms": round(self.average_latency_ms, 2),
            "error_rate_percent": round(self.error_rate, 2),
            "requests_per_minute": self.requests_per_minute,
            "top_endpoints": dict(top_endpoints),
        }


# Global request metrics instance
_request_metrics = RequestMetrics()


def get_request_metrics() -> RequestMetrics:
    """Get the global request metrics instance."""
    return _request_metrics


def record_request(
    endpoint: str,
    status_code: int,
    latency_ms: float,
) -> None:
    """Record a completed request in global metrics."""
    _request_metrics.record_request(endpoint, status_code, latency_ms)


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
            "version": "1.0.0",
            "python_version": sys.version.split()[0],
            "environment": _get_environment(),
        },
        "requests": _request_metrics.to_dict(),
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

    # Cache metrics
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

    # Check database
    try:
        from sqlalchemy import text
        from app.database import SessionLocal
        import time

        start = time.perf_counter()
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            latency_ms = (time.perf_counter() - start) * 1000
            components["database"] = {
                "healthy": True,
                "latency_ms": round(latency_ms, 2),
            }
        finally:
            db.close()
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

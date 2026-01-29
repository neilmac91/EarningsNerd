"""
Structured Logging Service for EarningsNerd.

Provides:
- JSON structured logging for production environments
- Correlation ID generation and propagation across requests
- Request context middleware for FastAPI
- Consistent logging helpers

Usage:
    # In a router
    from app.services.logging_service import get_logger, get_correlation_id

    logger = get_logger(__name__)
    logger.info("Processing request", extra={"ticker": "AAPL", "filing_type": "10-K"})

    # Access correlation ID
    correlation_id = get_correlation_id()
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for correlation ID (thread-safe per-request)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Context variable for request metadata
_request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID for the request."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current request context."""
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID (UUID4 truncated to 12 chars for readability)."""
    return uuid.uuid4().hex[:12]


def get_request_context() -> Dict[str, Any]:
    """Get the current request context metadata."""
    return _request_context.get()


def set_request_context(context: Dict[str, Any]) -> None:
    """Set request context metadata."""
    _request_context.set(context)


class StructuredLogFormatter(logging.Formatter):
    """
    JSON structured log formatter for production environments.

    Outputs logs in JSON format with consistent fields:
    - timestamp: ISO 8601 format
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - correlation_id: Request correlation ID (if available)
    - Additional fields from extra dict
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        # Add request context if available
        request_context = get_request_context()
        if request_context:
            log_data.update(request_context)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class SimpleLogFormatter(logging.Formatter):
    """
    Human-readable formatter for development environments.

    Format: [timestamp] LEVEL [correlation_id] logger - message {extra}
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        correlation_id = get_correlation_id() or "no-id"

        # Collect extra fields
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message",
        }
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }

        msg = f"[{timestamp}] {record.levelname:8} [{correlation_id}] {record.name} - {record.getMessage()}"

        if extra:
            msg += f" {extra}"

        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON structured format (for production)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter based on environment
    if json_format:
        formatter = StructuredLogFormatter()
    else:
        formatter = SimpleLogFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    This is a convenience wrapper around logging.getLogger that ensures
    consistent logger configuration.
    """
    return logging.getLogger(name)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and propagate correlation IDs.

    The correlation ID is:
    1. Extracted from the X-Correlation-ID header if present
    2. Generated if not present
    3. Added to the response headers
    4. Made available via get_correlation_id()
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            self.CORRELATION_ID_HEADER,
            generate_correlation_id()
        )

        # Set in context
        set_correlation_id(correlation_id)

        # Set request context for logging
        set_request_context({
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        })

        # Process request
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            # Log request completion
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Only log API requests (not health checks, etc.)
            if request.url.path.startswith("/api/"):
                logger = get_logger("api.request")
                logger.info(
                    f"{request.method} {request.url.path}",
                    extra={
                        "duration_ms": round(duration_ms, 2),
                        "status_code": response.status_code if response else None,
                    }
                )

            # Clear context
            set_correlation_id(None)
            set_request_context({})

        # Add correlation ID to response headers
        response.headers[self.CORRELATION_ID_HEADER] = correlation_id

        return response


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra,
) -> None:
    """
    Log a message with additional context.

    This is a convenience function that automatically includes
    the correlation ID and any extra fields.
    """
    logger.log(level, message, extra=extra)


# Convenience functions for common log patterns
def log_api_call(
    logger: logging.Logger,
    service: str,
    operation: str,
    duration_ms: float,
    success: bool,
    **extra,
) -> None:
    """Log an external API call with standard fields."""
    logger.info(
        f"External API call: {service}.{operation}",
        extra={
            "service": service,
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            **extra,
        }
    )


def log_cache_operation(
    logger: logging.Logger,
    operation: str,
    key: str,
    hit: Optional[bool] = None,
    **extra,
) -> None:
    """Log a cache operation with standard fields."""
    logger.debug(
        f"Cache {operation}: {key}",
        extra={
            "cache_operation": operation,
            "cache_key": key,
            "cache_hit": hit,
            **extra,
        }
    )

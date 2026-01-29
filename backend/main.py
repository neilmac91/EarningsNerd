from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import asyncio
import os
import time
from dotenv import load_dotenv

# Load environment variables early for Sentry initialization
load_dotenv()

# Initialize Sentry for error tracking (must be done before FastAPI app creation)
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_dsn = os.getenv("SENTRY_DSN", "")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% of sampled transactions for profiling
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            # Don't send PII
            send_default_pii=False,
        )
        print("✓ Sentry error tracking initialized")
    else:
        print("⚠️  SENTRY_DSN not configured - error tracking disabled")
except ImportError:
    print("Sentry SDK not available - install sentry-sdk for error tracking")

from app.database import engine, Base
from app.services.logging_service import (
    configure_logging,
    CorrelationIdMiddleware,
    get_logger,
)

# Initialize logger for startup messages
logger = get_logger(__name__)
from app.routers import (
    companies,
    filings,
    summaries,
    auth,
    users,
    subscriptions,
    saved_summaries,
    watchlist,
    sitemap,
    compare,
    hot_filings,
    trending,
    email,
    contact,
    webhooks,
    admin,
)
from app.config import settings

# Create database tables
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - run sync DB operation in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: Base.metadata.create_all(bind=engine))

    # Validate database connection at startup
    from sqlalchemy import text

    def _validate_db_connection():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True

    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _validate_db_connection),
            timeout=5.0
        )
        logger.info("Database connection validated successfully")
    except asyncio.TimeoutError:
        logger.critical("Database connection validation timed out")
        raise RuntimeError("Cannot start application: database connection timed out")
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        raise RuntimeError(f"Cannot start application: database unreachable - {e}")

    # Validate Google AI Studio configuration
    is_valid, warnings = settings.validate_openai_config()

    if warnings:
        logger.warning("Google AI Studio Configuration Warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    if is_valid:
        logger.info(f"Google AI Studio configured: base_url={settings.OPENAI_BASE_URL}, model={settings.AI_DEFAULT_MODEL}")
    else:
        logger.error("Google AI Studio configuration is invalid. AI summaries may not work.")

    # Validate Stripe configuration
    stripe_valid, stripe_warnings = settings.validate_stripe_config()
    if stripe_warnings:
        logger.warning("Stripe Configuration Warnings:")
        for warning in stripe_warnings:
            logger.warning(f"  - {warning}")
    if stripe_valid:
        logger.info("Stripe configured: API key present")
        if settings.STRIPE_WEBHOOK_SECRET:
            logger.info("Stripe webhook secret configured: subscription events will be processed")
        else:
            logger.warning("Stripe webhook secret not configured: subscription events will fail")
    else:
        logger.error("Stripe configuration is invalid. Subscription features will be disabled.")

    # Initialize Redis connection pool (with timeout to prevent hanging in CI/test)
    from app.services.redis_service import get_redis_pool, check_redis_health, close_redis

    if not settings.SKIP_REDIS_INIT:
        REDIS_INIT_TIMEOUT = 3.0  # Fast fail for CI environments
        try:
            await asyncio.wait_for(get_redis_pool(), timeout=REDIS_INIT_TIMEOUT)
            redis_health = await check_redis_health()
            if redis_health.get("healthy"):
                logger.info(f"Redis connected: latency={redis_health.get('latency_ms', 'N/A')}ms")
            else:
                logger.warning(f"Redis not available: {redis_health.get('error', 'unknown error')} (caching degraded)")
        except asyncio.TimeoutError:
            logger.warning("Redis initialization timed out (caching degraded)")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e} (caching degraded)")
    else:
        logger.info("Redis initialization skipped (SKIP_REDIS_INIT=true)")

    yield

    # Shutdown
    await close_redis()
    logger.info("Redis connections closed")

    # Shutdown EdgarTools thread pool
    from app.services.edgar.async_executor import shutdown_executor
    shutdown_executor(wait=True)
    logger.info("EdgarTools thread pool shut down")

app = FastAPI(
    title="EarningsNerd API",
    description="AI-powered SEC filing analysis and summarization",
    version="1.0.0",
    lifespan=lifespan
)

# Configure structured logging
configure_logging(
    level="DEBUG" if settings.ENVIRONMENT == "development" else "INFO",
    json_format=settings.ENVIRONMENT == "production",
)

# Correlation ID middleware (adds X-Correlation-ID to all requests)
app.add_middleware(CorrelationIdMiddleware)

# CORS middleware
# More restrictive in production, flexible in development
_cors_config = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    # Explicit methods instead of wildcard for security
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    # Explicit headers for security - include common auth and content headers
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Correlation-ID",
    ],
    "expose_headers": ["X-Correlation-ID"],
}

# Only allow localhost regex in development (for various dev server ports)
if settings.ENVIRONMENT != "production":
    _cors_config["allow_origin_regex"] = r"http://localhost:\d+"

app.add_middleware(CORSMiddleware, **_cors_config)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if settings.ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
    return response


# Request timeout middleware
# Configurable timeouts per endpoint pattern
REQUEST_TIMEOUT_SECONDS = {
    "default": 30.0,
    "/api/summaries/": 120.0,  # Summary generation needs more time
    "/api/filings/": 60.0,     # Filing fetches from SEC EDGAR
    "/health": 5.0,            # Health checks should be fast
}


def get_timeout_for_path(path: str) -> float:
    """Get the appropriate timeout for a request path."""
    for pattern, timeout in REQUEST_TIMEOUT_SECONDS.items():
        if pattern != "default" and path.startswith(pattern):
            return timeout
    return REQUEST_TIMEOUT_SECONDS["default"]


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    """
    Apply request-level timeouts to prevent hung connections.

    Excludes streaming endpoints (SSE) which manage their own timeouts.
    """
    path = request.url.path

    # Skip timeout for streaming endpoints (they have their own timeout handling)
    if "stream" in path.lower() or path.endswith("/progress"):
        return await call_next(request)

    timeout = get_timeout_for_path(path)

    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Request timed out after {timeout}s",
                "path": path,
                "timeout_seconds": timeout
            }
        )

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(filings.router, prefix="/api/filings", tags=["Filings"])
app.include_router(summaries.router, prefix="/api/summaries", tags=["Summaries"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(saved_summaries.router, prefix="/api/saved-summaries", tags=["Saved Summaries"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(watchlist.waitlist_router, prefix="/api/waitlist", tags=["Waitlist"])
app.include_router(sitemap.router, tags=["SEO"])
app.include_router(compare.router, prefix="/api/compare", tags=["Compare"])
app.include_router(hot_filings.router, prefix="/api", tags=["Hot Filings"])
app.include_router(trending.router, prefix="/api", tags=["Trending"])
app.include_router(email.router, prefix="/api/email", tags=["Email"])
app.include_router(contact.router, prefix="/api/contact", tags=["Contact"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler for unhandled errors.
    Provides consistent error response format and logs the error.
    """
    from fastapi.responses import JSONResponse

    # Log the error with full context
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}"
    )

    # Report to Sentry if available
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except ImportError:
        pass

    # Return a generic error response (don't leak internal details in production)
    error_detail = str(exc) if settings.ENVIRONMENT != "production" else "An unexpected error occurred"

    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail,
            "type": "internal_server_error",
        }
    )


@app.get("/")
async def root():
    return {
        "message": "EarningsNerd API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Basic health check for load balancer."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_check_detailed():
    """
    Detailed health check with dependency verification.

    Checks:
    - Database connectivity
    - Redis connectivity (if configured)

    Returns degraded status if any non-critical dependency is unhealthy.
    Returns unhealthy status if critical dependencies (database) are down.
    """
    import time
    from sqlalchemy import text
    from app.database import SessionLocal
    from app.services.redis_service import check_redis_health

    health_status = {
        "status": "healthy",
        "checks": {},
        "timestamp": time.time()
    }

    # Check database connectivity
    try:
        start = time.perf_counter()
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            latency_ms = (time.perf_counter() - start) * 1000
            health_status["checks"]["database"] = {
                "healthy": True,
                "latency_ms": round(latency_ms, 2)
            }
        finally:
            db.close()
    except Exception as e:
        health_status["checks"]["database"] = {
            "healthy": False,
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check Redis connectivity
    redis_health = await check_redis_health()
    health_status["checks"]["redis"] = redis_health

    # Redis is non-critical - degrade but don't fail
    if not redis_health.get("healthy"):
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # Check circuit breaker status
    from app.services.edgar.circuit_breaker import edgar_circuit_breaker
    cb_status = edgar_circuit_breaker.get_status()
    health_status["checks"]["sec_edgar_circuit"] = {
        "state": cb_status["state"],
        "healthy": cb_status["state"] != "open",
        "stats": {
            "total_requests": cb_status["stats"]["total_requests"],
            "success_rate": round(cb_status["stats"]["success_rate"], 1),
            "rejected_requests": cb_status["stats"]["rejected_requests"],
        }
    }

    # Circuit breaker open is degraded (not unhealthy - we have fallbacks)
    if cb_status["state"] == "open":
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # Return appropriate HTTP status
    from fastapi.responses import JSONResponse
    if health_status["status"] == "unhealthy":
        return JSONResponse(status_code=503, content=health_status)
    elif health_status["status"] == "degraded":
        return JSONResponse(status_code=200, content=health_status)

    return health_status


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve robots.txt to prevent search engine indexing of API endpoints."""
    from fastapi.responses import PlainTextResponse
    content = """# EarningsNerd API - robots.txt
# This is an API server, not intended for search engine indexing.
# The main website is at https://earningsnerd.io

User-agent: *
Disallow: /api/
Allow: /

# Sitemap for the frontend
Sitemap: https://earningsnerd.io/sitemap.xml
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Get application metrics for monitoring dashboards.

    Returns comprehensive metrics including:
    - Application info
    - HTTP request statistics
    - Circuit breaker status
    - Cache statistics
    - Database pool stats
    """
    from app.services.metrics_service import get_all_metrics
    return await get_all_metrics()

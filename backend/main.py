from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
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
    # Startup
    Base.metadata.create_all(bind=engine)
    
    # Validate Google AI Studio configuration
    is_valid, warnings = settings.validate_openai_config()
    
    if warnings:
        print("⚠️  Google AI Studio Configuration Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    if is_valid:
        print(f"✓ Google AI Studio configured: base_url={settings.OPENAI_BASE_URL}, model=gemini-2.0-flash")
    else:
        print("✗ Google AI Studio configuration is invalid. AI summaries may not work.")
    
    # Validate Stripe configuration
    stripe_valid, stripe_warnings = settings.validate_stripe_config()
    if stripe_warnings:
        print("⚠️  Stripe Configuration Warnings:")
        for warning in stripe_warnings:
            print(f"   - {warning}")
    if stripe_valid:
        print("✓ Stripe configured: API key present")
        if settings.STRIPE_WEBHOOK_SECRET:
            print("✓ Stripe webhook secret configured: subscription events will be processed")
        else:
            print("⚠️  Stripe webhook secret not configured: subscription events will fail")
    else:
        print("✗ Stripe configuration is invalid. Subscription features will be disabled.")
    
    yield
    # Shutdown
    pass

app = FastAPI(
    title="EarningsNerd API",
    description="AI-powered SEC filing analysis and summarization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.middleware("http")
async def log_request_latency(request: Request, call_next):
    start_time = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if request.url.path.startswith("/api/"):
            print(f"[API] {request.method} {request.url.path} {duration_ms:.1f} ms")


@app.get("/")
async def root():
    return {
        "message": "EarningsNerd API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


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

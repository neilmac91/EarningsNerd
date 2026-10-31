"""Private task-only ASGI app; no API timeout middleware, schema startup or parent DB pool."""
import logging

from fastapi import FastAPI

from app.config import settings
from app.routers.tasks import router
from app.services.logging_service import configure_logging
from app.utils.telemetry_bootstrap import init_sentry

configure_logging(level="INFO", json_format=settings.ENVIRONMENT == "production")
# Sentry starts before the app is built, with the task policy (app/utils/telemetry_bootstrap.py). Its status, from
# a closed set and never an init error's text, is logged, not printed: the ops logs-probe counts the API's lines.
_sentry = init_sentry("worker")
logging.getLogger(__name__).info("Sentry error tracking: %s", _sentry.status)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router, prefix="/internal")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

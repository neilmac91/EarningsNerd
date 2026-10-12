"""Private task-only ASGI app; no API timeout middleware, schema startup or parent DB pool."""
from fastapi import FastAPI

from app.config import settings
from app.routers.tasks import router
from app.services.logging_service import configure_logging

configure_logging(level="INFO", json_format=settings.ENVIRONMENT == "production")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router, prefix="/internal")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

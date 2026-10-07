"""Private task-only ASGI app; no API timeout middleware, schema startup or parent DB pool."""
from fastapi import FastAPI

from app.routers.tasks import router

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router, prefix="/internal")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

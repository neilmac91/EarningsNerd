"""Publish the API host's security-disclosure contact through the canonical website."""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt() -> RedirectResponse:
    return RedirectResponse(
        "https://www.earningsnerd.io/.well-known/security.txt",
        status_code=307,
        headers={"Cache-Control": "public, max-age=3600"},
    )

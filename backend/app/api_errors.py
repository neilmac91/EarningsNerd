"""The HTTP half of the error codes (E31; ``app/error_codes.py`` holds the vocabulary).

A router or a dependency raises ``CodedHTTPException`` where it raised an ``HTTPException``: same detail, same
headers, the status ``REGISTERED_STATUS`` gives its code, so the code and the status cannot disagree. ``main.py``
registers ``coded_http_exception_handler``, which answers ``{"detail": ..., "code": ...}``. Until it does, FastAPI's
own ``HTTPException`` handler answers a ``CodedHTTPException`` with its status, detail and headers and no code, so a
producer can land before the registration without changing any answer.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.error_codes import REGISTERED_STATUS, ErrorCode


class CodedHTTPException(HTTPException):
    """An ``HTTPException`` at ``code``'s registered status, answered as ``{"detail": detail, "code": code}``."""

    def __init__(self, code: ErrorCode, detail: str, headers: Optional[dict[str, str]] = None) -> None:
        code = ErrorCode(code)  # a plain string would pass the lookup and fail the handler's `.value`
        super().__init__(status_code=REGISTERED_STATUS[code], detail=detail, headers=headers)
        self.code = code


async def coded_http_exception_handler(request: Request, exc: CodedHTTPException) -> JSONResponse:
    """``main.py``'s handler for ``CodedHTTPException``: FastAPI's own answer to an ``HTTPException``, plus ``code``."""
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code.value}, headers=exc.headers
    )

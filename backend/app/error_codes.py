"""Machine-readable error codes beside the words a refusal already sends (E31; docs/audit/contracts/error-codes.md).

A refusal the browser acts on (log in, verify the email, upgrade, wait for the month's allowance) carried only its
sentence, so the frontend chose its card, its retry and its navigation by matching words, and a copy edit could
change what a button does (``frontend/tests/unit/backendMessageMatches.spec.ts`` holds both sides together until
the codes replace it). A producer now sends a ``code`` from ``ErrorCode`` beside its unchanged words: a router or a
dependency raises ``app.api_errors.CodedHTTPException``, and a stream yields ``sse_error(...)``.

This module imports no HTTP framework, so a service (a summary stage) may import it
(``tests/unit/test_services_http_free_allowlist.py``). A code is honoured only on its registered channel: its HTTP
status (``REGISTERED_STATUS``), or a stream's error event for the codes in ``STREAM_CODES``. The client checks the
same table (``frontend/lib/api/client.ts::parseErrorCode``), and ``tests/unit/test_api_error_codes.py`` holds the
two and the contract's table equal.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class ErrorCode(StrEnum):
    """Every code a producer may send. A code keeps one meaning forever; a retired one is never reused."""

    AUTH_REQUIRED = "auth_required"
    EMAIL_VERIFICATION_REQUIRED = "email_verification_required"
    PLAN_REQUIRED = "plan_required"
    FREE_ALLOWANCE_EXHAUSTED = "free_allowance_exhausted"
    PRO_FAIR_USE_LIMIT = "pro_fair_use_limit"
    GENERATION_PAUSED = "generation_paused"
    EARNINGS_ALERT_LIMIT = "earnings_alert_limit"


# The HTTP status each code is sent with.
REGISTERED_STATUS: Mapping[ErrorCode, int] = {
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.EMAIL_VERIFICATION_REQUIRED: 403,
    ErrorCode.PLAN_REQUIRED: 403,
    ErrorCode.FREE_ALLOWANCE_EXHAUSTED: 403,
    ErrorCode.PRO_FAIR_USE_LIMIT: 429,
    ErrorCode.GENERATION_PAUSED: 503,
    ErrorCode.EARNINGS_ALERT_LIMIT: 403,
}

# The codes a stream's error event may carry: the refusals a stream reaches after it has opened.
STREAM_CODES = frozenset({ErrorCode.FREE_ALLOWANCE_EXHAUSTED, ErrorCode.PRO_FAIR_USE_LIMIT, ErrorCode.GENERATION_PAUSED})


def sse_error(message: str, code: ErrorCode, **fields: Any) -> dict[str, Any]:
    """A stream's error event with ``code`` beside its unchanged keys: ``{"type": "error", "message": ...}``.

    Raises ``ValueError`` for a code outside ``STREAM_CODES``, which the client ignores on a stream, so the producer's
    own test of that branch fails instead of shipping a code nothing reads."""
    if code not in STREAM_CODES:
        raise ValueError(f"{code.value} is not a stream code")
    return {"type": "error", "message": message, "code": code.value, **fields}

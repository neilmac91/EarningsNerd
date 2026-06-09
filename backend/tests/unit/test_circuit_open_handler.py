"""Test the global CircuitOpenError -> 503 exception handler (roadmap Q8).

CircuitOpenError does not subclass EdgarError, so routers that only catch
SECEdgarServiceError would let it fall through to a generic 500. The global handler
converts it into a friendly, retryable 503 with a Retry-After header.
"""
import json
from unittest.mock import MagicMock

import pytest

from app.services.edgar.circuit_breaker import CircuitOpenError


@pytest.mark.asyncio
async def test_circuit_open_handler_returns_503_with_retry_after():
    from main import circuit_open_exception_handler

    request = MagicMock()
    request.method = "GET"
    request.url.path = "/api/companies/search"

    exc = CircuitOpenError("sec_edgar", time_until_recovery=12.0)
    response = await circuit_open_exception_handler(request, exc)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "12"
    body = json.loads(bytes(response.body).decode())
    assert "SEC EDGAR" in body["detail"]
    assert body["retry_after_seconds"] == 12


@pytest.mark.asyncio
async def test_circuit_open_handler_defaults_retry_after_when_unknown():
    from main import circuit_open_exception_handler

    request = MagicMock()
    request.method = "GET"
    request.url.path = "/api/filings/company/AAPL"

    exc = CircuitOpenError("sec_edgar")  # no time_until_recovery
    response = await circuit_open_exception_handler(request, exc)

    assert response.status_code == 503
    assert int(response.headers["Retry-After"]) == 30

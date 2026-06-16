"""Unit tests for Cloudflare Turnstile verification.

Covers the dark-when-unconfigured no-op, token verification (success/failure/missing),
fail-open on infra errors, and the enforce_turnstile 403.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import turnstile


def _run(coro):
    return asyncio.run(coro)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    def __init__(self, *, payload=None, error=None):
        self._payload = payload
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, data=None):
        if self._error is not None:
            raise self._error
        return _Resp(self._payload or {})


def _req(headers=None, ip="1.2.3.4"):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=ip))


def test_disabled_is_a_noop(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")
    assert turnstile.turnstile_enabled() is False
    assert _run(turnstile.verify_turnstile(None)) is True
    _run(turnstile.enforce_turnstile(_req()))  # must not raise when unconfigured


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "test-secret")


def test_missing_token_rejected_when_enabled(enabled):
    assert _run(turnstile.verify_turnstile(None)) is False


def test_valid_token_accepted(monkeypatch, enabled):
    monkeypatch.setattr(
        turnstile.httpx, "AsyncClient", lambda *a, **k: _Client(payload={"success": True})
    )
    assert _run(turnstile.verify_turnstile("tok")) is True


def test_invalid_token_rejected(monkeypatch, enabled):
    monkeypatch.setattr(
        turnstile.httpx, "AsyncClient", lambda *a, **k: _Client(payload={"success": False})
    )
    assert _run(turnstile.verify_turnstile("tok")) is False


def test_network_error_fails_open(monkeypatch, enabled):
    monkeypatch.setattr(
        turnstile.httpx, "AsyncClient", lambda *a, **k: _Client(error=RuntimeError("down"))
    )
    assert _run(turnstile.verify_turnstile("tok")) is True


def test_enforce_raises_403_on_invalid(monkeypatch, enabled):
    monkeypatch.setattr(
        turnstile.httpx, "AsyncClient", lambda *a, **k: _Client(payload={"success": False})
    )
    with pytest.raises(HTTPException) as exc:
        _run(turnstile.enforce_turnstile(_req(headers={"cf-turnstile-response": "bad"})))
    assert exc.value.status_code == 403


def test_enforce_passes_on_valid(monkeypatch, enabled):
    monkeypatch.setattr(
        turnstile.httpx, "AsyncClient", lambda *a, **k: _Client(payload={"success": True})
    )
    _run(turnstile.enforce_turnstile(_req(headers={"cf-turnstile-response": "good"})))  # no raise

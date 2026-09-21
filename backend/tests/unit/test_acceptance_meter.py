"""Provider admission is exercised with fake clients only; no credentials or network."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.ai import provider_requests as requests


class Meter:
    def __init__(self):
        self.events = []

    def reserve(self, request, operation, base_url):
        identity = len(self.events) + 1
        self.events.append(('reserve', identity, operation, request.copy(), base_url))
        return identity

    def settle(self, reservation, usage, model, outcome):
        self.events.append(('settle', reservation, usage, model, outcome))


def service(handler):
    obj = requests._ProviderRequestsMixin()
    obj.fallback_client = None
    obj.client = SimpleNamespace(max_retries=0, chat=SimpleNamespace(
        completions=SimpleNamespace(create=AsyncMock(side_effect=handler))))
    return obj


@pytest.mark.asyncio
@pytest.mark.parametrize('operation,mode', [
    ('summary_primary', 'retry'), ('section_recovery', 'retry'),
    ('attribution_verify', 'retry'), ('summary_primary', 'stream'),
    ('summary_primary', 'cancel'), ('summary_primary', 'deny'),
    ('summary_primary', 'sdk_retry'), ('summary_primary', 'invalid_reservation'),
])
async def test_every_measured_provider_attempt_is_reserved_and_retained(monkeypatch, operation, mode):
    meter = Meter()
    calls = []
    monkeypatch.setattr(requests, 'retry_delay', lambda *_: 0)
    monkeypatch.setattr(requests, 'record_ai_call', lambda **kw: kw)

    async def handler(**kw):
        attempt = requests.current_provider_attempt()
        assert attempt is not None
        assert meter.events[-1][:2] == ('reserve', attempt)
        calls.append(attempt)
        if mode == 'cancel':
            raise asyncio.CancelledError()
        if mode == 'retry' and len(calls) == 1:
            raise TimeoutError('offline timeout')
        return SimpleNamespace(model='deepseek-v4-flash', system_fingerprint=None,
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    obj = service(handler)
    async def stream(kw, cb, _, __, *, _client, _observation, **rest):
        response = await handler(**kw)
        _observation.update(model=response.model, usage=response.usage)
        cb('preview')
        return response.choices[0].message.content
    obj._stream_collect = stream
    previews = []
    if mode == 'deny':
        def refuse(*_):
            raise ValueError('offline admission refused')
        meter.reserve = refuse
    if mode == 'invalid_reservation':
        meter.reserve = lambda *_: None
    if mode == 'sdk_retry':
        obj.client.max_retries = 2
    with requests.measure_provider_requests(meter):
        call = obj._request_content(
            {'model': 'deepseek-v4-flash', 'messages': [{'role':'user','content':'fixture'}],
             'max_tokens': 500}, operation=operation,
            stream_cb=(lambda frame: previews.append((frame, requests.current_provider_attempt())))
            if mode == 'stream' else None)
        if mode in ('deny', 'sdk_retry', 'invalid_reservation'):
            with pytest.raises(ValueError):
                await call
        elif mode == 'cancel':
            with pytest.raises(asyncio.CancelledError):
                await call
        else:
            assert await call == '{"ok":true}'
    assert requests.current_provider_attempt() is None
    assert requests._request_meter.get() is None
    if mode in ('deny', 'sdk_retry', 'invalid_reservation'):
        assert not calls and not meter.events
        return
    reservations = [row for row in meter.events if row[0] == 'reserve']
    settlements = [row for row in meter.events if row[0] == 'settle']
    assert len(calls) == len(reservations) == len(settlements) == (2 if mode == 'retry' else 1)
    assert [r[1] for r in reservations] == calls == [r[1] for r in settlements]
    assert all(r[2] == operation for r in reservations)
    assert settlements[-1][-1] == ('cancelled' if mode == 'cancel' else 'success')
    if mode == 'retry':
        assert settlements[0][2:] == (None, None, 'error')
    if mode == 'stream':
        assert previews == [('preview', calls[0])]
        assert reservations[0][3]['stream_options'] == {'include_usage': True}

"""Keep local follower connections bounded without blocking cached recovery."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from app.database import SessionLocal, engine
from app.models import Base, Summary
from app.routers import summaries
from app.routers.auth import get_current_user
from app.services.rate_limiter import ActiveStreamLimiter
from app.services.summary_request_evidence import SummaryRequestEvidence
from main import app
from tests.support.summary_stream_harness import seed_company_filing


@pytest.fixture
def boundary(monkeypatch):
    Base.metadata.create_all(bind=engine)
    limiter = ActiveStreamLimiter(limit=4)
    monkeypatch.setattr(summaries, "SUMMARY_STREAM_LIMITER", limiter)
    user = SimpleNamespace(id=987654321, is_pro=False, subscription=None,
                           email="offline@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    yield limiter, f"summary:{user.id}"
    app.dependency_overrides.pop(get_current_user, None)
    assert limiter._active == {}, "a response leaked its active stream lease"


def test_active_leases_are_atomic_and_duplicate_release_cannot_free_another_stream():
    limiter = ActiveStreamLimiter(limit=4)
    with ThreadPoolExecutor(max_workers=12) as pool:
        leases = list(pool.map(lambda _: limiter.try_acquire("account"), range(40)))
    held = [lease for lease in leases if lease is not None]
    assert len(held) == 4
    held[0]()
    held[0]()
    assert limiter._active == {"account": 3}
    replacement = limiter.try_acquire("account")
    assert replacement is not None
    assert limiter.try_acquire("account") is None
    for lease in held:
        lease()
    assert limiter._active == {"account": 1}
    replacement()
    assert limiter._active == {}


@pytest.mark.asyncio
async def test_live_stream_cap_keeps_ready_replay_and_get_available(boundary, monkeypatch):
    limiter, key = boundary
    filing_id, cached_id = seed_company_filing(), seed_company_filing()
    with SessionLocal() as session:
        session.add(Summary(filing_id=cached_id, business_overview="A ready cached summary."))
        session.commit()
    held = asyncio.Event()
    all_started = asyncio.Event()
    starts = 0

    async def waiting_pipeline(**kwargs):
        nonlocal starts
        starts += 1
        if starts == 4:
            all_started.set()
        yield {"type": "progress", "stage": "queued"}
        await held.wait()
        yield {"type": "error", "message": "Offline test finished"}

    monkeypatch.setattr(summaries, "stream_filing_summary", waiting_pipeline)
    tasks = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        route = f"/api/summaries/filing/{filing_id}/generate-stream"
        try:
            tasks = [asyncio.create_task(client.post(route)) for _ in range(4)]
            await asyncio.wait_for(all_started.wait(), 3)
            refused = await asyncio.wait_for(client.post(route), 1)
            assert refused.status_code == 429
            assert refused.json()["code"] == "summary_rate_limited"
            assert refused.headers["Retry-After"] == "5"
            assert starts == 4
            assert limiter._active == {key: 4}
            replay = await client.post(f"/api/summaries/filing/{cached_id}/generate-stream")
            assert replay.status_code == 200
            assert '"type": "complete"' in replay.text
            assert (await client.get(f"/api/summaries/filing/{cached_id}")).status_code == 200
            assert limiter._active == {key: 4}
            assert not summaries.SUMMARY_LIMITER._hits
        finally:
            held.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 3)
    assert limiter._active == {}


@pytest.mark.parametrize("failure", ["load_user", "construct_response"])
def test_route_error_before_response_ownership_releases_slot(boundary, monkeypatch, failure):
    filing_id = seed_company_filing()

    def fail(*args, **kwargs):
        raise RuntimeError("offline setup failure")

    target = "load_generation_user" if failure == "load_user" else "SummaryStreamResponse"
    monkeypatch.setattr(summaries, target, fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f"/api/summaries/filing/{filing_id}/generate-stream")
    assert response.status_code == 500
    assert boundary[0]._active == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", ["2.3", "2.4"])
@pytest.mark.parametrize("stop", ["start", "body", "unexpected_error", "cancel", "complete"])
async def test_response_owns_lease_through_unstarted_failure_disconnect_and_cancel(spec, stop):
    limiter = ActiveStreamLimiter(limit=1)
    release = limiter.try_acquire("account")
    item = SummaryRequestEvidence(consent=False, account_id=1, filing_id=1,
                                  logical_request_id=None, client_attempt=None,
                                  transport_attempt=None, entry_point=None)
    send_blocked = asyncio.Event()
    entered = []

    async def producer():
        entered.append(True)
        yield "data: {}\n\n"
        if stop != "complete":
            await asyncio.Event().wait()

    async def send(message):
        target = "http.response.start" if stop == "start" else "http.response.body"
        if message["type"] != target or stop == "complete":
            return
        send_blocked.set()
        if stop == "unexpected_error":
            raise RuntimeError("offline send failure")
        if spec == "2.4" and stop != "cancel":
            raise OSError("offline socket failure")
        await asyncio.Event().wait()

    async def receive():
        if stop == "cancel":
            await asyncio.Event().wait()
        await send_blocked.wait()
        return {"type": "http.disconnect"}

    response = summaries.SummaryStreamResponse(producer(), item, release)
    call = response({"type": "http", "asgi": {"spec_version": spec}}, receive, send)
    if stop == "cancel":
        task = asyncio.create_task(call)
        await asyncio.wait_for(send_blocked.wait(), 2)
        assert limiter._active == {"account": 1}
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif stop == "unexpected_error":
        with pytest.raises(RuntimeError, match="offline send failure"):
            await asyncio.wait_for(call, 2)
    elif spec == "2.4" and stop != "complete":
        with pytest.raises(ClientDisconnect):
            await asyncio.wait_for(call, 2)
    else:
        await asyncio.wait_for(call, 2)
    assert entered == ([] if stop == "start" else [True])
    assert limiter._active == {}
    release()
    assert limiter._active == {}

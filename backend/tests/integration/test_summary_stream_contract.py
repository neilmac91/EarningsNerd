"""T1 — the full ordered SSE event contract of ``stream_filing_summary`` (the user-facing path).

Drives the REAL generator offline through the SHARED harness (``tests.support.summary_stream_harness``
— ONE definition of the boundary mocks, the canonical AI payload, and the Company+Filing seed, reused
by the fixture regen script and the other stream anchors) and pins, hard:

  * the ordered progress contract → a ``chunk`` carrying the summary markdown → exactly one terminal
    ``complete`` event, no ``error`` (``test_sse_ordered_contract``);
  * the ``to_sse`` wire framing (``test_to_sse_framing``);
  * the exact terminal ``complete`` key set the frontend reads (``test_terminal_complete_event_key_set``);
  * the ACTUAL error-frame JSON shape when the pipeline errors — so a ``message``→``detail`` rename, or
    a stray added key, fails (``test_error_frame_shape``);
  * FIELD-BY-FIELD parity between the checked-in frames fixture (shared with the frontend parser test
    T10) and a live drive, masking only volatile values — so a renamed progress message or an added/
    dropped/changed key on any frame is a hard failure (``test_recorded_frames_fixture_matches_live_contract``);
  * that the route itself is wired: ``POST /api/summaries/filing/{id}/generate-stream`` returns an SSE
    response with the streaming headers on success (authenticated — the route requires an account
    since the guest-generation removal; anonymous rejection is pinned in
    ``test_generation_requires_account.py``) and 404s a missing filing
    (``test_generate_stream_route_*``).

Determinism: instant fakes ⇒ the summarize step returns immediately ⇒ no heartbeat frames ⇒ a fully
ordered sequence. The fixture and this test render from ONE source: both mask frames with
``scripts.gen_summary_stream_frames.normalize_frame``, so ``masked-live == recorded`` by construction.
"""
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.routers.auth import get_current_user
from app.services.summary_pipeline import stream_filing_summary, to_sse
from main import app
from scripts.gen_summary_stream_frames import normalize_frame
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

FRAMES_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "summary_stream_frames.json"

# The exact top-level keys the frontend reads off the terminal ``complete`` frame. Enumerated so an
# addition or removal is a conscious, reviewed decision — not something that slips through silently.
COMPLETE_EVENT_KEYS = {"type", "summary_id", "percent"}


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_inflight():
    """A leaked ``_inflight_generations`` slot silently reroutes the next generation down the dedup
    (join) path — reset it around every test so each drives the primary path."""
    reset_inflight()
    yield
    reset_inflight()


@pytest.fixture(scope="module")
def client():
    """A ``TestClient`` whose ``with`` block runs the app lifespan (create_all) for the route tests."""
    with TestClient(app) as test_client:
        yield test_client


async def _drive(filing_id: int) -> list:
    return [
        ev
        async for ev in stream_filing_summary(
            filing_id=filing_id,
            current_user=None,
            user_id=None,
            telemetry_distinct_id="t",
            telemetry_entry_point=None,
            telemetry_ctx={},
        )
    ]


def _fresh_ip_headers() -> dict:
    """Unique per-request ``X-Forwarded-For`` so this request owns a FRESH sliding-window
    rate-limit bucket (``enforce_rate_limit`` prefixes the trusted client IP), isolated from
    sibling route tests / files that also hit ``SUMMARY_LIMITER``. Pairs with
    ``TRUSTED_PROXY_HOPS=1``."""
    return {"X-Forwarded-For": f"stream-route-{uuid.uuid4().hex}"}


@pytest.fixture
def authed_user():
    """Authenticate the route tests: generate-stream requires an account (guest generation was
    removed), so override ``get_current_user`` with a Free stand-in. ``track_usage_sync`` re-queries
    the id and no-ops when absent, so no User row needs seeding for these thin route anchors."""
    stand_in = SimpleNamespace(id=987_654_321, is_pro=False, subscription=None,
                               email="contract@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: stand_in
    yield stand_in
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sse_ordered_contract():
    with stream_boundaries():
        events = await _drive(seed_company_filing())

    # 1. progress stages appear as an ordered subsequence (initializing → … → summarizing)
    stages = [e["stage"] for e in events if e.get("type") == "progress" and "stage" in e]
    expected = ["initializing", "fetching", "parsing", "analyzing", "summarizing"]
    for stage in expected:
        assert stage in stages, f"missing progress stage {stage!r}; got {stages}"
    positions = [stages.index(s) for s in expected]
    assert positions == sorted(positions), f"stages out of order: {stages}"

    # 2. a chunk carries the summary markdown (business_overview)
    chunks = [e for e in events if e.get("type") == "chunk"]
    assert chunks, "no chunk event"
    assert chunks[-1]["content"] == CANONICAL_PAYLOAD["business_overview"]

    # 3. exactly one terminal event, and it's `complete` with percent 100 + an int summary_id
    terminals = [e for e in events if e.get("type") in {"complete", "partial", "error"}]
    assert len(terminals) == 1, f"expected one terminal event, got {[t['type'] for t in terminals]}"
    complete = terminals[0]
    assert complete["type"] == "complete"
    assert complete["percent"] == 100
    assert isinstance(complete["summary_id"], int)

    # 4. every frame is JSON-serializable (it must survive to_sse)
    for ev in events:
        to_sse(ev)


def test_to_sse_framing():
    """The wire framing the frontend parses: ``data: <json>\\n\\n``."""
    frame = to_sse({"type": "complete", "summary_id": 7, "percent": 100})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert json.loads(frame[len("data: "):].strip()) == {"type": "complete", "summary_id": 7, "percent": 100}


@pytest.mark.asyncio
async def test_terminal_complete_event_key_set():
    """The terminal ``complete`` event exposes EXACTLY the keys the frontend reads — no more, no
    less. Adding or dropping one here forces a conscious decision (the client parses these by name)."""
    with stream_boundaries():
        events = await _drive(seed_company_filing())

    complete = events[-1]
    assert complete["type"] == "complete"
    assert set(complete.keys()) == COMPLETE_EVENT_KEYS, (
        f"terminal complete key set changed: {sorted(complete.keys())} != {sorted(COMPLETE_EVENT_KEYS)}"
    )
    assert complete["percent"] == 100
    assert isinstance(complete["summary_id"], int)


@pytest.mark.asyncio
async def test_error_frame_shape():
    """Drive the generator into an error and pin the ACTUAL error frame's JSON shape.

    A ``status: "error"`` AI payload is intercepted by the guard right after summarization
    (``summary_pipeline.py`` ~L624), which yields ``{type, message}`` and returns — BEFORE the later
    ``{type, message, summary_id}`` branch (~L774). So for this trigger the persisted-id branch is
    effectively dead and the frame the frontend actually receives carries NO ``summary_id``. Pinning
    the exact key set makes a ``message``→``detail`` rename (or a stray added key) a hard failure.
    """
    with stream_boundaries(payload={"status": "error", "message": "boom"}):
        events = await _drive(seed_company_filing())

    # Exactly one terminal, and it's the error (no chunk / complete / partial after it).
    terminals = [e for e in events if e.get("type") in {"complete", "partial", "error"}]
    assert [t["type"] for t in terminals] == ["error"], (
        f"expected a lone error terminal, got {[t['type'] for t in terminals]}"
    )
    err = events[-1]
    assert set(err.keys()) == {"type", "message"}  # a message→detail rename fails HERE
    assert err == {"type": "error", "message": "boom"}


@pytest.mark.asyncio
async def test_recorded_frames_fixture_matches_live_contract():
    """FIELD-BY-FIELD parity: the checked-in frames fixture (shared with the frontend parser test
    T10) must match a live drive frame-for-frame, masking only volatile values via the SAME
    ``normalize_frame`` the regen script uses. A renamed progress message, a changed percent, or an
    added/dropped key on any frame — including ``complete`` — is a hard failure here."""
    assert FRAMES_FIXTURE.exists(), (
        f"missing {FRAMES_FIXTURE}; regenerate with scripts/gen_summary_stream_frames.py"
    )
    recorded = json.loads(FRAMES_FIXTURE.read_text())

    with stream_boundaries():
        live = await _drive(seed_company_filing())
    masked = [normalize_frame(e) for e in live]

    assert len(masked) == len(recorded), (
        f"frame count drifted: live={len(masked)} recorded={len(recorded)}; "
        "regenerate via scripts/gen_summary_stream_frames.py"
    )
    for i, (got, want) in enumerate(zip(masked, recorded)):
        assert got == want, (
            f"frame {i} drifted from the recorded fixture:\n  live    = {got}\n  fixture = {want}\n"
            "a renamed message / changed percent / added-or-dropped key breaks the shared "
            "producer↔consumer contract — regenerate via scripts/gen_summary_stream_frames.py"
        )
    assert recorded[-1]["type"] == "complete"


@pytest.mark.requires_db
def test_generate_stream_route_returns_event_stream(client, monkeypatch, authed_user):
    """Thin route test: ``POST /api/summaries/filing/{id}/generate-stream`` is registered and returns
    an SSE response with the streaming headers, and the real generator runs end-to-end to its
    terminal ``complete`` over the wire (boundaries mocked via the shared harness; authenticated —
    the route requires an account)."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    with stream_boundaries():
        filing_id = seed_company_filing()
        resp = client.post(
            f"/api/summaries/filing/{filing_id}/generate-stream",
            headers=_fresh_ip_headers(),
        )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"  # SSE buffering disabled for Cloud Run/nginx
    assert '"type": "complete"' in resp.text  # streamed through to the terminal event


@pytest.mark.requires_db
def test_generate_stream_route_missing_filing_404(client, monkeypatch, authed_user):
    """The route short-circuits with 404 for an unknown filing id (before any generation runs)."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    resp = client.post(
        "/api/summaries/filing/999999999/generate-stream",
        headers=_fresh_ip_headers(),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Filing not found"

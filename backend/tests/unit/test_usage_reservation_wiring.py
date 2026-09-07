"""E07b: the summary pipeline reserves a quota unit at admission and converts or releases it.

Runs the real pipeline offline (shared harness) against the SQLite test DB the way the route
does: with a ``GenerationUserSnapshot`` as ``current_user`` (the headless drain passes None and
never reaches the admission block). The harness patches ``check_usage_limit`` (the patchable
read) but leaves ``reserve_summary_use`` real, so these pin the wiring: a full result converts
the reservation into exactly one counted unit, a partial or failed generation releases it, the
read-side block never reserves, and the serialized decision can still block a request the read
admitted. PostgreSQL concurrency lives in tests/integration/test_usage_counter_transactions.py.
"""
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models import UsageReservation, User, UserUsage
from app.services import subscription_service as usage
from app.services import summary_pipeline
from app.services.subscription_service import get_current_month
from app.services.summary_pipeline import GenerationUserSnapshot, stream_filing_summary
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)


@pytest.fixture(autouse=True)
def _tables():
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield


def _seed_user() -> int:
    with SessionLocal() as db:
        user = User(email=f"res-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        db.commit()
        return user.id


async def _run(filing_id: int, user_id: int) -> list[dict]:
    """Drive the user-facing pipeline path with a Free snapshot, as the SSE route does."""
    snapshot = GenerationUserSnapshot(user_id, False, None)
    return [event async for event in stream_filing_summary(
        filing_id=filing_id, current_user=snapshot, user_id=user_id, telemetry_distinct_id=str(user_id),
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )]


def _state(user_id: int) -> tuple[int, int]:
    with SessionLocal() as db:
        reservations = db.query(UsageReservation).filter_by(user_id=user_id).count()
        bucket = db.query(UserUsage).filter_by(user_id=user_id, month=get_current_month()).first()
        return reservations, (bucket.summary_count if bucket else 0)


@pytest.mark.asyncio
async def test_full_result_converts_the_reservation_into_one_counted_unit():
    user_id, filing_id = _seed_user(), seed_company_filing()
    with stream_boundaries():
        events = await _run(filing_id, user_id)
    assert events[-1]["type"] == "complete"
    assert _state(user_id) == (0, 1)


@pytest.mark.asyncio
async def test_partial_result_releases_the_reservation_without_counting():
    user_id, filing_id = _seed_user(), seed_company_filing()
    partial = {**CANONICAL_PAYLOAD, "raw_summary": {"sections": {}, "section_coverage": {
        "per_section": {"executive_snapshot": True, "financial_highlights": True}, "covered_count": 2, "total_count": 9,
    }}}
    with stream_boundaries(payload=partial), patch.object(summary_pipeline.settings, "AI_QUALITY_GATE", True):
        await _run(filing_id, user_id)
    assert _state(user_id) == (0, 0)


@pytest.mark.asyncio
async def test_reservation_is_held_while_the_provider_runs():
    user_id, filing_id = _seed_user(), seed_company_filing()
    seen: list[tuple[int, int]] = []

    async def observe(*args, **kwargs):
        seen.append(_state(user_id))
        return CANONICAL_PAYLOAD

    with stream_boundaries() as summarize:
        summarize.side_effect = observe
        await _run(filing_id, user_id)
    assert seen == [(1, 0)]  # one reservation, nothing counted, while the provider ran
    assert _state(user_id) == (0, 1)


@pytest.mark.asyncio
async def test_failed_generation_releases_the_reservation():
    user_id, filing_id = _seed_user(), seed_company_filing()
    with stream_boundaries() as summarize:
        summarize.side_effect = RuntimeError("provider down")
        events = await _run(filing_id, user_id)
    assert events[-1]["type"] == "error"
    assert _state(user_id) == (0, 0)


@pytest.mark.asyncio
async def test_completion_after_a_month_rollover_counts_in_the_admitted_month():
    """A lease admitted in one UTC month and converted in the next charges the month whose quota
    admitted it. The new month's admissions never saw that lease, so counting it there could let
    the new month exceed its cap by the number of straddling generations."""
    user_id, filing_id = _seed_user(), seed_company_filing()
    admitted_month = "2000-01"
    # Admission (the service's own clock) happens in the old month; conversion runs after the
    # rollover on the pipeline's clock, which stays real.
    with stream_boundaries(), patch.object(usage, "get_current_month", lambda: admitted_month):
        events = await _run(filing_id, user_id)
    assert events[-1]["type"] == "complete"
    with SessionLocal() as db:
        buckets = {b.month: b.summary_count for b in db.query(UserUsage).filter_by(user_id=user_id)}
        assert db.query(UsageReservation).filter_by(user_id=user_id).count() == 0
    assert buckets == {admitted_month: 1}


def test_account_deletion_takes_live_and_expired_reservations_with_it():
    """Same ORM deletion as DELETE /api/users/me on the full schema: leases go with the account
    instead of orphaning (SQLite has no FK enforcement here) or rejecting the delete (the
    PostgreSQL FK cascade is proved in tests/integration/test_usage_counter_transactions.py)."""
    user_id = _seed_user()
    now = usage.utcnow()
    with SessionLocal() as db:
        for expires_at in (now + timedelta(seconds=300), now - timedelta(seconds=1)):  # live, then stale
            db.add(UsageReservation(user_id=user_id, month=get_current_month(), kind=usage.SUMMARY_RESERVATION_KIND,
                                    token=uuid.uuid4().hex, expires_at=expires_at, created_at=now))
        db.commit()
        db.delete(db.query(User).filter(User.id == user_id).one())
        db.commit()
    with SessionLocal() as db:
        assert db.query(User).filter(User.id == user_id).first() is None
        assert db.query(UsageReservation).filter_by(user_id=user_id).count() == 0


def test_read_side_block_never_reserves_and_serialized_block_is_honoured():
    user_id = _seed_user()
    reserve = MagicMock(return_value=(True, 0, 5, "tok"))
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).one()
        with patch.object(summary_pipeline, "check_usage_limit", lambda u, s: (False, 5, 5)), \
             patch.object(summary_pipeline, "reserve_summary_use", reserve):
            assert summary_pipeline._check_usage_and_plan(user, db) == (False, 5, 5, False, None)
        reserve.assert_not_called()
        with patch.object(summary_pipeline, "check_usage_limit", lambda u, s: (True, 4, 5)), \
             patch.object(summary_pipeline, "reserve_summary_use", lambda u, s: (False, 4, 5, None)):
            assert summary_pipeline._check_usage_and_plan(user, db) == (False, 4, 5, False, None)
        with patch.object(summary_pipeline, "check_usage_limit", lambda u, s: (True, 4, 5)), \
             patch.object(summary_pipeline, "reserve_summary_use", reserve):
            assert summary_pipeline._check_usage_and_plan(user, db) == (True, 0, 5, False, "tok")


def test_unlimited_pro_without_a_cap_reserves_nothing(monkeypatch):
    from types import SimpleNamespace

    from app.services import subscription_service as usage

    monkeypatch.setattr(usage, "get_entitlements", lambda user: SimpleNamespace(monthly_summary_limit=None))
    monkeypatch.setattr(usage.settings, "PRO_SUMMARY_MONTHLY_CAP", 0)
    assert usage.reserve_summary_use(SimpleNamespace(id=1), db=None) == (True, 0, None, None)


@pytest.mark.asyncio
async def test_client_disconnect_mid_generation_releases_lease_slot_and_leadership():
    """uvicorn speaks ASGI 2.3, so on a client disconnect Starlette CANCELS the streaming task
    and keeps re-delivering the cancellation at every await until the generator exits. The
    pipeline's ``finally`` awaits (provider task drain, lease release) before it releases the
    generation slot and in-flight leadership, so unshielded cleanup aborts at its first await:
    the lease waits out its TTL, the slot is gone for the process lifetime and every later
    request for the filing joins a leader that never finishes. Drives the real pipeline through
    the route's wrapper and ``StreamingResponse`` with a raw 2.3 scope; TestClient never takes
    that path."""
    import asyncio

    from starlette.responses import StreamingResponse

    from app.services.summary_pipeline import to_sse

    user_id, filing_id = _seed_user(), seed_company_filing()
    provider_started, disconnected = asyncio.Event(), asyncio.Event()

    async def blocking_provider(*args, **kwargs):
        provider_started.set()
        await asyncio.sleep(30)  # still generating when the client leaves
        return CANONICAL_PAYLOAD

    async def event_stream():
        async for event in stream_filing_summary(
            filing_id=filing_id, current_user=GenerationUserSnapshot(user_id, False, None), user_id=user_id,
            telemetry_distinct_id=str(user_id), telemetry_entry_point=None, telemetry_ctx={},
            emit_funnel_telemetry=False,
        ):
            yield to_sse(event)

    async def receive():
        await provider_started.wait()
        await asyncio.sleep(0.05)
        disconnected.set()
        return {"type": "http.disconnect"}

    async def send(message):
        if disconnected.is_set() and message["type"] == "http.response.body":
            raise OSError("peer closed connection")

    with stream_boundaries() as summarize, patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.2):
        summarize.side_effect = blocking_provider
        semaphore = summary_pipeline._get_generation_semaphore()
        slots_before = semaphore._value
        response = StreamingResponse(event_stream(), media_type="text/event-stream")
        await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.3"}, "headers": []}, receive, send), 10)
        await asyncio.sleep(0.1)
    assert _state(user_id) == (0, 0)  # lease released, nothing counted
    assert semaphore._value == slots_before  # generation slot given back
    assert filing_id not in summary_pipeline._inflight_generations  # leadership released

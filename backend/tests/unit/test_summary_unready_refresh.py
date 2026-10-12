"""A stored summary the filing page cannot show is regenerated in place, for any signed-in user.

The filing page shows a stored row as its "Summary temporarily unavailable" card (with Retry) or as
"generating" when the row fails the readiness rule (summary_placeholders.is_summary_ready): failure
filler, a writer error, an empty body, or an earlier pipeline's in-progress marker. Before this, the
route replayed such a row on every visit, and Retry sent force=true, which is Pro-only, so a Free
user had no way out and a stale marker never left "generating". Now:

  stored row        force   user   result
  not ready         no      Free   regenerated in place (same summaries.id), metered as a generation
  not ready         yes     Free   regenerated in place (no 403: there is nothing to wipe)
  ready             no      Free   replayed, no generation
  ready             yes     Free   403, Pro-only as before

Keep-better protects only a row the page shows: a refresh that comes back below a not-ready row's
stored tier still replaces it. A refresh that fails saves nothing, so the stored row survives for
the next retry. An unready row counts as a missing summary throughout: the route clears nothing for
it (no XBRL, no progress), and the pipeline re-reads it at admission, after a joined leader
finishes, and at save, under the row lock its write takes. The locked anchors (test_summary_request_evidence, the background
characterization) are untouched; their stored bodies are ready.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary, SummaryGenerationProgress, User, UserUsage
from app.routers.auth import get_current_user
from app.services.summary_generation_service import generate_summary_background
from main import app
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

FAILURE_FILLER = "Summary temporarily unavailable. Please retry."
STALE_MARKER = "Generating summary... please wait."
READY_BODY = "# Summary\n\nStored analysis the filing page shows."

# A result assess_quality grades "partial" (2 of 9 sections), as a 75s AI-timeout fallback does.
PARTIAL_PAYLOAD = {
    **CANONICAL_PAYLOAD,
    "business_overview": "# Summary\n\nPartial analysis from the refresh.",
    "raw_summary": {
        "sections": {},
        "section_coverage": {
            "per_section": {"executive_snapshot": True, "financial_highlights": True},
            "covered_count": 2,
            "total_count": 9,
        },
    },
}


@pytest.fixture(autouse=True)
def free_user():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    stand_in = SimpleNamespace(id=987654322, is_pro=False, subscription=None,
                               email="unready@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: stand_in
    from app.routers import summaries
    summaries.SUMMARY_LIMITER._hits.clear()
    yield stand_in
    app.dependency_overrides.pop(get_current_user, None)
    reset_inflight()


def _seed_summary(filing_id, body, raw_summary=None):
    with SessionLocal() as db:
        row = Summary(filing_id=filing_id, business_overview=body, raw_summary=raw_summary)
        db.add(row)
        db.commit()
        row_id = row.id
        # A later row, so a delete and re-insert cannot come back with the same id: SQLite reuses the
        # highest id once it is deleted, which would pass an "updated in place" check.
        db.add(Summary(filing_id=seed_company_filing(), business_overview=READY_BODY))
        db.commit()
        return row_id


def _stored(filing_id):
    with SessionLocal() as db:
        rows = db.query(Summary).filter(Summary.filing_id == filing_id).all()
        assert len(rows) == 1  # always one row: an in-place UPDATE, never delete + insert
        return rows[0].id, rows[0].business_overview, (rows[0].raw_summary or {})


def _post(filing_id, query=""):
    with TestClient(app) as client:
        return client.post(f"/api/summaries/filing/{filing_id}/generate-stream{query}")


@pytest.mark.parametrize(
    ("body", "raw_summary"),
    [
        (FAILURE_FILLER, None),
        ("Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY.", None),
        (STALE_MARKER, None),
        ("   ", None),
        (READY_BODY, {"writer_error": "writer output failed validation"}),
    ],
    ids=["failure-filler", "api-key-placeholder", "stale-marker", "empty", "writer-error"],
)
def test_free_user_visit_regenerates_an_unready_row_in_place(body, raw_summary):
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, body, raw_summary)

    with stream_boundaries() as summarize:
        response = _post(filing_id)

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    summarize.assert_awaited_once()  # a fresh generation, not a replay of the unready row
    row_id, overview, raw = _stored(filing_id)
    assert row_id == stored_id  # in place: a bookmark on the row keeps resolving
    assert "Acme Corp designs and sells widgets worldwide." in overview
    if body.strip():
        assert body.strip() not in overview
    assert not raw.get("writer_error")


def test_free_user_retry_with_force_on_an_unready_row_is_not_forbidden():
    # The page's Retry on the "Summary temporarily unavailable" card sends force=true.
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)

    with stream_boundaries() as summarize:
        response = _post(filing_id, "?force=true")

    assert response.status_code == 200
    summarize.assert_awaited_once()
    row_id, overview, _ = _stored(filing_id)
    assert row_id == stored_id
    assert FAILURE_FILLER not in overview


def test_a_ready_row_is_replayed_without_a_generation():
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, READY_BODY)

    with stream_boundaries() as summarize:
        response = _post(filing_id)

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert "Stored analysis the filing page shows." in response.text
    summarize.assert_not_called()
    assert _stored(filing_id)[:2] == (stored_id, READY_BODY)


def test_force_over_a_ready_row_stays_pro_only():
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, READY_BODY)

    with stream_boundaries() as summarize:
        response = _post(filing_id, "?force=true")

    assert response.status_code == 403
    assert response.json()["detail"] == "Regenerating an analysis is a Pro feature."
    summarize.assert_not_called()
    assert _stored(filing_id)[:2] == (stored_id, READY_BODY)


def test_a_refresh_that_fails_keeps_the_stored_row_for_the_next_retry():
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)

    with stream_boundaries(payload={"status": "error", "message": "offline failure"}) as summarize:
        response = _post(filing_id)

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    summarize.assert_awaited_once()
    assert _stored(filing_id)[:2] == (stored_id, FAILURE_FILLER)


def test_keep_better_never_keeps_an_unready_row_over_a_fresh_partial():
    # The stored failure row claims tier "full"; the refresh comes back partial. Keep-better would
    # keep a stored full the page shows; it must not keep filler the page cannot show.
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER, {"quality": {"tier": "full"}})

    with stream_boundaries(payload=PARTIAL_PAYLOAD):
        response = _post(filing_id)

    assert response.status_code == 200
    row_id, overview, raw = _stored(filing_id)
    assert row_id == stored_id
    assert "Partial analysis from the refresh." in overview
    assert raw.get("quality", {}).get("tier") == "partial"


@pytest.mark.asyncio
async def test_admin_refresh_replaces_an_unready_row_even_when_the_refresh_is_partial():
    # The same gate on the background path (admin refresh-stale threads force_regenerate=True).
    filing_id = seed_company_filing(filing_type="10-Q")
    stored_id = _seed_summary(filing_id, STALE_MARKER, {"quality": {"tier": "full"}})

    with stream_boundaries(payload=PARTIAL_PAYLOAD):
        await generate_summary_background(filing_id, None, force_regenerate=True)

    row_id, overview, raw = _stored(filing_id)
    assert row_id == stored_id
    assert STALE_MARKER not in overview
    assert raw.get("quality", {}).get("tier") == "partial"


# --- Admitted for an unready row, the run re-checks it (Codex review on #1166, two rounds) ----------
# The route decides from the row it read; another request (another process, or a run that finished in
# between) may make the row ready before this run reaches the pipeline or while it generates. A run
# admitted only for an unready row must then serve or keep that summary, never pay for another one
# under the waived Pro gate or replace a summary readers now see. Nor may it have cleared what that
# request wrote on the way, and a leader it joined that failed leaves it a missing summary to claim.

OTHER_READY = "# Summary\n\nA summary another request finished first."
WINNER_XBRL = {"revenue": [{"period": "FY2025", "value": 1000}]}


def _make_ready(filing_id):
    with SessionLocal() as db:
        row = db.query(Summary).filter(Summary.filing_id == filing_id).one()
        row.business_overview = OTHER_READY
        row.raw_summary = {"quality": {"tier": "full"}}
        db.commit()


@pytest.mark.parametrize("query", ["", "?force=true"])
def test_a_row_made_ready_before_the_pipeline_starts_is_served_with_nothing_cleared(monkeypatch, query):
    # The other request's run fetched the filing's XBRL and recorded progress early, then saves its
    # summary after this route has read the row as unready. This run serves that summary and rebuilds
    # neither, so the route must not have cleared them: the change report reads that XBRL.
    from app.routers import summaries

    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)
    with SessionLocal() as db:
        db.get(Filing, filing_id).xbrl_data = WINNER_XBRL
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage="summarizing"))
        db.commit()
    original = summaries.load_generation_user

    def ready_in_between(snapshot):
        _make_ready(filing_id)  # after the route's decision, before the pipeline's first read
        return original(snapshot)

    monkeypatch.setattr(summaries, "load_generation_user", ready_in_between)
    with stream_boundaries() as summarize:
        response = _post(filing_id, query)

    assert response.status_code == 200
    assert "A summary another request finished first." in response.text
    summarize.assert_not_called()
    assert _stored(filing_id)[:2] == (stored_id, OTHER_READY)
    with SessionLocal() as db:
        assert db.get(Filing, filing_id).xbrl_data == WINNER_XBRL
        assert db.get(SummaryGenerationProgress, filing_id) is not None


def test_a_row_made_ready_during_generation_is_kept_not_replaced():
    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)

    async def finished_elsewhere(*_args, **_kwargs):
        _make_ready(filing_id)  # another process saves while this run generates
        return CANONICAL_PAYLOAD

    with stream_boundaries() as summarize:
        summarize.side_effect = finished_elsewhere
        response = _post(filing_id)

    assert response.status_code == 200
    summarize.assert_awaited_once()
    assert _stored(filing_id)[:2] == (stored_id, OTHER_READY)


def test_the_save_reads_the_row_under_the_lock_its_write_takes():
    # Codex review on #1166 (P1): two instances refreshing one unready row could both read it as unready
    # at save, and the later commit overwrote the first ready summary. The save's read takes the row lock
    # its UPDATE takes, so on PostgreSQL the later save waits for that commit and reads the ready row
    # (the case above keeps it). SQLite omits the clause, so this pins the read as PostgreSQL runs it.
    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session

    filing_id = seed_company_filing()
    _seed_summary(filing_id, FAILURE_FILLER)
    reads = []

    def record(state):
        if state.is_select and any(mapper.class_ is Summary for mapper in state.all_mappers):
            reads.append(str(state.statement.compile(dialect=postgresql.dialect())))

    event.listen(Session, "do_orm_execute", record)
    try:
        with stream_boundaries():
            response = _post(filing_id)
    finally:
        event.remove(Session, "do_orm_execute", record)

    assert response.status_code == 200
    assert _stored(filing_id)[1] != FAILURE_FILLER
    locked = [sql for sql in reads if "FOR NO KEY UPDATE" in sql]
    assert len(locked) == 1, reads  # the save's read; admission and join reads take no lock


def test_a_forced_retry_with_no_row_serves_a_summary_saved_in_between(monkeypatch):
    # Force with no stored row waives nothing, so any user may send it (a Retry after a failed first
    # generation). Another request may save a summary between the route's read and the pipeline's first
    # read; this run serves it rather than paying for another (correctness review on #1166).
    from app.routers import summaries

    filing_id = seed_company_filing()
    original = summaries.load_generation_user

    def saved_in_between(snapshot):
        _seed_summary(filing_id, OTHER_READY, {"quality": {"tier": "full"}})
        return original(snapshot)

    monkeypatch.setattr(summaries, "load_generation_user", saved_in_between)
    with stream_boundaries() as summarize:
        response = _post(filing_id, "?force=true")

    assert response.status_code == 200
    assert "A summary another request finished first." in response.text
    summarize.assert_not_called()
    assert _stored(filing_id)[1] == OTHER_READY


def test_a_forced_retry_with_no_row_keeps_a_summary_saved_during_generation():
    filing_id = seed_company_filing()

    async def saved_elsewhere(*_args, **_kwargs):
        # No quality tier: keep-better alone would let this run replace a summary readers now see.
        _seed_summary(filing_id, OTHER_READY)
        return CANONICAL_PAYLOAD

    with stream_boundaries() as summarize:
        summarize.side_effect = saved_elsewhere
        response = _post(filing_id, "?force=true")

    assert response.status_code == 200
    summarize.assert_awaited_once()
    assert _stored(filing_id)[1] == OTHER_READY


@pytest.mark.asyncio
async def test_a_follower_of_a_failed_unready_refresh_generates_instead_of_serving_the_row():
    # Two visitors on one process refresh the same unready row, and the second joins the first. The
    # first fails and saves nothing, so the unready row is still there. The follower claims the
    # generation, as a follower of a failed first generation does; serving the row would hand it
    # the failure card (or "generating" for good) as its result.
    from app.services import summary_pipeline as pipeline

    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)
    leader = pipeline._claim_inflight(filing_id)  # the first visitor's run, generating
    joined = asyncio.Event()

    async def follow():
        events = []
        async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="t",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
            force_regenerate=True, replace_unready_only=True,
        ):
            events.append(event)
            if event.get("stage") == "queued":
                joined.set()
        return events

    with stream_boundaries() as summarize:
        follower = asyncio.create_task(follow())
        try:
            await asyncio.wait_for(joined.wait(), 2)
            pipeline._release_inflight(filing_id, leader)  # the first run failed: nothing saved
            events = await asyncio.wait_for(follower, 5)
        finally:
            follower.cancel()
            await asyncio.gather(follower, return_exceptions=True)

    summarize.assert_awaited_once()
    assert events[-1]["type"] == "complete"
    row_id, overview, _ = _stored(filing_id)
    assert row_id == stored_id
    assert FAILURE_FILLER not in overview


@pytest.mark.asyncio
async def test_a_follower_of_a_refresh_that_succeeds_is_served_its_summary():
    # The other half of the join: the leader saves a summary the page shows, and the follower serves
    # it without a generation of its own (tests-and-gates review on #1166).
    from app.services import summary_pipeline as pipeline

    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)
    leader = pipeline._claim_inflight(filing_id)  # the first visitor's run, generating
    joined = asyncio.Event()

    async def follow():
        events = []
        async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="t",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
            force_regenerate=True, replace_unready_only=True,
        ):
            events.append(event)
            if event.get("stage") == "queued":
                joined.set()
        return events

    with stream_boundaries() as summarize:
        follower = asyncio.create_task(follow())
        try:
            await asyncio.wait_for(joined.wait(), 2)
            _make_ready(filing_id)  # the first run saves its summary
            pipeline._release_inflight(filing_id, leader)
            events = await asyncio.wait_for(follower, 5)
        finally:
            follower.cancel()
            await asyncio.gather(follower, return_exceptions=True)

    summarize.assert_not_called()
    assert events[-1]["type"] == "complete"
    assert "A summary another request finished first." in events[-1]["summary"]
    assert _stored(filing_id)[:2] == (stored_id, OTHER_READY)


def test_a_refresh_is_metered_like_any_generation():
    # A Free user already at the monthly cap gets the cap's paywall frame, not a free generation: the
    # waived Pro gate is not a waived quota (tests-and-gates review on #1166).
    from sqlalchemy.orm import joinedload

    from app.services.subscription_service import FREE_TIER_SUMMARY_LIMIT, get_current_month

    filing_id = seed_company_filing()
    stored_id = _seed_summary(filing_id, FAILURE_FILLER)
    with SessionLocal() as db:
        user = User(email=f"cap-{uuid.uuid4().hex}@example.com", hashed_password="x",
                    email_verified=True, is_active=True, is_pro=False)
        db.add(user)
        db.commit()
        uid = user.id
        db.add(UserUsage(user_id=uid, month=get_current_month(), summary_count=FREE_TIER_SUMMARY_LIMIT))
        db.commit()
        user = db.query(User).options(joinedload(User.subscription)).filter(User.id == uid).first()
        db.expunge(user)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with stream_boundaries(patch_usage_limit=False) as summarize:
            response = _post(filing_id)
    finally:
        with SessionLocal() as db:
            db.query(UserUsage).filter(UserUsage.user_id == uid).delete()
            db.query(User).filter(User.id == uid).delete()
            db.commit()

    assert response.status_code == 200
    assert '"type": "error"' in response.text and "Upgrade to Pro" in response.text
    summarize.assert_not_called()
    assert _stored(filing_id)[:2] == (stored_id, FAILURE_FILLER)


@pytest.mark.asyncio
@pytest.mark.parametrize(("replace_unready_only", "generates"), [(True, False), (False, True)])
async def test_only_a_run_admitted_for_an_unready_row_serves_a_ready_one(replace_unready_only, generates):
    # The control: a forced run (a Pro "Regenerate") still regenerates a ready row; the flag alone
    # turns the same call into a replay.
    from app.services import summary_pipeline as pipeline

    filing_id = seed_company_filing()
    _seed_summary(filing_id, READY_BODY)
    with stream_boundaries() as summarize:
        events = [event async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="t",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
            force_regenerate=True, replace_unready_only=replace_unready_only,
        )]
    assert events[-1]["type"] == "complete"
    assert summarize.await_count == (1 if generates else 0)

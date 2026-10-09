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
the next retry. The locked anchors (test_summary_request_evidence, the background characterization)
are untouched; their stored bodies are ready.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import Base, Summary
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
        return row.id


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

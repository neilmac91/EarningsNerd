"""A Pro "Regenerate" keeps the filing's XBRL snapshot until fresh XBRL arrives.

The force path of ``POST /api/summaries/filing/{id}/generate-stream`` used to write
``Filing.xbrl_data = None`` and commit before the pipeline admitted the run, so the run would
re-fetch XBRL. The column is rewritten only by the run's own XBRL task, so a run the pipeline refused
(the fair-use ceiling) or that ended before that task persisted (an SEC document-fetch failure
cancels it during release) left the filing with no snapshot while its stored summary was still
served, and ``GET /api/summaries/filing/{id}`` lost that summary's source verification.

Now the route clears nothing and sets ``refresh_xbrl``; the run looks past the persisted snapshot,
overwrites it only with the XBRL it got, and uses the stored snapshot when nothing arrives. Only that
route sets the flag: ``force_regenerate`` alone (the admin refresh-stale endpoint, the job drain, a
forced precompute and the route's refresh of an unready row) still reads the persisted snapshot and
fetches nothing.

Only the SEC boundary is faked (``EdgarXBRLService._fetch_xbrl_data``); the persisted-snapshot read,
the caches and the pipeline run for real (``real_xbrl_lookup``).
"""
import asyncio
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary, SummaryGenerationProgress, User, UserUsage
from app.routers.auth import get_current_user
from app.services import summary_pipeline
from app.services.edgar.compat import XBRLServiceCompat
from app.services.edgar.xbrl_service import edgar_xbrl_service
from app.services.subscription_service import get_current_month
from app.services.summary_generation_service import generate_summary_background
from main import app
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries

STORED = {"revenue": [{"period": "2025-12-31", "start": "2025-01-01", "value": 1_000_000_000.0,
                       "form": "10-K", "fy": 2025, "fp": "FY", "accn": "stored"}]}
FRESH = {"revenue": [{"period": "2025-12-31", "start": "2025-01-01", "value": 2_000_000_000.0,
                      "form": "10-K", "fy": 2025, "fp": "FY", "accn": "fresh"}]}
READY = "# Summary\n\nStored analysis the filing page shows."
FAILURE_FILLER = "Summary temporarily unavailable. Please retry."
HIGHLIGHTS = {"table": [{"metric": "Revenue", "current_period": "$1.0B", "prior_period": "", "commentary": "x"}]}


@pytest.fixture(autouse=True)
def pro_user():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    with SessionLocal() as db:
        user = User(email=f"pro-regen-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x", is_pro=True)
        db.add(user)
        db.commit()
        user_id = user.id
    stand_in = SimpleNamespace(id=user_id, is_pro=True, subscription=None, email="pro-regen@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: stand_in
    from app.routers import summaries
    summaries.SUMMARY_LIMITER._hits.clear()
    yield stand_in
    app.dependency_overrides.pop(get_current_user, None)
    reset_inflight()


@contextmanager
def real_xbrl_lookup(fetch):
    """Undo the stream harness's XBRL stub and fake only the SEC fetch (``fetch``)."""
    compat = summary_pipeline.xbrl_service
    with patch.object(compat, "get_xbrl_data", XBRLServiceCompat.get_xbrl_data.__get__(compat)), \
         patch.object(edgar_xbrl_service, "_fetch_xbrl_data", fetch):
        yield


def _seed(body=READY):
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.get(Filing, filing_id).xbrl_data = STORED
        db.add(Summary(filing_id=filing_id, business_overview=body, raw_summary={"sections": {}},
                       financial_highlights=HIGHLIGHTS))
        db.commit()
    return filing_id


def _at_the_fair_use_ceiling(user_id, monkeypatch):
    monkeypatch.setattr(settings, "PRO_SUMMARY_MONTHLY_CAP", 1)
    with SessionLocal() as db:
        db.add(UserUsage(user_id=user_id, month=get_current_month(), summary_count=1))
        db.commit()


def _regenerate(client, filing_id):
    return client.post(f"/api/summaries/filing/{filing_id}/generate-stream?force=true")


def _revenue_row(client, filing_id):
    return client.get(f"/api/summaries/filing/{filing_id}").json()["financial_highlights"]["table"][0]


def _stored_xbrl(filing_id):
    with SessionLocal() as db:
        return db.get(Filing, filing_id).xbrl_data


def _overview(filing_id):
    with SessionLocal() as db:
        return db.query(Summary).filter(Summary.filing_id == filing_id).one().business_overview


def _metrics(data):
    return edgar_xbrl_service.extract_standardized_metrics(data)


async def _still_fetching(*_args):
    await asyncio.sleep(5)  # still running when the document fetch fails; release cancels it
    return FRESH


@pytest.mark.parametrize("ending", ["fair_use_refusal", "document_fetch_fails"])
def test_a_regenerate_that_ends_before_fresh_xbrl_keeps_the_snapshot_and_its_verification(
    pro_user, monkeypatch, ending,
):
    filing_id = _seed()
    refused = ending == "fair_use_refusal"
    if refused:
        _at_the_fair_use_ceiling(pro_user.id, monkeypatch)
        fetch, expected = AsyncMock(return_value=FRESH), "temporarily paused new summary generation"
    else:
        fetch, expected = _still_fetching, "We could not generate this summary"

    with TestClient(app) as client:
        before = _revenue_row(client, filing_id)
        with stream_boundaries(patch_usage_limit=not refused) as summarize, real_xbrl_lookup(fetch), \
                patch.object(summary_pipeline.sec_edgar_service, "get_filing_document",
                             AsyncMock(side_effect=RuntimeError("SEC 503"))):
            response = _regenerate(client, filing_id)
        after = _revenue_row(client, filing_id)

    assert expected in response.text
    summarize.assert_not_called()
    assert _stored_xbrl(filing_id) == STORED
    assert _overview(filing_id) == READY
    # The kept summary keeps the source verification GET builds from the snapshot.
    assert before["source_verified"] is True and before["xbrl_concept"] == "Revenue"
    assert after == before


def test_a_regenerate_with_fresh_xbrl_replaces_the_snapshot_and_generates_from_it():
    filing_id = _seed()
    fetch = AsyncMock(return_value=FRESH)

    with stream_boundaries() as summarize, real_xbrl_lookup(fetch), TestClient(app) as client:
        response = _regenerate(client, filing_id)

    assert '"type": "complete"' in response.text
    fetch.assert_awaited_once()  # looked past the persisted snapshot
    assert _stored_xbrl(filing_id) == FRESH
    assert summarize.await_args.kwargs["xbrl_metrics"] == _metrics(FRESH)


def test_a_regenerate_whose_xbrl_fetch_comes_back_empty_keeps_and_uses_the_stored_snapshot():
    # The service maps every SEC failure (a timeout, a non-2xx, an empty companyfacts set) to None.
    filing_id = _seed()
    fetch = AsyncMock(return_value=None)

    with stream_boundaries() as summarize, real_xbrl_lookup(fetch), TestClient(app) as client:
        response = _regenerate(client, filing_id)

    assert '"type": "complete"' in response.text
    fetch.assert_awaited_once()
    assert _stored_xbrl(filing_id) == STORED
    # The run generates from what it would have used without force: the stored snapshot.
    assert summarize.await_args.kwargs["xbrl_metrics"] == _metrics(STORED)


def test_a_regenerate_whose_xbrl_fetch_outlasts_the_enrichment_join_keeps_the_snapshot(monkeypatch):
    # The stated limit: the join cancels a fetch still running at its timeout, and the run generates
    # without XBRL, as the force path always has. The snapshot is never cleared, so it stays.
    monkeypatch.setattr(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 0.5)
    filing_id = _seed()

    with stream_boundaries() as summarize, real_xbrl_lookup(_still_fetching), TestClient(app) as client:
        response = _regenerate(client, filing_id)

    assert '"type": "complete"' in response.text
    assert summarize.await_args.kwargs["xbrl_metrics"] is None
    assert _stored_xbrl(filing_id) == STORED


@pytest.mark.parametrize("caller", ["background_force_regenerate", "unready_row_route"])
def test_force_regenerate_without_refresh_xbrl_reads_the_snapshot_and_fetches_nothing(caller):
    # generate_summary_background(force_regenerate=True) is what the admin refresh-stale endpoint
    # (admin_summary_service.regenerate_in_place), the job drain (summary_refresh.drain_stale) and a
    # forced precompute call; the route's unready-row refresh also forces without refreshing XBRL.
    filing_id = _seed(READY if caller == "background_force_regenerate" else FAILURE_FILLER)
    fetch = AsyncMock(return_value=FRESH)

    with stream_boundaries() as summarize, real_xbrl_lookup(fetch):
        if caller == "background_force_regenerate":
            outcome = asyncio.run(generate_summary_background(filing_id, None, force_regenerate=True))
            assert outcome["type"] == "complete"
        else:
            with TestClient(app) as client:
                assert '"type": "complete"' in _regenerate(client, filing_id).text

    summarize.assert_awaited_once()
    fetch.assert_not_called()
    assert _stored_xbrl(filing_id) == STORED
    assert summarize.await_args.kwargs["xbrl_metrics"] == _metrics(STORED)


def test_the_progress_row_the_route_clears_is_invisible_while_the_summary_exists(pro_user, monkeypatch):
    # The force path still deletes the filing's progress row before admission, so the run's row starts
    # a fresh clock. That is harmless: the branch runs only while a summary exists, the run never
    # removes it, and the readers show that summary, not the progress row. GET /progress answers
    # "completed", and the dashboard feed's status (like the watchlist router's) reads progress only
    # for a filing without a summary.
    from app.services.dashboard_feed_service import _summary_status

    filing_id = _seed()
    with SessionLocal() as db:
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage="summarizing"))
        db.commit()
    _at_the_fair_use_ceiling(pro_user.id, monkeypatch)

    with TestClient(app) as client:
        before = client.get(f"/api/summaries/filing/{filing_id}/progress").json()
        with stream_boundaries(patch_usage_limit=False), real_xbrl_lookup(AsyncMock(return_value=FRESH)):
            assert "temporarily paused new summary generation" in _regenerate(client, filing_id).text
        after = client.get(f"/api/summaries/filing/{filing_id}/progress").json()

    with SessionLocal() as db:
        assert db.query(SummaryGenerationProgress).filter_by(filing_id=filing_id).count() == 0  # it ran
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).one()
    assert before == after == {"stage": "completed", "elapsedSeconds": 0}
    assert _summary_status(summary, {"stage": "summarizing"}) == _summary_status(summary, None) \
        == {"summary_id": summary.id, "summary_status": "ready"}

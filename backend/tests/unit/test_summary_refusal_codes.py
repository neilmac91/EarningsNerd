"""The summary refusals Agent C owns carry their E31 code (docs/audit/contracts/error-codes.md §3).

- The summary exports' 401 answers ``auth_required`` beside its unchanged words. Their 403 (``plan_required``) is
  held by ``test_cached_filings_pool_lifetime.py``'s export case, and the regenerate 403 by
  ``test_summary_unready_refresh.py``.
- Admission's two account refusals, the free monthly limit and Pro's fair-use pause, carry their code on a reader's
  own stream (``test_summary_pipeline_anchors_admission.py`` holds the events whole). On a durable worker's run they
  stay code-less: that job belongs to the filing, ``summary_job_store.finish_job`` stores the event's code on it, and
  ``summary_jobs.observe_job`` replays it to every later observer of the failed job, other accounts among them, so
  one account's paywall would reach them. There the refusal is filed under ``summary_generation_failed``, as before.
- An account code outside ``STREAM_CODES`` is refused on either run, as ``sse_error`` refuses one.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.services import summary_job_store, summary_pipeline
from app.services.summary_stages import admission
from main import app

QUOTA = "You've used this month's 5 free summaries. Upgrade to Pro for unlimited summaries."
PAUSE = (
    "Your account has reached this month's limit for generating summaries, regenerations "
    "included. It resets next month. Contact support with any questions."
)


@pytest.mark.parametrize("export", ["pdf", "csv"])
def test_an_export_without_an_account_answers_auth_required(export):
    with TestClient(app) as client:
        response = client.get(f"/api/summaries/filing/1/export/{export}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required", "code": "auth_required"}


def _run(durable_lease):
    async def run_sync_db(fn, *args):
        return fn(*args)

    return SimpleNamespace(
        filing_id=7, user_id=3, request_evidence=None, admit_generation=None, rebuild_excerpt=False,
        filing_fields={
            "company_name": "Example Co", "company_cik": "1", "company_sic": None,
            "document_url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/x.htm",
            "filing_type": "10-K", "accession_number": "0000000001-26-000001", "cache_excerpt": None,
            "cache_updated_at": None, "cache_created_at": None,
        },
        current_user=SimpleNamespace(id=3), run_sync_db=run_sync_db, durable_lease=durable_lease,
        emit_funnel=lambda *args, **kwargs: None, telemetry_distinct_id="3", telemetry_entry_point=None,
    )


async def _events(run) -> list[dict]:
    return [event async for event in admission.admit(run)]


@pytest.mark.asyncio
@pytest.mark.parametrize(("unlimited", "message", "code"), [
    (False, QUOTA, "free_allowance_exhausted"),
    (True, PAUSE, "pro_fair_use_limit"),
])
async def test_an_account_refusal_is_coded_on_the_readers_stream_and_never_on_a_durable_job(
        monkeypatch, unlimited, message, code):
    verdict = (False, 5, 5, unlimited, None)
    monkeypatch.setattr(summary_pipeline, "_check_usage_and_plan", lambda *_: verdict)
    assert await _events(_run(durable_lease=None)) == [{"type": "error", "message": message, "code": code}]

    lease = SimpleNamespace(filing_id=7)
    monkeypatch.setattr(summary_job_store, "reserve_job_usage", lambda held: verdict if held is lease else pytest.fail())
    assert await _events(_run(durable_lease=lease)) == [{"type": "error", "message": message}]


@pytest.mark.parametrize("durable_lease", [None, SimpleNamespace(filing_id=7)])
def test_an_account_code_is_a_stream_code_on_either_run(durable_lease):
    # As sse_error refuses one: an HTTP-only code on a stream is a code the client ignores.
    with pytest.raises(ValueError, match="plan_required is not a stream code"):
        admission._account_code(_run(durable_lease), summary_pipeline.ErrorCode.PLAN_REQUIRED)

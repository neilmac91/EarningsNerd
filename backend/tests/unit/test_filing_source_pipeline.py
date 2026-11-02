"""Enabled source artifacts gate the real orchestrator and publish cache only with its winning result."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app import database
from app.models import FilingContentCache, FilingSourceBundle, FilingSourceExtraction, Summary
from app.services import filing_source_storage as storage, summary_generation_service, summary_pipeline as pipeline
from app.services.edgar import filing_source_capture as capture
from app.services.filing_source_types import FilingSourceError
from app.services.summary_stages import failure
from tests.support.filing_source_fixtures import LEGACY, PRIMARY, MemorySourceObjects, seed_source, source_metadata
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries


@pytest.fixture
def source(monkeypatch):
    reset_inflight()
    identity = seed_source()
    objects = MemorySourceObjects()
    monkeypatch.setattr(storage, 'BoundedFilingSourceStorage', lambda bucket: objects)
    monkeypatch.setattr(pipeline.settings, 'FILING_SOURCE_ARTIFACTS_ENABLED', True)
    monkeypatch.setattr(pipeline.settings, 'FILING_SOURCE_ARTIFACTS_BUCKET', 'private-bucket-sentinel')
    primary = AsyncMock(return_value=(PRIMARY, source_metadata(identity, 'primary.htm', PRIMARY)))
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', primary)
    yield identity, objects, primary
    reset_inflight()


async def drain(filing_id, **kwargs):
    return [event async for event in pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id='offline',
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False, **kwargs,
    )]


def cache_and_summary(filing_id):
    with database.SessionLocal() as db:
        cache = db.get(FilingContentCache, filing_id)
        summary = db.query(Summary).filter_by(filing_id=filing_id).first()
        return cache.critical_excerpt, cache.risk_source_text, summary.raw_summary if summary else None


@pytest.mark.asyncio
async def test_real_pipeline_commits_source_before_provider_and_atomically_replaces_legacy(source):
    identity, objects, primary = source
    observed = []
    async def provider(text, *args, **kwargs):
        assert text == PRIMARY.decode()
        assert LEGACY not in kwargs['filing_excerpt']
        assert 'Revenue $5.1 billion' in kwargs['filing_excerpt']
        # Actual DB read during model entry proves source commit and proves no
        # pre-promotion mutation of the served cache.
        with database.SessionLocal() as db:
            bundle = db.query(FilingSourceBundle).filter_by(identity_sha256=identity.sha256).one()
            extraction = db.query(FilingSourceExtraction).filter_by(bundle_id=bundle.id).one()
            observed.append((bundle.id, extraction.id))
        assert cache_and_summary(identity.filing_id) == (LEGACY, LEGACY, None)
        return deepcopy(CANONICAL_PAYLOAD)
    with stream_boundaries() as mock, patch.object(pipeline.openai_service, 'summarize_filing', AsyncMock(side_effect=provider)) as model, \
            patch.object(pipeline, 'get_or_cache_excerpt', summary_generation_service.get_or_cache_excerpt):
        events = await drain(identity.filing_id)
        assert events[-1]['type'] == 'complete', events
        mock.assert_not_awaited()
        model.assert_awaited_once()
    primary.assert_awaited_once()
    excerpt, risk, raw = cache_and_summary(identity.filing_id)
    assert 'Revenue $5.1 billion' in excerpt
    assert risk is None
    assert (raw['filing_source_provenance']['artifact']['bundle_id'], raw['filing_source_provenance']['artifact']['extraction_id']) == observed[0]
    # A completed read remains a read even when source storage is unavailable.
    with stream_boundaries() as model, patch.object(pipeline, 'load_or_capture_source', AsyncMock(side_effect=AssertionError('cached read backfilled artifacts'))):
        again = await drain(identity.filing_id)
        assert again[-1]['type'] == 'complete'
        model.assert_not_awaited()
    assert len(objects.puts) == 1


@pytest.mark.asyncio
async def test_no_excerpt_fallback_uses_verified_text_and_atomically_clears_incompatible_cache(source):
    identity, _, _ = source
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as model, patch.object(pipeline, 'get_or_cache_excerpt', lambda *a, **k: None):
        events = await drain(identity.filing_id)
    assert events[-1]['type'] == 'complete'
    assert model.await_args.args[0] == PRIMARY.decode()
    assert model.await_args.kwargs['filing_excerpt'] is None
    excerpt, risk, raw = cache_and_summary(identity.filing_id)
    assert excerpt is None and risk is None
    assert raw['filing_source_provenance']['artifact']['bundle_id']


@pytest.mark.asyncio
async def test_provider_failure_preserves_cache_and_retry_reuses_committed_source(source):
    identity, _, primary = source
    with stream_boundaries(payload={'status': 'error', 'message': 'offline failure'}) as model, \
            patch.object(pipeline, 'get_or_cache_excerpt', summary_generation_service.get_or_cache_excerpt):
        first = await drain(identity.filing_id)
    assert first[-1]['type'] == 'error'
    assert cache_and_summary(identity.filing_id) == (LEGACY, LEGACY, None)
    model.assert_awaited_once()
    primary.side_effect = AssertionError('retry re-fetched source')
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as model, \
            patch.object(pipeline, 'get_or_cache_excerpt', summary_generation_service.get_or_cache_excerpt):
        second = await drain(identity.filing_id)
    assert second[-1]['type'] == 'complete'
    primary.assert_awaited_once()
    assert model.await_args.args[0] == PRIMARY.decode()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['storage', 'commit', 'readback'])
async def test_preparation_failure_never_enters_provider_or_mutates_served_cache(source, monkeypatch, fault):
    identity, objects, _ = source
    async def failed(*a, **k):
        raise FilingSourceError('artifact_storage_unavailable', retryable=True)
    if fault == 'storage':
        monkeypatch.setattr(objects, 'put', failed)
    elif fault == 'commit':
        monkeypatch.setattr(capture.store, 'commit_bundle', lambda *a: (_ for _ in ()).throw(FilingSourceError('artifact_commit_unverified', retryable=True)))
    else:
        monkeypatch.setattr(capture.store, 'commit_extraction', lambda *a: (_ for _ in ()).throw(FilingSourceError('artifact_commit_unverified', retryable=True)))
    with stream_boundaries() as model:
        events = await drain(identity.filing_id)
    assert events[-1]['type'] == 'error'
    assert events[-1]['code'] == 'filing_source_unavailable'
    model.assert_not_awaited()
    assert cache_and_summary(identity.filing_id) == (LEGACY, LEGACY, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['text', 'identity', 'receipt'])
async def test_actual_generation_pre_task_barrier_rejects_unverified_inputs(source, monkeypatch, fault):
    identity, _, _ = source
    original = pipeline.fetch.fetch_document
    async def corrupt_after_fetch(run):
        async for event in original(run):
            yield event
        if fault == 'text':
            run.filing_text = 'unverified replacement'
        elif fault == 'identity':
            run.committed_source = replace(run.committed_source, bundle=replace(run.committed_source.bundle, identity=replace(identity, filing_id=identity.filing_id+1000)))
        else:
            run.committed_source = None
    monkeypatch.setattr(pipeline.fetch, 'fetch_document', corrupt_after_fetch)
    with stream_boundaries() as model:
        events = await drain(identity.filing_id)
    assert events[-1]['type'] == 'error'
    assert events[-1]['code'] == 'filing_source_unavailable'
    model.assert_not_awaited()
    assert cache_and_summary(identity.filing_id) == (LEGACY, LEGACY, None)


@pytest.mark.asyncio
async def test_run_snapshot_survives_setting_flip_during_source_capture(source, monkeypatch):
    identity, _, primary = source
    async def fetch(*a, **k):
        monkeypatch.setattr(pipeline.settings, 'FILING_SOURCE_ARTIFACTS_ENABLED', False)
        return PRIMARY, source_metadata(identity, 'primary.htm', PRIMARY)
    primary.side_effect = fetch
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as model:
        events = await drain(identity.filing_id)
    assert events[-1]['type'] == 'complete'
    model.assert_awaited_once()
    assert cache_and_summary(identity.filing_id)[2]['filing_source_provenance']['artifact']['bundle_id']


@pytest.mark.asyncio
async def test_disabled_mode_keeps_existing_path_and_uses_no_artifact_boundary(source, monkeypatch):
    identity, _, primary = source
    monkeypatch.setattr(pipeline.settings, 'FILING_SOURCE_ARTIFACTS_ENABLED', False)
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as model, patch.object(pipeline, 'load_or_capture_source', AsyncMock(side_effect=AssertionError('flag-off artifact call'))):
        events = await drain(identity.filing_id)
    assert events[-1]['type'] == 'complete'
    primary.assert_not_awaited()
    model.assert_awaited_once()
    assert 'filing_source_provenance' not in cache_and_summary(identity.filing_id)[2]


@pytest.mark.asyncio
async def test_keep_better_keeps_existing_summary_and_excerpt(source):
    identity, _, _ = source
    with database.SessionLocal() as db:
        db.add(Summary(filing_id=identity.filing_id, business_overview='Existing source-safe summary', raw_summary={'quality': {'tier': 'full'}, 'old': True}))
        db.commit()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)), \
            patch.object(pipeline, 'get_or_cache_excerpt', summary_generation_service.get_or_cache_excerpt), \
            patch.object(pipeline, 'assess_quality', return_value={'tier': 'partial', 'reasons': []}):
        await drain(identity.filing_id, force_regenerate=True)
    assert cache_and_summary(identity.filing_id) == (LEGACY, LEGACY, {'quality': {'tier': 'full'}, 'old': True})


def test_storage_429_is_never_classified_as_sec_429():
    request = httpx.Request('GET', 'https://private.example/secret')
    error = FilingSourceError('artifact_storage_unavailable', retryable=True)
    error.__cause__ = httpx.HTTPStatusError('secret body', request=request, response=httpx.Response(429, request=request))
    code, status, classification, delay = failure._source_failure_details(error)
    assert code == pipeline.ErrorCode.FILING_SOURCE_UNAVAILABLE
    assert status is None and delay is None and classification == 'artifact_storage_unavailable'
    assert failure._source_retryable(error, status) is True

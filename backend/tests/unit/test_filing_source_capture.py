"""Actual capture/commit/reuse gates; only SEC and object storage are offline fixtures."""
import asyncio
import hashlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import select

from app import database
from app.config import settings
from app.models import FilingSourceBundle, FilingSourceExtraction, FilingSourceMember
from app.services import filing_source_store as store, filing_source_storage as storage
from app.services.edgar import filing_source_capture as capture, eightk_extractor
from app.services.filing_source_types import FilingSourceError, FilingSourceIdentity, MAX_SOURCE_BYTES
from app.services.request_work import RequestWork
from tests.support.filing_source_fixtures import COVER, PRIMARY, RELEASE, MemorySourceObjects, seed_source, source_metadata


@pytest.fixture
def objects(monkeypatch):
    result = MemorySourceObjects()
    monkeypatch.setattr(storage, 'BoundedFilingSourceStorage', lambda bucket: result)
    monkeypatch.setattr(settings, 'FILING_SOURCE_ARTIFACTS_BUCKET', 'private-coordinate-canary')
    return result


def transport(monkeypatch, identity, body=PRIMARY, exhibits=None):
    exhibits = exhibits or {'release.htm': RELEASE}
    async def primary(cik, accession, filename, **kwargs):
        assert (cik, accession, filename) == (identity.cik, identity.accession, identity.primary_filename)
        assert kwargs['max_bytes'] == MAX_SOURCE_BYTES
        return body, source_metadata(identity, filename, body)
    async def exhibit(cik, accession, filename, **kwargs):
        assert (cik, accession) == (identity.cik, identity.accession)
        value = exhibits[filename]
        assert len(value) <= kwargs['max_bytes'] <= MAX_SOURCE_BYTES
        return value, source_metadata(identity, filename, value)
    first, attached = AsyncMock(side_effect=primary), AsyncMock(side_effect=exhibit)
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', first)
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_attachment_bytes', attached)
    return first, attached


async def load(identity):
    owner = RequestWork()
    try:
        return await capture.load_or_capture_source(identity, deadline=time.monotonic()+20, owner=owner)
    finally:
        await owner.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize('form,body', [('10-Q', PRIMARY), ('10-K/A', PRIMARY), ('8-K', COVER)])
async def test_capture_and_reuse_committed_identity_preserve_actual_old_grounding(monkeypatch, objects, form, body):
    identity = seed_source(form=form)
    first, attached = transport(monkeypatch, identity, body)
    if form == '8-K':
        legacy = await eightk_extractor.get_eightk_grounding(body.decode(), identity.url_for(identity.primary_filename), identity.cik, identity.accession)
        old_text = legacy.text
        attached.reset_mock()
    else:
        old_text = httpx.Response(200, headers={'content-type': 'text/html; charset=utf-8'}, content=body).text
    committed = await load(identity)
    assert committed.grounding_text == old_text
    assert committed.bundle.identity == identity
    committed.require_identity(identity, old_text)
    with database.SessionLocal() as db:
        assert db.get(FilingSourceBundle, committed.bundle.id) is not None
        assert db.get(FilingSourceExtraction, committed.extraction_id) is not None
    first.side_effect = AssertionError('retry must not contact SEC')
    attached.side_effect = AssertionError('retry must not contact SEC')
    reused = await load(identity)
    assert reused == committed
    assert len(objects.reads) == len(committed.bundle.members)
    first.assert_awaited_once()
    assert attached.await_count == (1 if form == '8-K' else 0)
    if form == '8-K':
        assert attached.await_args.kwargs['max_bytes'] == MAX_SOURCE_BYTES - len(body)
    serialized = json.dumps(committed.safe_provenance)
    assert 'private-coordinate-canary' not in serialized
    assert 'storage_generation' not in serialized and 'filing-source/v1/' not in serialized
    assert committed.bundle.members[0].sha256 == hashlib.sha256(body).hexdigest()
    assert committed.grounding_sha256 == hashlib.sha256(old_text.encode()).hexdigest()


@pytest.mark.asyncio
async def test_reextract_version_reuses_bytes_but_commits_new_extraction(monkeypatch, objects):
    identity = seed_source()
    primary, _ = transport(monkeypatch, identity)
    first = await load(identity)
    monkeypatch.setattr(capture, 'SOURCE_EXTRACTION_VERSION', 'grounding_v2')
    second = await load(identity)
    assert second.bundle.id == first.bundle.id
    assert second.extraction_id != first.extraction_id
    assert second.grounding_text == first.grounding_text
    primary.assert_awaited_once()
    with database.SessionLocal() as db:
        assert len(db.scalars(select(FilingSourceExtraction).where(FilingSourceExtraction.bundle_id == first.bundle.id)).all()) == 2


@pytest.mark.asyncio
async def test_incomplete_object_set_never_publishes_bundle(monkeypatch, objects):
    identity = seed_source(form='8-K')
    transport(monkeypatch, identity, COVER)
    original = objects.put
    async def fail_second(*args, **kwargs):
        if objects.puts:
            raise FilingSourceError('artifact_storage_unavailable', retryable=True)
        return await original(*args, **kwargs)
    monkeypatch.setattr(objects, 'put', fail_second)
    with pytest.raises(FilingSourceError, match='artifact_storage_unavailable'):
        await load(identity)
    assert len(objects.puts) == 1
    assert store.lookup_bundle(identity) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['object', 'metadata', 'extraction'])
async def test_corruption_fails_closed_before_releasing_receipt(monkeypatch, objects, fault):
    identity = seed_source()
    primary, _ = transport(monkeypatch, identity)
    committed = await load(identity)
    if fault == 'object':
        objects.bodies[(identity.sha256, committed.bundle.members[0].sha256)] = b'changed'
    else:
        with database.SessionLocal() as db:
            if fault == 'metadata':
                db.get(FilingSourceMember, (committed.bundle.id, 0)).content_type = 'text/plain'
            else:
                db.get(FilingSourceExtraction, committed.extraction_id).text_sha256 = '0'*64
            db.commit()
    with pytest.raises(FilingSourceError):
        await load(identity)
    primary.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_capture_winner_text_is_reloaded_not_candidate(monkeypatch, objects):
    identity = seed_source()
    transport(monkeypatch, identity)
    first = await load(identity)
    # Model an earlier miss that resumes after another caller committed.
    real_lookup = store.lookup_bundle
    count = 0
    def stale_miss(value):
        nonlocal count
        count += 1
        return None if count == 1 else real_lookup(value)
    monkeypatch.setattr(store, 'lookup_bundle', stale_miss)
    transport(monkeypatch, identity, PRIMARY.replace(b'5.1', b'8.9'))
    second = await load(identity)
    assert second == first
    assert '8.9' not in second.grounding_text
    assert objects.reads


@pytest.mark.asyncio
async def test_total_deadline_cancels_sec_wait_and_issues_no_receipt(monkeypatch, objects):
    identity = seed_source()
    entered, cancelled = asyncio.Event(), asyncio.Event()
    deadlines = []
    def recorded_timeout(seconds):
        owner = asyncio.timeout(seconds)
        deadlines.append((seconds, owner))
        return owner
    monkeypatch.setattr(capture, 'asyncio', SimpleNamespace(**{**vars(asyncio), 'timeout': recorded_timeout}))
    async def wait(*a, **k):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', wait)
    owner = RequestWork()
    task = asyncio.create_task(capture.load_or_capture_source(identity, deadline=time.monotonic()+30, owner=owner))
    try:
        # Initial SQL dispatch/lookup is setup, not the SEC cancellation under test.
        await asyncio.wait_for(entered.wait(), 10)
        assert len(deadlines) == 1 and 0 < deadlines[0][0] <= capture.SOURCE_STAGE_SECONDS
        deadlines[0][1].reschedule(asyncio.get_running_loop().time())
        with pytest.raises(FilingSourceError, match='artifact_storage_timeout'):
            await asyncio.wait_for(task, 10)
        assert deadlines[0][1].expired() and cancelled.is_set()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await owner.drain()
    assert objects.puts == []
    assert store.lookup_bundle(identity) is None


@pytest.mark.parametrize('field,value', [
    ('content_type', 'application/pdf'), ('content_type', 'text/html\nsecret'),
    ('content_encoding', 'gzip'), ('content_encoding', {}), ('representation', 'decoded_text'),
    ('requested_url', 'https://evil.test/'), ('final_url', 'https://evil.test/'),
    ('accession_number', '0'*18), ('cik', '1'), ('filename', '../primary.htm'),
    ('sha256', '0'*64), ('bytes', True), ('status_code', 429),
])
def test_source_metadata_rejects_wrong_identity_representation_and_transport(field, value):
    identity = FilingSourceIdentity(1, '872589', '000087258926000123', '10-Q', 'primary.htm')
    metadata = source_metadata(identity, 'primary.htm', PRIMARY)
    metadata[field] = value
    with pytest.raises(FilingSourceError, match='artifact_source_invalid'):
        capture._source_metadata(identity, 'primary.htm', PRIMARY, metadata)


@pytest.mark.parametrize('url', [
    'https://evil.test/primary.htm',
    'https://www.sec.gov/Archives/edgar/data/1/000087258926000123/primary.htm',
    'https://www.sec.gov/Archives/edgar/data/872589/000087258926000122/primary.htm',
    'https://www.sec.gov/Archives/edgar/data/872589/000087258926000123/primary.htm?x=1',
    'https://www.sec.gov/Archives/edgar/data/872589/000087258926000123/..%2fprimary.htm',
])
def test_identity_rejects_cross_filing_or_ambiguous_url(url):
    with pytest.raises(FilingSourceError, match='artifact_identity_invalid'):
        FilingSourceIdentity.from_filing(1, {'company_cik': '872589', 'accession_number': '0000872589-26-000123', 'filing_type': '10-Q', 'document_url': url})



@pytest.mark.asyncio
async def test_no_sql_checkout_is_held_across_source_or_object_io(monkeypatch, objects):
    from sqlalchemy import event
    identity = seed_source()
    primary, _ = transport(monkeypatch, identity)
    active = []
    def checkout(*args):
        active.append(True)
    def checkin(*args):
        active.pop()
    event.listen(database.engine, 'checkout', checkout)
    event.listen(database.engine, 'checkin', checkin)
    original_primary, original_put, original_read = primary.side_effect, objects.put, objects.read
    async def checked_primary(*a, **k):
        assert not active
        return await original_primary(*a, **k)
    async def checked_put(*a, **k):
        assert not active
        return await original_put(*a, **k)
    async def checked_read(*a, **k):
        assert not active
        return await original_read(*a, **k)
    primary.side_effect = checked_primary
    monkeypatch.setattr(objects, 'put', checked_put)
    monkeypatch.setattr(objects, 'read', checked_read)
    try:
        await load(identity)
        await load(identity)
        assert not active
    finally:
        event.remove(database.engine, 'checkout', checkout)
        event.remove(database.engine, 'checkin', checkin)


@pytest.mark.asyncio
async def test_aggregate_byte_cap_includes_primary_and_every_selected_member(monkeypatch, objects):
    identity = seed_source(form='8-K')
    body = COVER + b' ' * 100
    monkeypatch.setattr(capture, 'MAX_SOURCE_BYTES', len(body)+len(RELEASE)-1)
    primary = AsyncMock(return_value=(body, source_metadata(identity, 'primary.htm', body)))
    attachment = AsyncMock(return_value=(RELEASE, source_metadata(identity, 'release.htm', RELEASE)))
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', primary)
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_attachment_bytes', attachment)
    with pytest.raises(FilingSourceError, match='artifact_source_too_large'):
        await load(identity)
    assert attachment.await_args.kwargs['max_bytes'] == len(RELEASE)-1
    assert objects.puts == [] and store.lookup_bundle(identity) is None


@pytest.mark.asyncio
async def test_primary_charset_decoding_matches_legacy_httpx_text(monkeypatch, objects):
    identity = seed_source()
    body = b'<html><body><p>Revenue: \x801.2 billion.</p></body></html>'
    content_type = 'text/html; charset=windows-1252'
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', AsyncMock(return_value=(body, source_metadata(identity, 'primary.htm', body, content_type))))
    result = await load(identity)
    expected = httpx.Response(200, headers={'content-type': content_type}, content=body).text
    assert result.grounding_text == expected and '€1.2 billion' in result.grounding_text
    assert result.bundle.members[0].sha256 == hashlib.sha256(body).hexdigest()
    assert result.grounding_sha256 == hashlib.sha256(expected.encode()).hexdigest()


@pytest.mark.asyncio
@pytest.mark.parametrize('bucket', ['', 'configured-feedback-bucket'])
async def test_missing_or_feedback_bucket_refused_before_any_artifact_io(monkeypatch, bucket):
    identity = seed_source()
    monkeypatch.setattr(settings, 'FILING_SOURCE_ARTIFACTS_ENABLED', True)
    monkeypatch.setattr(settings, 'FILING_SOURCE_ARTIFACTS_BUCKET', bucket)
    monkeypatch.setattr(settings, 'FEEDBACK_MEDIA_BUCKET', 'configured-feedback-bucket')
    object_boundary = Mock(side_effect=AssertionError('configuration refusal must precede adapter construction'))
    database_boundary = Mock(side_effect=AssertionError('configuration refusal must precede metadata lookup'))
    sec_boundary = AsyncMock(side_effect=AssertionError('configuration refusal must precede SEC retrieval'))
    monkeypatch.setattr(storage, 'BoundedFilingSourceStorage', object_boundary)
    monkeypatch.setattr(store, 'lookup_bundle', database_boundary)
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_primary_bytes', sec_boundary)
    monkeypatch.setattr(capture.sec_edgar_service, 'get_filing_attachment_bytes', sec_boundary)
    with pytest.raises(FilingSourceError, match='^artifact_not_configured$'):
        await load(identity)
    object_boundary.assert_not_called()
    database_boundary.assert_not_called()
    sec_boundary.assert_not_awaited()

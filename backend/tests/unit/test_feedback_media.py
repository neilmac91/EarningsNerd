"""Private feedback ingress and publication against real SQL, with only image/provider I/O faked."""
from __future__ import annotations

import hashlib
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.models import User
from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.routers import feedback as router
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackCreate
from app.services import feedback_submission_service as service
from app.services.feedback_image_service import NormalizedFeedbackImage
from app.services.feedback_storage_service import FeedbackStorageError
from app.services.user_account_service import delete_user
from app.utils.datetimes import utcnow
from main import app


@pytest.fixture
def media(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'feedback.sqlite'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        db.add_all([User(id=1, email="owner@example.test", is_active=True),
                    User(id=2, email="other@example.test", is_active=True),
                    User(id=3, email="admin@example.test", is_active=True, is_admin=True)])
        db.commit()
    actor = SimpleNamespace(id=1, email="owner@example.test", is_admin=False)
    storage = {}
    uploads = []
    notifications = []

    def get_session():
        with sessions() as db:
            yield db

    async def normalize(data):
        assert engine.pool.checkedout() == 0, "No SQL connection belongs to image I/O"
        return NormalizedFeedbackImage(data, 2, 2, hashlib.sha256(data).hexdigest())

    async def store(bucket, operation, key, *, data=None, generation=None):
        assert engine.pool.checkedout() == 0, "No SQL connection belongs to provider I/O"
        if operation == "upload":
            with sessions() as db:
                manifest = db.query(FeedbackAttachment).filter_by(object_key=key).one()
                assert manifest.state == "pending", "Durable key must precede provider write"
                assert manifest.object_generation is None
            uploads.append(key)
            storage[key] = data
            return "1"
        assert operation == "download" and generation == "1"
        return storage[key]

    async def notify(*args):
        assert engine.pool.checkedout() == 0
        notifications.append(args)

    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_ENABLED", True)
    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_BUCKET", "private-test-bucket")
    monkeypatch.setattr(router, "normalize_feedback_image", normalize)
    monkeypatch.setattr(router, "run_feedback_storage_operation", store)
    monkeypatch.setattr(router, "_notify_admin", notify)
    monkeypatch.setattr(router, "capture_event", lambda *args: None)
    router.FEEDBACK_LIMITER._hits.clear()
    router.MEDIA_INGRESS_LIMITER._hits.clear()
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sessions=sessions, actor=actor, storage=storage,
                              uploads=uploads, notify=notifications, store=store, engine=engine)
    app.dependency_overrides = original_overrides
    engine.dispose()


def headers(key=None, owner=1):
    return {"Origin": settings.CORS_ORIGINS[0], "X-Requested-With": "XMLHttpRequest",
            "X-Feedback-User-Id": str(owner), "Idempotency-Key": key or str(uuid4())}


def send(media, *, key=None, images=(b"first screenshot",), message="This chart clipped the filing text"):
    return media.client.post("/api/feedback/with-attachments", headers=headers(key),
                             data={"type": "bug", "message": message, "page_url": "/company/AAPL"},
                             files=[("files", ("private-name.png", data, "image/png")) for data in images])


def test_complete_retry_matches_actual_payload_and_private_reads(media):
    key = str(uuid4())
    first = send(media, key=key, images=(b"first", b"second"))
    assert first.status_code == 201, first.text
    again = send(media, key=key, images=(b"first", b"second"))
    assert again.status_code == 200 and again.json() == first.json()
    assert len(media.uploads) == 2 and len(media.notify) == 1
    assert send(media, key=key, images=(b"changed", b"second")).status_code == 409
    receipt = media.client.get(f"/api/feedback/submissions/{key}").json()
    assert receipt["state"] == "submitted" and receipt["feedback"] == first.json()
    with media.sessions() as db:
        attachments = db.query(FeedbackAttachment).order_by(FeedbackAttachment.position).all()
        ids = [row.id for row in attachments]
        assert [row.state for row in attachments] == ["available", "available"]
        assert db.query(Feedback).count() == 1
    loaded = media.client.get(f"/api/feedback/attachments/{ids[0]}")
    assert loaded.content == b"first"
    assert loaded.headers["Cache-Control"] == "private, no-store"
    assert loaded.headers["X-Content-Type-Options"] == "nosniff"
    media.actor.id = 2
    assert media.client.get(f"/api/feedback/attachments/{ids[0]}").status_code == 404
    assert media.client.get(f"/api/feedback/submissions/{key}").status_code == 404
    media.actor.id = 3
    assert media.client.get(f"/api/feedback/attachments/{ids[0]}").content == b"first"


def test_provider_failure_has_no_partial_feedback_and_retry_uses_distinct_keys(media, monkeypatch):
    key = str(uuid4())
    async def uncertain_write(bucket, operation, object_key, **kwargs):
        await media.store(bucket, operation, object_key, **kwargs)
        raise FeedbackStorageError()  # The provider wrote, but its generation receipt was lost.
    monkeypatch.setattr(router, "run_feedback_storage_operation", uncertain_write)
    failed = send(media, key=key, images=(b"first", b"second"))
    assert failed.status_code == 503
    assert media.client.get(f"/api/feedback/submissions/{key}").json()["state"] == "retryable"
    with media.sessions() as db:
        assert db.query(Feedback).count() == 0
        orphan_keys = {row.object_key for row in db.query(FeedbackAttachment)}
        assert len(orphan_keys) == 2
        assert all(row.object_generation is None for row in db.query(FeedbackAttachment))
    monkeypatch.setattr(router, "run_feedback_storage_operation", media.store)
    assert send(media, key=key, images=(b"first", b"second")).status_code == 201
    with media.sessions() as db:
        published = db.query(FeedbackAttachment).filter_by(state="available").all()
        assert not orphan_keys.intersection(row.object_key for row in published)
        assert db.query(Feedback).count() == 1
        assert db.query(FeedbackSubmission).one().attempt_count == 2


@pytest.mark.parametrize("change", ("owner_deleted", "admin_revoked", "admin_deleted", "expired"))
def test_download_reauthorizes_after_storage_io(media, monkeypatch, change):
    assert send(media).status_code == 201
    with media.sessions() as db:
        attachment_id = db.query(FeedbackAttachment.id).scalar()
    if change.startswith("admin"):
        media.actor.id = 3
    async def read_then_change(bucket, operation, key, **kwargs):
        value = await media.store(bucket, operation, key, **kwargs)
        with media.sessions() as db:
            if change == "owner_deleted":
                delete_user(db, 1)
            elif change == "admin_deleted":
                delete_user(db, 3)
            elif change == "admin_revoked":
                db.get(User, 3).is_admin = False
                db.commit()
            else:
                db.get(FeedbackAttachment, attachment_id).expires_at = utcnow() - timedelta(seconds=1)
                db.commit()
        return value
    monkeypatch.setattr(router, "run_feedback_storage_operation", read_then_change)
    result = media.client.get(f"/api/feedback/attachments/{attachment_id}")
    assert result.status_code in (404, 410)
    assert result.content != b"first screenshot"


def test_account_deleted_during_upload_cannot_publish(media, monkeypatch):
    async def upload_then_delete(bucket, operation, key, **kwargs):
        result = await media.store(bucket, operation, key, **kwargs)
        with media.sessions() as db:
            delete_user(db, 1)
        return result
    monkeypatch.setattr(router, "run_feedback_storage_operation", upload_then_delete)
    result = send(media)
    assert result.status_code == 401
    with media.sessions() as db:
        assert db.query(Feedback).count() == 0
        row = db.query(FeedbackAttachment).one()
        assert row.owner_id is None and row.state == "purge_pending" and row.object_key


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("account", "origin", "csrf", "disabled", "slots", "quota"))
async def test_admission_rejects_before_receiving_multipart_bytes(media, monkeypatch, failure):
    request_headers = headers()
    expected = 403
    if failure == "account":
        request_headers["X-Feedback-User-Id"] = "2"
        expected = 409
    elif failure == "origin":
        request_headers["Origin"] = "https://untrusted.example"
    elif failure == "csrf":
        request_headers.pop("X-Requested-With")
    elif failure == "disabled":
        monkeypatch.setattr(settings, "FEEDBACK_MEDIA_ENABLED", False)
        expected = 503
    elif failure == "slots":
        monkeypatch.setattr(router, "_UPLOAD_SLOTS", SimpleNamespace(acquire=lambda **kwargs: False))
        expected = 503
    elif failure == "quota":
        monkeypatch.setattr(router, "MEDIA_INGRESS_LIMITER", router.RateLimiter(0, 3600))
        expected = 429
    received = []
    async def body():
        received.append(True)
        yield b"private-image-body"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post("/api/feedback/with-attachments", headers=request_headers, content=body())
    assert result.status_code == expected, result.text
    assert received == []


@pytest.mark.parametrize("images", ((b"x" * (router.MAX_FILE_BYTES + 1),), (b"1", b"2", b"3", b"4")))
def test_parser_bounds_before_decoder_or_storage(media, images):
    response = send(media, images=images)
    assert response.status_code == 413
    assert media.uploads == []
    with media.sessions() as db:
        assert db.query(FeedbackSubmission).count() == 0


def test_malformed_multipart_is_validation_failure(media):
    request_headers = {**headers(), "Content-Type": "multipart/form-data; boundary=valid-boundary"}
    response = media.client.post("/api/feedback/with-attachments", headers=request_headers,
                                 content=b"--wrong-boundary\r\nprivate text")
    assert response.status_code == 413 and media.uploads == []


@pytest.mark.parametrize("excess", ("headers", "field_bytes", "field_count"))
def test_multipart_metadata_is_bounded_before_publication(media, excess):
    request_headers = {**headers(), "Content-Type": "multipart/form-data; boundary=limited"}
    if excess == "headers":
        body = (b'--limited\r\nContent-Disposition: form-data; name="files"; filename="'
                + b"x" * 4096 + b'.png"\r\nContent-Type: image/png\r\n\r\nx\r\n--limited--\r\n')
    elif excess == "field_bytes":
        body = (b'--limited\r\nContent-Disposition: form-data; name="message"\r\n\r\n'
                + b"x" * 16001 + b'\r\n--limited--\r\n')
    else:
        body = b"".join(b'--limited\r\nContent-Disposition: form-data; name="' + name
                        + b'"\r\n\r\nvalue\r\n' for name in (b"type", b"message", b"page_url", b"extra"))
        body += b"--limited--\r\n"
    response = media.client.post("/api/feedback/with-attachments", headers=request_headers, content=body)
    assert response.status_code == 413 and media.uploads == []
    with media.sessions() as db:
        assert db.query(FeedbackSubmission).count() == 0


@pytest.mark.asyncio
async def test_actual_body_budget_applies_without_content_length(media, monkeypatch):
    request_headers = headers()
    request_headers["Content-Type"] = "multipart/form-data; boundary=body"
    decoded = []
    normalize = router.normalize_feedback_image

    async def observe_normalization(data):
        decoded.append(True)
        return await normalize(data)

    monkeypatch.setattr(router, "normalize_feedback_image", observe_normalization)

    async def body():
        # This is a valid complete form: without the aggregate byte limit, the parser
        # ignores the trailing chunks and would publish it. Each chunk alone is within
        # budget, so the witness also requires accumulation across received chunks.
        yield (b'--body\r\nContent-Disposition: form-data; name="message"\r\n\r\nA useful description\r\n'
               b'--body\r\nContent-Disposition: form-data; name="files"; filename="private.png"\r\n'
               b'Content-Type: image/png\r\n\r\nx\r\n--body--\r\n')
        yield b"x" * (router.MAX_BODY_BYTES // 2)
        yield b"x" * (router.MAX_BODY_BYTES // 2)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/feedback/with-attachments", headers=request_headers, content=body())
    assert response.status_code == 413 and media.uploads == [] and decoded == []
    with media.sessions() as db:
        assert db.query(FeedbackSubmission).count() == 0


def test_sql_failure_does_not_echo_private_values_to_response_logs_or_sentry(media, monkeypatch, caplog):
    import main
    import sentry_sdk

    marker = "Private brokerage note: https://private.example/portfolio"
    def database_error(*args):
        raise RuntimeError(marker)
    monkeypatch.setattr(service, "persist_legacy_feedback", database_error)
    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda *args: pytest.fail("Private exception reached Sentry"))
    monkeypatch.setattr(main.settings, "ENVIRONMENT", "development")
    # Catch-all handlers send a safe response even in development; the real server does not
    # re-raise the exception into a caller as TestClient's default debugging behavior does.
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.post("/api/feedback/", json={"message": marker})
    assert result.status_code == 500
    assert marker not in result.text and marker not in caplog.text


def test_expired_lease_is_read_only_retryable_and_stale_attempt_cannot_publish(media, monkeypatch):
    payload = FeedbackCreate(message="A useful description")
    key = str(uuid4())
    fingerprint = service.payload_fingerprint(payload, [])
    with media.sessions() as db:
        first = service.claim_submission(db, 1, key, fingerprint)
        row = db.get(FeedbackSubmission, first.submission_id)
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        before = row.updated_at
        assert service.read_receipt(db, 1, key).state == "retryable"
        assert db.get(FeedbackSubmission, first.submission_id).updated_at == before
        db.close()
        # Expiry fences the still-current worker even before another request replaces its token.
        with pytest.raises(service.FeedbackSubmissionError, match="stale_attempt"):
            service.publish_submission(db, 1, first, payload, "hashed", {}, 180)
        db.rollback()
        assert db.query(Feedback).count() == 0
        db.close()
        second = service.claim_submission(db, 1, key, fingerprint)
        assert second.attempt_token != first.attempt_token
        with pytest.raises(service.FeedbackSubmissionError, match="stale_attempt"):
            service.publish_submission(db, 1, first, payload, "hashed", {}, 180)
        db.rollback()
        service.fail_attempt(db, 1, first)
        db.close()
        saved = service.publish_submission(db, 1, second, payload, "hashed", {}, 180)
        assert service.read_receipt(db, 1, key).feedback.id == saved.id


def test_durable_quota_and_attempt_caps_do_not_charge_identical_replays(media, monkeypatch):
    monkeypatch.setattr(service, "MAX_SUBMISSIONS_PER_HOUR", 1)
    monkeypatch.setattr(service, "MAX_ATTEMPTS", 2)
    key = str(uuid4())
    assert send(media, key=key).status_code == 201
    assert send(media).status_code == 429
    assert send(media, key=key).status_code == 200
    with media.sessions() as db:
        assert db.query(FeedbackSubmission).one().attempt_count == 1
    # A second owner has an independent allowance; failures consume attempts, not new rows.
    payload = FeedbackCreate(message="Another account's report")
    with media.sessions() as db:
        claim = service.claim_submission(db, 2, key, service.payload_fingerprint(payload, []))
        service.fail_attempt(db, 2, claim)
        db.close()
        claim = service.claim_submission(db, 2, key, service.payload_fingerprint(payload, []))
        service.fail_attempt(db, 2, claim)
        db.close()
        with pytest.raises(service.FeedbackSubmissionError, match="retry_limit"):
            service.claim_submission(db, 2, key, service.payload_fingerprint(payload, []))


def test_legacy_json_and_keyed_json_share_receipts_without_changing_legacy_contract(media):
    payload = {"message": "Useful text feedback"}
    assert media.client.post("/api/feedback/", json=payload).status_code == 201
    key = str(uuid4())
    first = media.client.post("/api/feedback/", json=payload, headers=headers(key))
    again = media.client.post("/api/feedback/", json=payload, headers=headers(key))
    assert first.status_code == 201 and again.status_code == 200
    assert first.json() == again.json()
    assert media.client.get(f"/api/feedback/submissions/{key}").json()["state"] == "submitted"


def test_disable_uploads_preserves_private_reads_and_capabilities(media, monkeypatch):
    assert send(media).status_code == 201
    with media.sessions() as db:
        attachment_id = db.query(FeedbackAttachment.id).scalar()
    monkeypatch.setattr(settings, "FEEDBACK_MEDIA_ENABLED", False)
    assert media.client.get("/api/feedback/capabilities").json()["attachments_enabled"] is False
    assert send(media).status_code == 503
    assert media.client.get(f"/api/feedback/attachments/{attachment_id}").status_code == 200


@pytest.mark.asyncio
async def test_request_deadline_closes_partial_multipart_files(media, monkeypatch):
    import asyncio
    import starlette.formparsers

    from contextlib import asynccontextmanager

    real_timeout = asyncio.timeout
    real_file = starlette.formparsers.SpooledTemporaryFile
    temporary_files = []
    body_waiting = asyncio.Event()

    def track_file(*args, **kwargs):
        result = real_file(*args, **kwargs)
        temporary_files.append(result)
        return result

    monkeypatch.setattr(starlette.formparsers, 'SpooledTemporaryFile', track_file)
    @asynccontextmanager
    async def expire_when_body_is_waiting(seconds):
        assert seconds == 55
        async with real_timeout(None) as deadline:
            async def expire():
                await body_waiting.wait()
                deadline.reschedule(asyncio.get_running_loop().time())
            expiry = asyncio.create_task(expire())
            try:
                yield
            finally:
                expiry.cancel()
                await asyncio.gather(expiry, return_exceptions=True)

    monkeypatch.setattr(router.asyncio, 'timeout', expire_when_body_is_waiting)
    request_headers = {**headers(), 'Content-Type': 'multipart/form-data; boundary=feedback'}

    async def body():
        yield (b'--feedback\r\nContent-Disposition: form-data; name="files"; filename="private.png"\r\n'
               b'Content-Type: image/png\r\n\r\npartial-image-bytes')
        body_waiting.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        async with real_timeout(5):
            response = await client.post('/api/feedback/with-attachments', headers=request_headers, content=body())
    assert body_waiting.is_set() and temporary_files
    assert response.status_code == 504, response.text
    assert all(file.closed for file in temporary_files)
    assert media.uploads == []
    # Both permits are available for subsequent requests after an interrupted upload.
    assert router._UPLOAD_SLOTS.acquire(blocking=False)
    assert router._UPLOAD_SLOTS.acquire(blocking=False)
    router._UPLOAD_SLOTS.release()
    router._UPLOAD_SLOTS.release()
    with media.sessions() as db:
        assert db.query(FeedbackSubmission).count() == 0


@pytest.mark.asyncio
async def test_cancelled_provider_is_settled_before_attempt_becomes_retryable(media, monkeypatch):
    import asyncio

    entered = asyncio.Event()
    settled = asyncio.Event()
    key = str(uuid4())
    real_fail_attempt = service.fail_attempt
    failures = []

    async def provider(bucket, operation, object_key, **kwargs):
        await media.store(bucket, operation, object_key, **kwargs)
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            settled.set()

    def fail_attempt(*args):
        assert settled.is_set(), 'Cleanup must not race a still-owned write'
        failures.append(True)
        return real_fail_attempt(*args)

    monkeypatch.setattr(router, 'run_feedback_storage_operation', provider)
    monkeypatch.setattr(service, 'fail_attempt', fail_attempt)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        sending = asyncio.create_task(client.post('/api/feedback/with-attachments', headers=headers(key),
                                                   data={'message': 'A useful note'},
                                                   files=[('files', ('private.png', b'image', 'image/png'))]))
        await asyncio.wait_for(entered.wait(), timeout=5)
        sending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await sending
    assert settled.is_set() and failures
    with media.sessions() as db:
        assert db.query(Feedback).count() == 0
        assert db.query(FeedbackSubmission).one().state == 'retryable'
        manifest = db.query(FeedbackAttachment).one()
        assert manifest.state == 'purge_pending' and manifest.object_key in media.storage


def test_lost_commit_response_recovers_original_receipt_without_duplicate(media, monkeypatch):
    real_publish = service.publish_submission
    key = str(uuid4())

    def publish_then_disconnect(*args):
        real_publish(*args)
        raise RuntimeError('Synthetic response loss after commit')

    monkeypatch.setattr(service, 'publish_submission', publish_then_disconnect)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post('/api/feedback/with-attachments', headers=headers(key),
                               data={'message': 'A useful note'},
                               files=[('files', ('private.png', b'image', 'image/png'))])
    assert response.status_code == 500
    receipt = media.client.get(f'/api/feedback/submissions/{key}')
    assert receipt.status_code == 200 and receipt.json()['state'] == 'submitted'
    monkeypatch.setattr(service, 'publish_submission', real_publish)
    replay = media.client.post('/api/feedback/with-attachments', headers=headers(key),
                               data={'message': 'A useful note'},
                               files=[('files', ('private.png', b'image', 'image/png'))])
    assert replay.status_code == 200 and replay.json() == receipt.json()['feedback']
    assert len(media.uploads) == 1
    with media.sessions() as db:
        assert db.query(Feedback).count() == 1


@pytest.mark.asyncio
async def test_repeated_cancellation_does_not_reuse_a_session_while_publication_runs(media, monkeypatch):
    import asyncio
    import threading
    from starlette.requests import Request
    from starlette.responses import Response
    from app.services.request_work import RequestWork

    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    draining = asyncio.Event()
    drain_returned = asyncio.Event()
    release = threading.Event()
    finished = threading.Event()
    original_publish = service.publish_submission
    original_drain = RequestWork.drain
    original_fail = service.fail_attempt
    cleanup_after_worker = []

    def held_publication(db, *args):
        db.query(User.id).filter(User.id == 1).one()
        loop.call_soon_threadsafe(started.set)
        try:
            assert release.wait(5)
            return original_publish(db, *args)
        finally:
            finished.set()

    async def observed_drain(work):
        draining.set()
        try:
            await original_drain(work)
        finally:
            drain_returned.set()

    def observed_failure(*args):
        cleanup_after_worker.append(finished.is_set())
        return original_fail(*args)

    monkeypatch.setattr(service, 'publish_submission', held_publication)
    monkeypatch.setattr(service, 'fail_attempt', observed_failure)
    monkeypatch.setattr(RequestWork, 'drain', observed_drain)
    outgoing = httpx.Request('POST', 'http://test/api/feedback/with-attachments', headers=headers(),
                             data={'message': 'A useful note'},
                             files=[('files', ('private.png', b'image', 'image/png'))])
    body = outgoing.read()

    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}

    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/feedback/with-attachments',
                       'headers': [(name.lower(), value) for name, value in outgoing.headers.raw], 'scheme': 'http', 'client': ('127.0.0.1', 1),
                       'server': ('test', 80), 'query_string': b''}, receive)
    db = media.sessions()
    sending = asyncio.create_task(router.submit_feedback_with_attachments(request, Response(), media.actor, db))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        sending.cancel()
        await asyncio.wait_for(draining.wait(), timeout=5)
        sending.cancel()
        # Drain's gather cancellation runs through a few event-loop callbacks. No worker
        # release or elapsed-time assertion is used to make the race pass.
        for _ in range(5):
            await asyncio.sleep(0)
        assert not drain_returned.is_set(), 'The SQL owner was abandoned while its thread still ran'
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await sending
        db.close()
    assert finished.is_set() and cleanup_after_worker == [True]

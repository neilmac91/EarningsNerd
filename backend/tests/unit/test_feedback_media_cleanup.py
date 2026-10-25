"""Screenshot manifests outlive owners, retry failed deletes, and release SQL before storage."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, SessionLocal
from app.models import User
from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.services import feedback_media_cleanup_service as cleanup
from app.services.feedback_storage_service import FeedbackStorageError, make_feedback_object_key
from app.services.user_account_service import delete_user
from app.services.user_data_export_service import build_user_data_export
from app.utils.datetimes import ensure_utc


NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


@pytest.fixture
def database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(**{**SessionLocal.kw, "bind": engine})
    active = {"connections": 0}
    @event.listens_for(engine, "checkout")
    def checked_out(*_):
        active["connections"] += 1
    @event.listens_for(engine, "checkin")
    def checked_in(*_):
        active["connections"] -= 1
    yield SimpleNamespace(factory=factory, active=active)
    engine.dispose()


def _seed(database, *, due=NOW, state="available", owner_id=None):
    with database.factory() as db:
        if owner_id is None:
            owner = User(email=f"media-{uuid4().hex}@example.com")
            db.add(owner)
            db.flush()
            owner_id = owner.id
        report = None
        if state == "available":
            report = Feedback(user_id=owner_id, message="A useful report", created_at=NOW)
            db.add(report)
            db.flush()
        submission_id, attempt, attachment_id = (str(uuid4()) for _ in range(3))
        submission = FeedbackSubmission(
            id=submission_id, owner_id=owner_id, submission_key=str(uuid4()), fingerprint="a" * 64,
            state="submitted" if report else "processing", attempt_token=attempt,
            lease_expires_at=NOW + timedelta(seconds=120), feedback_id=report.id if report else None,
            created_at=NOW - timedelta(hours=25), updated_at=NOW,
        )
        db.add(submission)
        db.flush()
        attachment = FeedbackAttachment(
            id=attachment_id, submission_id=submission_id, attempt_token=attempt, owner_id=owner_id,
            feedback_id=report.id if report else None,
            object_key=make_feedback_object_key(attempt, attachment_id), object_generation="17",
            checksum="b" * 64, content_type="image/png", width=20, height=10, byte_count=100,
            state=state, created_at=NOW - timedelta(hours=25), expires_at=due if report else None,
            deletion_due_at=due,
        )
        db.add(attachment)
        db.commit()
        return SimpleNamespace(id=attachment_id, owner_id=owner_id, submission_id=submission_id)


def test_cleanup_retries_failure_without_losing_keys_and_never_holds_sql_during_storage(database):
    expired = _seed(database)
    orphan = _seed(database, state="pending")
    live = _seed(database, due=NOW + timedelta(days=1))
    calls = []
    class Storage:
        fail = True
        def delete(self, key, generation):
            assert database.active["connections"] == 0
            calls.append((key, generation))
            if self.fail and orphan.id.replace("-", "") in key:
                raise FeedbackStorageError("generation_conflict")
    storage = Storage()
    stats = cleanup.run_feedback_media_cleanup(database.factory, storage, now=NOW)
    assert stats == {"dry_run": False, "eligible": 2, "deleted": 1, "errors": 1, "overdue": 0, "pending_verification": 0}
    with database.factory() as db:
        assert db.get(FeedbackAttachment, expired.id).state == "deleted"
        failed = db.get(FeedbackAttachment, orphan.id)
        assert failed.state == "purge_pending" and failed.object_key and failed.object_generation == "17"
        assert failed.last_cleanup_error == "generation_conflict" and failed.cleanup_attempts == 1
        assert db.get(FeedbackAttachment, live.id).state == "available"
    storage.fail = False
    assert cleanup.run_feedback_media_cleanup(database.factory, storage, now=NOW + timedelta(hours=1))["deleted"] == 1
    assert len(calls) == 3
    with database.factory() as db:
        assert db.get(FeedbackAttachment, orphan.id).cleanup_attempts == 2


def test_dry_run_does_not_claim_or_contact_storage_and_reports_overdue(database):
    old = _seed(database, due=NOW - timedelta(hours=25))
    class NoStorage:
        def delete(self, *_):
            pytest.fail("dry run contacted object storage")
    stats = cleanup.run_feedback_media_cleanup(database.factory, NoStorage(), now=NOW, dry_run=True)
    assert stats == {"dry_run": True, "eligible": 1, "deleted": 0, "errors": 0, "overdue": 1, "pending_verification": 0}
    with database.factory() as db:
        row = db.get(FeedbackAttachment, old.id)
        assert row.cleanup_attempts == 0 and row.last_cleanup_attempt_at is None and row.state == "available"


def test_account_deletion_revokes_media_and_preserves_pending_upload_cleanup_deadline(database, monkeypatch):
    available = _seed(database, due=NOW + timedelta(days=180))
    pending = _seed(database, state="pending", owner_id=available.owner_id)
    with database.factory() as db:
        db.get(FeedbackAttachment, pending.id).created_at = NOW
        db.commit()
    monkeypatch.setattr(cleanup, "utcnow", lambda: NOW)
    with database.factory() as db:
        delete_user(db, available.owner_id)
    with database.factory() as db:
        assert db.get(User, available.owner_id) is None
        for seeded in (available, pending):
            row = db.get(FeedbackAttachment, seeded.id)
            assert row.owner_id is None and row.state == "purge_pending" and row.object_key
            submission = db.get(FeedbackSubmission, seeded.submission_id)
            assert submission.owner_id is None and submission.state == "retryable"
        assert ensure_utc(db.get(FeedbackAttachment, available.id).deletion_due_at) == NOW
        assert ensure_utc(db.get(FeedbackAttachment, pending.id).deletion_due_at) == NOW + timedelta(hours=24)
        assert db.query(Feedback).one().user_id is None


def test_overlapping_cleanup_claim_and_stale_ack_cannot_overwrite_newer_attempt(database):
    seeded = _seed(database)
    first = cleanup._claim(database.factory, NOW)
    assert first is not None
    assert cleanup._claim(database.factory, NOW) is None
    newer = cleanup._claim(database.factory, NOW + cleanup.CLAIM_DURATION)
    assert newer is not None and newer.attempt == first.attempt + 1
    cleanup._acknowledge(database.factory, first, NOW, "storage_error")
    with database.factory() as db:
        assert db.get(FeedbackAttachment, seeded.id).last_cleanup_error is None
    cleanup._acknowledge(database.factory, newer, NOW, None)
    cleanup._acknowledge(database.factory, first, NOW, "storage_error")
    with database.factory() as db:
        assert db.get(FeedbackAttachment, seeded.id).state == "deleted"
        assert db.get(FeedbackAttachment, seeded.id).last_cleanup_error is None


def test_export_is_owner_scoped_media_manifest_without_private_storage_identifiers(database, monkeypatch):
    live = _seed(database, due=NOW + timedelta(days=1))
    expired = _seed(database, due=NOW - timedelta(seconds=1), owner_id=live.owner_id)
    other = _seed(database, due=NOW + timedelta(days=1))
    monkeypatch.setattr("app.services.user_data_export_service.utcnow", lambda: NOW)
    with database.factory() as db:
        result = build_user_data_export(db, db.get(User, live.owner_id))["feedback"]
    manifests = [attachment for report in result for attachment in report["attachments"]]
    assert {attachment["id"] for attachment in manifests} == {live.id, expired.id}
    assert all(attachment["id"] != other.id for attachment in manifests)
    by_id = {attachment["id"]: attachment for attachment in manifests}
    assert by_id[live.id]["download_path"] == f"/api/feedback/attachments/{live.id}"
    assert by_id[expired.id]["status"] == "expired" and by_id[expired.id]["download_path"] is None
    assert all(not ({"object_key", "object_generation", "attempt_token"} & attachment.keys()) for attachment in manifests)


@pytest.mark.parametrize("fail_delete", [False, True])
def test_storage_probe_persists_ownerless_manifest_before_io_and_keeps_failed_cleanup(database, fail_delete):
    class Storage:
        data = None
        def upload(self, key, data):
            assert database.active["connections"] == 0
            with database.factory() as db:
                row = db.query(FeedbackAttachment).filter_by(object_key=key).one()
                assert row.owner_id is None and row.state == "purge_pending"
                assert row.object_generation is None
                assert db.query(Feedback).count() == 0
            self.data = data
            assert data.startswith(b"\x89PNG\r\n\x1a\n")
            return "23"
        def download(self, key, generation):
            assert database.active["connections"] == 0
            assert generation == "23"
            return self.data
        def delete(self, key, generation):
            assert database.active["connections"] == 0
            assert generation == "23"
            if fail_delete:
                raise FeedbackStorageError()
    stats = cleanup.verify_feedback_media_storage(database.factory, Storage(), now=NOW)
    assert stats == {"storage_verified": 1, "deleted": int(not fail_delete), "errors": int(fail_delete), "pending_verification": 0}
    with database.factory() as db:
        row = db.query(FeedbackAttachment).one()
        assert row.object_key and row.object_generation == "23"
        assert row.owner_id is None
        assert row.state == ("purge_pending" if fail_delete else "deleted")


def test_uncertain_probe_upload_retains_known_key_for_generation_lookup_cleanup(database):
    class Storage:
        def upload(self, key, data):
            raise FeedbackStorageError()
        def delete(self, key, generation):
            assert generation is None
            raise FeedbackStorageError()
    assert cleanup.verify_feedback_media_storage(database.factory, Storage(), now=NOW) == {
        "storage_verified": 0, "deleted": 0, "errors": 2, "pending_verification": 0,
    }
    with database.factory() as db:
        row = db.query(FeedbackAttachment).one()
        assert row.object_key and row.object_generation is None and row.state == "purge_pending"


def test_unknown_absence_is_rechecked_without_starving_new_deletions_then_catches_late_commit(database):
    orphan = _seed(database, state="pending")
    with database.factory() as db:
        db.get(FeedbackAttachment, orphan.id).object_generation = None
        db.commit()
    class Storage:
        late_generation = None
        def delete(self, key, generation):
            return self.late_generation if orphan.id.replace("-", "") in key else generation
    storage = Storage()
    first = cleanup.run_feedback_media_cleanup(database.factory, storage, now=NOW)
    assert first["deleted"] == 0 and first["pending_verification"] == 1 and first["errors"] == 0
    with database.factory() as db:
        row = db.get(FeedbackAttachment, orphan.id)
        assert row.state == "absent_unknown" and row.deleted_at is None and row.object_key
        assert ensure_utc(row.deletion_due_at) == NOW + timedelta(days=1)
    # A newly due known object takes priority over an older unknown tombstone.
    new = _seed(database, due=NOW + timedelta(days=1))
    second = cleanup.run_feedback_media_cleanup(database.factory, storage, now=NOW + timedelta(days=1), batch_size=1)
    assert second["deleted"] == 1 and second["pending_verification"] == 1
    with database.factory() as db:
        assert db.get(FeedbackAttachment, new.id).state == "deleted"
        assert db.get(FeedbackAttachment, orphan.id).state == "absent_unknown"
    storage.late_generation = "41"
    final = cleanup.run_feedback_media_cleanup(database.factory, storage, now=NOW + timedelta(days=1))
    assert final["deleted"] == 1 and final["pending_verification"] == 0
    with database.factory() as db:
        row = db.get(FeedbackAttachment, orphan.id)
        assert row.state == "deleted" and row.object_generation == "41"

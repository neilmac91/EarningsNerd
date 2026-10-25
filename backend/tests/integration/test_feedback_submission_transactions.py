"""PostgreSQL races for owner-serialized feedback claims, publication and account deletion.

FEEDBACK_CONCURRENCY_TEST_DATABASE_URL arms the required CI gate. Each test owns a disposable
schema and uses production SessionLocal settings. A writer's commit is held until a second
writer is observed blocked on PostgreSQL, rather than trusting a scheduling sleep.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import User
from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.schemas.feedback import FeedbackCreate
from app.services import feedback_submission_service as service
from app.services.feedback_image_service import NormalizedFeedbackImage
from app.services.user_account_service import delete_user

HANG_GUARD_S = 5
PAYLOAD = FeedbackCreate(type="bug", message="The chart clipped the filing text")


@pytest.fixture
def postgres_engine():
    url = os.environ.get("FEEDBACK_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("FEEDBACK_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql"
    schema = "feedback_submission_" + uuid4().hex
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        with _session(engine) as db:
            db.add(User(id=1, email="feedback-owner@example.test", is_active=True))
            db.commit()
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(engine):
    return sessionmaker(**{**SessionLocal.kw, "bind": engine})()


def _claim(db, key):
    return service.claim_submission(db, 1, key, service.payload_fingerprint(PAYLOAD, []))


def _race(engine, first, second):
    """Hold the first owner's lock through commit until the second waits or wrongly finishes."""
    held = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    second_pid = []

    def run_first():
        with _session(engine) as db:
            def before_commit(_):
                held.set()
                assert release.wait(HANG_GUARD_S), "The contender never reached its ownership lock"
            event.listen(db, "before_commit", before_commit, once=True)
            return first(db)

    def run_second():
        assert held.wait(HANG_GUARD_S)
        with _session(engine) as db:
            second_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            second_started.set()
            try:
                return second(db)
            except service.FeedbackSubmissionError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        leader = executor.submit(run_first)
        follower = executor.submit(run_second)
        try:
            assert second_started.wait(HANG_GUARD_S)
            deadline = time.monotonic() + HANG_GUARD_S
            blocked = False
            with engine.connect() as observer:
                while not follower.done() and time.monotonic() < deadline:
                    # READ COMMITTED snapshots of pg_stat_activity must not reuse a cached
                    # statistics snapshot while waiting for the contender's lock acquisition.
                    observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    wait = observer.execute(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                                            {"pid": second_pid[0]}).scalar_one_or_none()
                    observer.commit()
                    if wait == "Lock":
                        blocked = True
                        break
            assert blocked, "Competing feedback writer did not wait on the owner row"
        finally:
            release.set()
        return leader.result(timeout=HANG_GUARD_S), follower.result(timeout=HANG_GUARD_S)


def test_same_key_claim_is_single_flight_across_sessions(postgres_engine):
    key = str(uuid4())
    first, second = _race(postgres_engine, lambda db: _claim(db, key), lambda db: _claim(db, key))
    assert first.attempt_token and second.attempt_token is None
    assert first.submission_id == second.submission_id
    assert second.receipt.state == "processing"
    with _session(postgres_engine) as db:
        assert db.query(FeedbackSubmission).count() == 1


def test_distinct_keys_cannot_race_past_durable_allowance(postgres_engine, monkeypatch):
    monkeypatch.setattr(service, "MAX_SUBMISSIONS_PER_HOUR", 1)
    first, second = _race(postgres_engine, lambda db: _claim(db, str(uuid4())), lambda db: _claim(db, str(uuid4())))
    assert first.attempt_token and second == "quota"


def test_only_one_worker_can_publish_a_claim(postgres_engine):
    with _session(postgres_engine) as db:
        claim = _claim(db, str(uuid4()))
    def publish(db):
        return service.publish_submission(db, 1, claim, PAYLOAD, "hashed", {}, 180)
    first, second = _race(postgres_engine, publish, publish)
    assert first.id and second == "stale_attempt"
    with _session(postgres_engine) as db:
        assert db.query(Feedback).count() == 1


@pytest.mark.parametrize("deletion_first", (False, True))
def test_publication_and_owner_deletion_share_lock_order(postgres_engine, deletion_first):
    with _session(postgres_engine) as db:
        claim = _claim(db, str(uuid4()))
        manifests = service.reserve_attachments(db, 1, claim, [NormalizedFeedbackImage(b"pixels", 1, 1, "a" * 64)])
    def publish(db):
        return service.publish_submission(db, 1, claim, PAYLOAD, "hashed", {manifests[0].id: "1"}, 180)
    def delete(db):
        return delete_user(db, 1)
    first, second = _race(postgres_engine, delete if deletion_first else publish, publish if deletion_first else delete)
    if deletion_first:
        assert second == "owner_missing"
    with _session(postgres_engine) as db:
        assert db.get(User, 1) is None
        assert db.query(Feedback).count() == (0 if deletion_first else 1)
        attachment = db.get(FeedbackAttachment, manifests[0].id)
        assert attachment.state == "purge_pending" and attachment.owner_id is None
        assert attachment.object_key == manifests[0].object_key
        assert db.get(FeedbackSubmission, claim.submission_id).owner_id is None

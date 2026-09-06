"""Completed-use counter behavior and actual PostgreSQL transaction concurrency.

USAGE_CONCURRENCY_TEST_DATABASE_URL enables the PostgreSQL cases in CI. A supplied invalid or
unavailable database fails; each case owns a disposable schema, never public tables.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import MIN_SECRET_KEY_LENGTH, Settings, settings
from app.database import Base
from app.models import Summary, UsageReservation, User, UserUsage
from app.services import subscription_service as usage


MONTH = "2026-09"
WRITERS = [(usage.increment_user_usage, "summary_count"),
           (usage.increment_user_qa, "qa_count"), (usage.increment_user_analysis, "analysis_count")]
TABLES = [User.__table__, UserUsage.__table__, UsageReservation.__table__]


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'usage.db'}")
    Base.metadata.create_all(engine, tables=TABLES)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_engine():
    url = os.environ.get("USAGE_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("USAGE_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "Usage concurrency gate requires PostgreSQL"
    schema = f"usage_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=5000"})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine, tables=TABLES)
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _seed(engine, counts=None):
    with Session(engine) as db:
        user = User(email=f"usage-{uuid.uuid4().hex}@example.com")
        db.add(user)
        db.flush()
        if counts is not None:
            db.add(UserUsage(user_id=user.id, month=MONTH, summary_count=counts[0], qa_count=counts[1], analysis_count=counts[2]))
        db.commit()
        return user.id


def _rows(engine, user_id):
    with Session(engine) as db:
        return [(r.id, r.summary_count, r.qa_count, r.analysis_count)
                for r in db.query(UserUsage).filter_by(user_id=user_id, month=MONTH).order_by(UserUsage.id)]


@pytest.mark.parametrize("value", [0, -1, 10001, 0.5, float("inf"), float("nan")])
def test_lock_timeout_requires_positive_whole_bounded_milliseconds(value):
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="x" * MIN_SECRET_KEY_LENGTH, _env_file=None, USAGE_COUNTER_LOCK_TIMEOUT_MS=value)


@pytest.mark.parametrize("writer,column", WRITERS)
def test_postgres_existing_bucket_retains_parallel_increments_with_stale_sessions(postgres_engine, writer, column):
    uid = _seed(postgres_engine, (5, 7, 11))
    ready = threading.Barrier(2, timeout=5)

    def complete():
        with Session(postgres_engine) as db:
            stale = db.query(UserUsage).filter_by(user_id=uid, month=MONTH).one()
            ready.wait()
            writer(uid, MONTH, db)
            assert stale.id  # retain the identity-map entry through the increment

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(complete) for _ in range(2)]
        for future in futures:
            future.result(timeout=6)
    expected = dict(summary_count=5, qa_count=7, analysis_count=11)
    expected[column] += 2
    rows = _rows(postgres_engine, uid)
    assert len(rows) == 1
    assert rows[0][1:] == tuple(expected.values())


def test_postgres_parallel_first_use_creates_one_bucket_across_resources(postgres_engine):
    uid = _seed(postgres_engine)
    first_reads = threading.Barrier(3, timeout=5)
    local = threading.local()

    def after_read(conn, cursor, statement, parameters, context, executemany):
        if getattr(local, "first", False) and statement.startswith("SELECT user_usage.id"):
            local.first = False
            first_reads.wait()

    def complete(writer):
        local.first = True
        with Session(postgres_engine) as db:
            writer(uid, MONTH, db)

    event.listen(postgres_engine, "after_cursor_execute", after_read)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(complete, writer) for writer, _ in WRITERS]
            for future in futures:
                future.result(timeout=6)
    finally:
        event.remove(postgres_engine, "after_cursor_execute", after_read)
    rows = _rows(postgres_engine, uid)
    assert len(rows) == 1
    assert rows[0][1:] == (1, 1, 1)


@pytest.mark.parametrize("existing", [False, True])
def test_postgres_counter_lock_wait_is_bounded_and_failure_does_not_increment(postgres_engine, monkeypatch, existing):
    uid = _seed(postgres_engine, (0, 0, 0) if existing else None)
    monkeypatch.setattr(settings, "USAGE_COUNTER_LOCK_TIMEOUT_MS", 80)
    before = _rows(postgres_engine, uid)
    holder = Session(postgres_engine)
    target = UserUsage if existing else User
    predicate = UserUsage.user_id == uid if existing else User.id == uid
    holder.query(target).filter(predicate).with_for_update().first()

    def complete():
        with Session(postgres_engine) as db:
            usage.increment_user_usage(uid, MONTH, db)

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(complete)
        try:
            with pytest.raises(DBAPIError) as failure:
                future.result(timeout=1.5)
            assert failure.value.orig.pgcode == "55P03"
            assert time.monotonic() - started < 1.5
        finally:
            holder.rollback()
            holder.close()
            # A broken timeout must still leave a bounded mutation experiment.
            if not future.done():
                future.result(timeout=6)
    assert _rows(postgres_engine, uid) == before
    with Session(postgres_engine) as db:
        usage.increment_user_usage(uid, MONTH, db)
    assert _rows(postgres_engine, uid)[0][1:] == (1, 0, 0)


def test_postgres_existing_bucket_does_not_wait_for_stripe_parent_lock(postgres_engine, monkeypatch):
    uid = _seed(postgres_engine, (0, 0, 0))
    monkeypatch.setattr(settings, "USAGE_COUNTER_LOCK_TIMEOUT_MS", 80)
    with Session(postgres_engine) as holder:
        holder.query(User).filter_by(id=uid).with_for_update().first()
        with Session(postgres_engine) as db:
            usage.increment_user_usage(uid, MONTH, db)
        assert _rows(postgres_engine, uid)[0][1:] == (1, 0, 0)


def test_postgres_lock_setting_is_local_to_counter_transaction(postgres_engine):
    uid = _seed(postgres_engine, (0, 0, 0))
    with postgres_engine.connect() as conn:
        original = conn.scalar(select(func.current_setting("lock_timeout")))
        conn.commit()
        with Session(bind=conn) as db:
            usage.increment_user_usage(uid, MONTH, db)
        assert conn.scalar(select(func.current_setting("lock_timeout"))) == original


@pytest.mark.parametrize("existing", [False, True])
def test_failed_commit_rolls_back_without_retry(sqlite_engine, existing):
    uid = _seed(sqlite_engine, (2, 3, 4) if existing else None)
    before = _rows(sqlite_engine, uid)
    calls = []

    class FailedCommit(Session):
        def commit(self):
            calls.append("commit")
            self.flush()
            raise RuntimeError("commit outcome unavailable")

    with pytest.raises(RuntimeError, match="commit outcome unavailable"):
        with FailedCommit(sqlite_engine) as db:
            usage.increment_user_usage(uid, MONTH, db)
    assert calls == ["commit"]
    assert _rows(sqlite_engine, uid) == before


def test_existing_duplicate_history_is_neither_repaired_nor_summed(sqlite_engine):
    uid = _seed(sqlite_engine, (2, 3, 4))
    with Session(sqlite_engine) as db:
        db.add(UserUsage(user_id=uid, month=MONTH, summary_count=20, qa_count=30, analysis_count=40))
        db.commit()
        selected = db.query(UserUsage).filter_by(user_id=uid, month=MONTH).first().id
    before = _rows(sqlite_engine, uid)
    for writer, _ in WRITERS:
        with Session(sqlite_engine) as db:
            writer(uid, MONTH, db)
    expected = [(rid, a + (rid == selected), b + (rid == selected), c + (rid == selected)) for rid, a, b, c in before]
    assert _rows(sqlite_engine, uid) == expected
    with Session(sqlite_engine) as db:
        assert usage.get_user_usage_count(uid, MONTH, db) == next(r[1] for r in expected if r[0] == selected)


@pytest.mark.asyncio
async def test_signed_in_background_cached_summary_keeps_legacy_increment(sqlite_engine, monkeypatch):
    from app import database
    from app.services import summary_generation_service, summary_pipeline
    from tests.support.summary_stream_harness import seed_company_filing

    Base.metadata.create_all(sqlite_engine)
    factory = sessionmaker(bind=sqlite_engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(summary_generation_service, "SessionLocal", factory)
    fid = seed_company_filing()
    uid = _seed(sqlite_engine)
    with Session(sqlite_engine) as db:
        db.add(Summary(filing_id=fid, business_overview="Already stored"))
        db.commit()
    drain = AsyncMock(side_effect=AssertionError("cached background path regenerated"))
    monkeypatch.setattr(summary_pipeline, "stream_filing_summary", drain)
    await summary_generation_service.generate_summary_background(fid, uid)
    drain.assert_not_called()
    with Session(sqlite_engine) as db:
        assert usage.get_user_usage_count(uid, usage.get_current_month(), db) == 1
        assert db.query(Summary).filter_by(filing_id=fid).count() == 1


# --- E07b admission reservations (serialized decision + lease) --------------------------------
# reserve_summary_use is the only serialized admission decision; these pin that N parallel
# requests admit exactly the remaining units, that a converted unit blocks and a released one
# re-admits, that an expired lease is ignored and swept, and that a bounded lock wait admits
# nothing. The entitlement is stubbed to a small limit so the cases stay cheap.

def _free_limit(monkeypatch, limit):
    monkeypatch.setattr(usage, "get_entitlements", lambda user: SimpleNamespace(monthly_summary_limit=limit))


def _reservations(engine, user_id):
    with Session(engine) as db:
        return [(r.token, r.kind) for r in db.query(UsageReservation).filter_by(user_id=user_id).order_by(UsageReservation.id)]


def _load_user(db, user_id):
    return db.query(User).filter(User.id == user_id).one()


def test_postgres_parallel_reservations_admit_exactly_the_remaining_units(postgres_engine, monkeypatch):
    _free_limit(monkeypatch, 2)
    uid = _seed(postgres_engine, (0, 0, 0))
    ready = threading.Barrier(3, timeout=5)

    def reserve():
        with Session(postgres_engine) as db:
            user = _load_user(db, uid)
            ready.wait()
            return usage.reserve_summary_use(user, db)

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = [f.result(timeout=8) for f in [pool.submit(reserve) for _ in range(3)]]
    admitted = [o for o in outcomes if o[0]]
    blocked = [o for o in outcomes if not o[0]]
    assert len(admitted) == 2 and len(blocked) == 1
    assert all(o[3] for o in admitted) and blocked[0][3] is None
    assert blocked[0][2] == 2  # the visible Free cap, as check_usage_limit reports it
    assert len(_reservations(postgres_engine, uid)) == 2
    assert _rows(postgres_engine, uid)[0][1] == 0  # nothing counted until completion


def test_postgres_converted_reservation_blocks_and_released_reservation_readmits(postgres_engine, monkeypatch):
    _free_limit(monkeypatch, 1)
    uid = _seed(postgres_engine, (0, 0, 0))
    with Session(postgres_engine) as db:
        admitted, completed, limit, token = usage.reserve_summary_use(_load_user(db, uid), db)
        assert (admitted, completed, limit) == (True, 0, 1) and token
        # The reservation is held, so a second request is blocked before anything completes.
        assert usage.reserve_summary_use(_load_user(db, uid), db)[0] is False
        # Completion converts: the delete rides in the increment's commit, into the lease's month.
        assert usage.convert_reservation(token, db) == MONTH
        usage.increment_user_usage(uid, MONTH, db)
    assert _reservations(postgres_engine, uid) == []
    assert _rows(postgres_engine, uid)[0][1] == 1
    with Session(postgres_engine) as db:
        assert usage.reserve_summary_use(_load_user(db, uid), db) == (False, 1, 1, None)

    other = _seed(postgres_engine, (0, 0, 0))
    with Session(postgres_engine) as db:
        _, _, _, token = usage.reserve_summary_use(_load_user(db, other), db)
        assert usage.reserve_summary_use(_load_user(db, other), db)[0] is False
        usage.release_reservation(token, db)  # abandoned generation: give the unit back
        assert usage.reserve_summary_use(_load_user(db, other), db)[0] is True
        usage.release_reservation(None, db)  # idempotent no-op
    assert _rows(postgres_engine, other)[0][1] == 0


def test_postgres_expired_reservation_is_ignored_and_swept(postgres_engine, monkeypatch):
    _free_limit(monkeypatch, 1)
    uid = _seed(postgres_engine, (0, 0, 0))
    with Session(postgres_engine) as db:
        db.add(UsageReservation(
            user_id=uid, month=MONTH, kind=usage.SUMMARY_RESERVATION_KIND, token="stale-lease",
            expires_at=usage.utcnow() - timedelta(seconds=1), created_at=usage.utcnow() - timedelta(seconds=400),
        ))
        db.commit()
        admitted, _, _, token = usage.reserve_summary_use(_load_user(db, uid), db)
    assert admitted and token
    assert [t for t, _ in _reservations(postgres_engine, uid)] == [token]  # stale row swept


def test_postgres_reservation_lock_wait_is_bounded_and_admits_nothing(postgres_engine, monkeypatch):
    _free_limit(monkeypatch, 5)
    uid = _seed(postgres_engine, (0, 0, 0))
    monkeypatch.setattr(settings, "USAGE_COUNTER_LOCK_TIMEOUT_MS", 80)
    holder = Session(postgres_engine)
    holder.execute(select(User.id).where(User.id == uid).with_for_update())
    try:
        started = time.monotonic()
        with Session(postgres_engine) as db, pytest.raises(DBAPIError) as excinfo:
            usage.reserve_summary_use(_load_user(db, uid), db)
        assert getattr(excinfo.value.orig, "pgcode", None) == "55P03"
        assert time.monotonic() - started < 1.5
    finally:
        holder.rollback()
        holder.close()
    assert _reservations(postgres_engine, uid) == []


def test_postgres_conversion_between_admission_reads_blocks_instead_of_over_admitting(postgres_engine, monkeypatch):
    """READ COMMITTED: a completion that commits between admission's two reads must count at
    least once. Leases are read first, so the racing conversion is seen as a lease AND as a
    completed use (conservative block); reading the counter first would see neither."""
    _free_limit(monkeypatch, 1)
    uid = _seed(postgres_engine, (0, 0, 0))
    with Session(postgres_engine) as db:
        _, _, _, token = usage.reserve_summary_use(_load_user(db, uid), db)
    real_count = usage.get_user_usage_count

    def convert_then_count(user_id, month, db):
        # The in-flight generation completes in another session while admission is mid-decision.
        with Session(postgres_engine) as other:
            usage.increment_user_usage(uid, usage.convert_reservation(token, other), other)
        return real_count(user_id, month, db)

    monkeypatch.setattr(usage, "get_user_usage_count", convert_then_count)
    with Session(postgres_engine) as db:
        assert usage.reserve_summary_use(_load_user(db, uid), db)[0] is False
    assert _rows(postgres_engine, uid)[0][1] == 1
    assert _reservations(postgres_engine, uid) == []


def test_postgres_deleting_the_users_row_cascades_live_and_expired_reservations(postgres_engine, monkeypatch):
    """DELETE /api/users/me deletes the users row after Stripe cancellation; a live lease, or one
    a crashed worker left behind (swept only on a later admission), must go with it instead of
    failing the deletion on the FK. Core delete bypasses ORM cascades: this proves the database
    constraint (the ORM path is pinned in tests/unit/test_usage_reservation_wiring.py)."""
    _free_limit(monkeypatch, 5)
    uid = _seed(postgres_engine)
    with Session(postgres_engine) as db:
        assert usage.reserve_summary_use(_load_user(db, uid), db)[0] is True
        db.add(UsageReservation(
            user_id=uid, month=MONTH, kind=usage.SUMMARY_RESERVATION_KIND, token="abandoned-lease",
            expires_at=usage.utcnow() - timedelta(seconds=1), created_at=usage.utcnow() - timedelta(seconds=400),
        ))
        db.commit()
    assert len(_reservations(postgres_engine, uid)) == 2
    with Session(postgres_engine) as db:
        db.execute(delete(User).where(User.id == uid))
        db.commit()
    assert _reservations(postgres_engine, uid) == []


def test_convert_reservation_returns_the_admitted_month_and_drops_the_lease(sqlite_engine):
    """Conversion charges the month whose quota admitted the generation, so a lease that straddles
    a UTC month rollover never lands in the new month (whose admissions did not see it)."""
    uid = _seed(sqlite_engine)
    admitted_month = "2026-08"
    with Session(sqlite_engine) as db:
        db.add(UsageReservation(
            user_id=uid, month=admitted_month, kind=usage.SUMMARY_RESERVATION_KIND, token="rollover-lease",
            expires_at=usage.utcnow() + timedelta(seconds=300), created_at=usage.utcnow(),
        ))
        db.commit()
        assert usage.convert_reservation(None, db) is None
        assert usage.convert_reservation("unknown-token", db) is None
        assert _reservations(sqlite_engine, uid) == [("rollover-lease", "summary")]  # nothing dropped yet
        assert usage.convert_reservation("rollover-lease", db) == admitted_month
        usage.increment_user_usage(uid, admitted_month, db)  # commits the delete with the increment
    assert _reservations(sqlite_engine, uid) == []
    with Session(sqlite_engine) as db:
        buckets = {r.month: r.summary_count for r in db.query(UserUsage).filter_by(user_id=uid)}
    assert buckets == {admitted_month: 1}

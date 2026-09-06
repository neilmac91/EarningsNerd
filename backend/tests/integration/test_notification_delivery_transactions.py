"""E11b-1 delivery claims under real PostgreSQL concurrency, plus the FK cascades.

DELIVERY_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI. A supplied invalid or
unavailable database fails; each case owns a disposable schema, never public tables.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base
from app.models import Company, Filing, NotificationLog, NotificationPreferences, User, Watchlist
from app.models.notification_delivery import (
    KIND_FILING_REALTIME,
    STATUS_ACCEPTED,
    STATUS_CLAIMED,
    DeliveryBatch,
    DeliveryItem,
)
from app.services import notification_delivery_service as delivery

NOW = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
TABLES = [User.__table__, Company.__table__, Filing.__table__, Watchlist.__table__,
          NotificationPreferences.__table__, NotificationLog.__table__,
          DeliveryBatch.__table__, DeliveryItem.__table__]


@pytest.fixture
def postgres_engine():
    url = os.environ.get("DELIVERY_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DELIVERY_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "Delivery concurrency gate requires PostgreSQL"
    schema = f"delivery_transactions_{uuid.uuid4().hex}"
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


def _seed_batch(engine) -> tuple[int, int, int]:
    with Session(engine) as db:
        company = Company(cik=uuid.uuid4().hex[:10], ticker="T1", name="Company One")
        user = User(email=f"delivery-{uuid.uuid4().hex}@example.com", is_active=True, is_pro=True)
        db.add_all([company, user])
        db.flush()
        filing = Filing(company_id=company.id, accession_number=uuid.uuid4().hex, filing_type="10-Q", filing_date=NOW,
                        sec_url="https://sec.example/a/", document_url="https://sec.example/a/doc.htm")
        db.add_all([filing, Watchlist(user_id=user.id, company_id=company.id, created_at=NOW),
                    NotificationPreferences(user_id=user.id, realtime=True)])
        db.commit()
        batch = delivery.create_batch(db, kind=KIND_FILING_REALTIME, user_id=user.id, subject="s", html="h",
                                      filing_ids=[filing.id], now=NOW)
        return user.id, filing.id, batch.id


def test_postgres_competing_claims_admit_exactly_one_owner(postgres_engine):
    _, _, batch_id = _seed_batch(postgres_engine)
    ready = threading.Barrier(4, timeout=5)

    def try_claim(token):
        with Session(postgres_engine) as db:
            ready.wait()
            return delivery.claim(db, batch_id, token, NOW)

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = [f.result(timeout=8) for f in [pool.submit(try_claim, f"worker-{i}") for i in range(4)]]
    assert outcomes.count(True) == 1
    with Session(postgres_engine) as db:
        row = db.get(DeliveryBatch, batch_id)
        assert row.status == STATUS_CLAIMED and row.owner_token in {f"worker-{i}" for i in range(4)}


def test_postgres_stale_owner_is_fenced_out_of_send_and_finalisation(postgres_engine):
    _, _, batch_id = _seed_batch(postgres_engine)
    with Session(postgres_engine) as db:
        assert delivery.claim(db, batch_id, "owner", NOW) is True
    # Another worker that read the batch earlier can neither authorise nor finalise it.
    with Session(postgres_engine) as stale, Session(postgres_engine) as owner:
        assert delivery.authorize_send(stale, batch_id, "stale", NOW) is False
        assert delivery.authorize_send(owner, batch_id, "owner", NOW) is True
        assert delivery.finalize_accepted(stale, stale.get(DeliveryBatch, batch_id), "stale", "x", NOW) is False
        assert stale.query(NotificationLog).count() == 0
        assert delivery.finalize_accepted(owner, owner.get(DeliveryBatch, batch_id), "owner", "x", NOW) is True
    with Session(postgres_engine) as db:
        assert db.get(DeliveryBatch, batch_id).status == STATUS_ACCEPTED
        assert db.query(NotificationLog).count() == 1
        assert db.query(Watchlist).one().last_alerted_at is not None


def test_postgres_deleting_the_users_row_cascades_batches_and_items(postgres_engine):
    uid, _, batch_id = _seed_batch(postgres_engine)
    with Session(postgres_engine) as db:
        db.execute(delete(Watchlist).where(Watchlist.user_id == uid))
        db.execute(delete(NotificationPreferences).where(NotificationPreferences.user_id == uid))
        db.execute(delete(User).where(User.id == uid))  # Core delete: proves the FK, not the ORM cascade
        db.commit()
        assert db.get(DeliveryBatch, batch_id) is None
        assert db.query(DeliveryItem).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
async def test_postgres_deleting_a_filing_row_cascades_its_items(postgres_engine, partial):
    _, filing_id, batch_id = _seed_batch(postgres_engine)
    with Session(postgres_engine) as db:
        if partial:
            filing = db.get(Filing, filing_id)
            second = Filing(company_id=filing.company_id, accession_number=uuid.uuid4().hex,
                            filing_type="10-Q", filing_date=NOW, sec_url="https://sec.example/b/",
                            document_url="https://sec.example/b/doc.htm")
            db.add(second)
            db.flush()
            batch = db.get(DeliveryBatch, batch_id)
            batch.expected_item_count = 2
            db.add(DeliveryItem(batch_id=batch_id, user_id=batch.user_id, filing_id=second.id,
                                channel="email", position=1))
            db.commit()
        db.execute(delete(Filing).where(Filing.id == filing_id))
        db.commit()
        assert db.query(DeliveryItem).count() == int(partial) and db.get(DeliveryBatch, batch_id) is not None
        calls = []

        async def send(prepared):
            calls.append(prepared)
            return "email_1"

        result = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=send, now=NOW)
        assert calls == [] and result.suppressed == 1
        assert db.query(NotificationLog).count() == 0
        assert db.query(Watchlist).one().last_alerted_at is None

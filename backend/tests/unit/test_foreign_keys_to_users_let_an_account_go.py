"""Gate: no foreign key to ``users`` can stop an account's deletion (PB-02; CLAUDE.md rule 12).

An account's deletion (``user_account_service._delete_locked_account``) deletes its ``users`` row through the ORM. A
table that references ``users.id`` lets that DELETE through only when the database acts on it (``ON DELETE CASCADE`` or
``SET NULL``) or the ORM deletes the referencing rows first (a ``User`` relationship whose cascade includes delete).
``trend_analysis.created_by_user_id`` did neither until PB-02, so on PostgreSQL an account that had generated a cached
Multi-Period Analysis could not be deleted, and a complimentary grant opens analysis generation to every invited
tester. This gate reads every mapped table's foreign keys to ``users.id`` and holds each to one of the two.

The second case plants the bug: an account stamped on an analysis, deleted through the real deletion path on a SQLite
database that enforces foreign keys (``PRAGMA foreign_keys=ON``, as PostgreSQL always does). It passes only while the
reference sets null, and then keeps the shared analysis with its stamp cleared.

Out of reach: a deletion made outside the ORM path (``test_unaudited_deletion_callers_allowlist.py`` holds those to a
reviewed list), and a reference declared in a migration but not in a model (every table here is mapped).
"""
import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Company, TrendAnalysis, User
from app.services import user_account_service
from tests.support.models import import_every_model

# What the database does with a reference when the account goes: delete the row, or clear the reference.
ACTS_ON_DELETE = {"CASCADE", "SET NULL"}


def _blocking_references() -> list[str]:
    import_every_model()
    cascaded = {rel.mapper.local_table.name for rel in User.__mapper__.relationships if rel.cascade.delete}
    return sorted(
        f"{table.name}.{fk.parent.name}"
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "users"
        and (fk.ondelete or "").upper() not in ACTS_ON_DELETE
        and table.name not in cascaded
    )


def test_every_foreign_key_to_users_lets_the_account_go():
    assert _blocking_references() == [], (
        "a reference to users.id that neither acts on delete (ON DELETE CASCADE or SET NULL, in the model and a "
        "migration) nor is deleted by a User relationship's cascade stops the account's deletion on PostgreSQL"
    )


@pytest.fixture
def enforcing_db(monkeypatch):
    """A private SQLite database that enforces foreign keys, as PostgreSQL does, for the real deletion path."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enforce(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    import_every_model()
    Base.metadata.create_all(engine)
    # The deletion queues the owner's feedback media for removal; nothing here stores any.
    monkeypatch.setattr(user_account_service, "enqueue_owner_media_deletion", lambda db, user_id: None)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_deleting_an_account_that_generated_an_analysis_clears_its_stamp_and_keeps_the_analysis(enforcing_db):
    db = enforcing_db
    user = User(email=f"analyst-{uuid.uuid4().hex}@example.com", email_verified=True, is_pro=True)
    company = Company(cik="0000000042", ticker="STMP", name="Stamp Co")
    db.add_all([user, company])
    db.flush()
    db.add(TrendAnalysis(company_id=company.id, mode="annual", period_key="FY2022..FY2024", prompt_version="v",
                         dataset_fingerprint="f" * 64, dataset_json={}, narrative_md="n", citations_json=[],
                         model="m", grounded=1, created_by_user_id=user.id))
    db.commit()
    user_id = user.id

    user_account_service.delete_account(db, user_id, third_party_results={"stripe": "none"})

    db.expire_all()
    assert db.get(User, user_id) is None
    analysis = db.query(TrendAnalysis).one()
    assert analysis.created_by_user_id is None

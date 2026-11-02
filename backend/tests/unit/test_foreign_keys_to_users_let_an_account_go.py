"""Gate: no foreign key to ``users`` can stop an account's deletion (PB-02; CLAUDE.md rule 12).

An account's deletion (``user_account_service._delete_locked_account``) deletes its ``users`` row through the ORM. A
table that references ``users.id`` lets that DELETE through only when the database acts on it (``ON DELETE CASCADE`` or
``SET NULL``) or the ORM deletes the referencing rows first (a ``User`` relationship whose cascade includes delete).
``trend_analysis.created_by_user_id`` did neither until PB-02, so on PostgreSQL an account that had generated a cached
Multi-Period Analysis could not be deleted, and a complimentary grant opens analysis generation to every invited
tester. This gate reads every mapped table's foreign keys to ``users.id`` and holds each to one of the two: the
relationship's exemption covers only the column it deletes through, since a second reference on the same table that
does neither still stops the DELETE, and ``SET NULL`` counts only on a column that can hold a null. Production's constraints are the ones its migrations built (CI's PostgreSQL jobs
seed with ``create_all``, which builds the model's), so it also reads every reference to ``users`` a migration
declares and holds it to acting on delete, save the one legacy file a later migration replaced.

The second case plants the bug: an account stamped on an analysis, deleted through the real deletion path on a SQLite
database that enforces foreign keys (``PRAGMA foreign_keys=ON``, as PostgreSQL always does). It passes only while the
reference sets null, and then keeps the shared analysis with its stamp cleared.

Out of reach: a deletion made outside the ORM path (``test_unaudited_deletion_callers_allowlist.py`` holds those to a
reviewed list), and a reference made in production outside the migrations and the models.
"""
import re
import uuid
from pathlib import Path

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
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
# A migration that declared a reference to users with no ON DELETE action, and the later one that replaced it. An
# applied migration is never edited (CLAUDE.md rule 3), so the old file stays; its replacement must stay too.
SUPERSEDED = {"20260707_create_trend_analysis.sql": "20261102_trend_analysis_creator_set_null.sql"}
_REFERENCE = re.compile(
    r'(?P<column>[^,;\n]*)REFERENCES\s+(?:"?public"?\s*\.\s*)?"?users"?(?!\w)(?:\s*\(\s*"?id"?\s*\))?(?P<rest>[^,;]*)',
    re.IGNORECASE)
_ACTION = re.compile(r"\bON\s+DELETE\s+(?:CASCADE|SET\s+NULL)\b", re.IGNORECASE)
_SET_NULL = re.compile(r"\bON\s+DELETE\s+SET\s+NULL\b", re.IGNORECASE)
# A column's NOT NULL, not a guard's "IS NOT NULL".
_NOT_NULL = re.compile(r"(?<!IS )\bNOT\s+NULL\b", re.IGNORECASE)


def _blocking_references(user_mapper=None, tables=None) -> list[str]:
    if user_mapper is None:
        import_every_model()
        user_mapper, tables = User.__mapper__, Base.metadata.tables.values()
    # The ORM deletes the rows a cascading User relationship reaches through its own columns, so only those columns
    # are exempt: another reference to users on the same table still stops the DELETE. With passive_deletes the ORM
    # leaves rows it has not loaded to the database's ON DELETE, so such a relationship exempts nothing.
    cascaded = {
        (column.table.name, column.name)
        for rel in user_mapper.relationships if rel.cascade.delete and not rel.passive_deletes
        for column in rel.remote_side
    }
    def acts(fk) -> bool:
        action = (fk.ondelete or "").upper()
        # SET NULL on a column that cannot hold a null fails the DELETE as surely as no action does.
        return action in ACTS_ON_DELETE and (action != "SET NULL" or fk.parent.nullable)

    return sorted(
        f"{table.name}.{fk.parent.name}"
        for table in tables
        for fk in table.foreign_keys
        if fk.column.table.name == "users" and not acts(fk) and (table.name, fk.parent.name) not in cascaded
    )


def _migrations_without_an_action(texts) -> list[str]:
    """Each migration that declares a reference to users without ON DELETE CASCADE or SET NULL, or with SET NULL on a
    column it declares NOT NULL (before the reference on its line, or after it), once per reference. A column
    definition is read back to the comma before it on its line, so these are out of reach, and the models' check covers
    them while model and migration agree: a NOT NULL on an earlier line or before a CHECK holding a comma of its own, a
    table constraint's reference from a column declared NOT NULL elsewhere, and a later ALTER ... SET NOT NULL."""
    found = []
    for name, text in texts:
        sql = re.sub(r"--[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
        found += [
            name for match in _REFERENCE.finditer(sql)
            if not _ACTION.search(match.group("rest"))
            or (_SET_NULL.search(match.group("rest"))
                and (_NOT_NULL.search(match.group("column")) or _NOT_NULL.search(match.group("rest"))))
        ]
    return found


def test_every_foreign_key_to_users_lets_the_account_go():
    assert _blocking_references() == [], (
        "a reference to users.id that neither acts on delete (ON DELETE CASCADE or SET NULL, in the model and a "
        "migration) nor is the column a User relationship's cascade deletes through stops the account's deletion on "
        "PostgreSQL"
    )


def test_the_relationship_exemption_covers_only_the_column_it_deletes_through():
    """Planted: two references from one table, one of them a cascading relationship's (the review's probe of the
    gate's first form, which exempted the whole table)."""
    from sqlalchemy import Column, ForeignKey, Integer
    from sqlalchemy.orm import declarative_base, relationship

    Planted = declarative_base()

    class Owner(Planted):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        invites = relationship("Invite", foreign_keys="Invite.user_id", cascade="all, delete-orphan")
        # passive_deletes: the ORM leaves the rows it has not loaded to the database, which has no ON DELETE here.
        items = relationship("Item", cascade="all, delete-orphan", passive_deletes=True)

    class Invite(Planted):
        __tablename__ = "invites"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"))
        created_by = Column(Integer, ForeignKey("users.id"))
        # SET NULL where no null may go: the DELETE fails on the column's NOT NULL instead.
        reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
        cleared_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    class Item(Planted):
        __tablename__ = "items"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"))

    assert _blocking_references(Owner.__mapper__, Planted.metadata.tables.values()) == [
        "invites.created_by", "invites.reviewed_by", "items.user_id"]


def test_every_migration_reference_to_users_acts_on_delete():
    texts = [(path.name, path.read_text(encoding="utf-8")) for path in sorted(MIGRATIONS.glob("*.sql"))]
    assert sorted(set(_migrations_without_an_action(texts))) == sorted(SUPERSEDED), (
        "a migration's REFERENCES users must say ON DELETE CASCADE or SET NULL: production's constraint is the one the "
        "migration built, and CI's create_all seed would hide its absence"
    )
    for legacy, replacement in SUPERSEDED.items():
        assert _ACTION.search((MIGRATIONS / replacement).read_text(encoding="utf-8")), (legacy, replacement)
    # The reader, on the forms the files use: a column's reference, a table constraint, a line break before the action,
    # and a comment, which declares nothing.
    assert _migrations_without_an_action([
        ("column", "user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,"),
        ("constraint", "ADD CONSTRAINT k FOREIGN KEY (a) REFERENCES users(id) ON DELETE SET NULL NOT VALID;"),
        ("wrapped", "owner_id INTEGER REFERENCES \"users\" (id)\n    ON DELETE SET NULL,"),
        ("comment", "-- created_by references users(id) with no ON DELETE action"),
        ("bare", "created_by INTEGER REFERENCES users,"),
        ("other table", "x INTEGER REFERENCES users_archive (id),"),
        ("set null where no null may go", "CREATE TABLE t (owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL);"),
        ("cascade beside not null", "user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,"),
        ("not null after it", "owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL NOT NULL,"),
        ("not null before a check", "owner_id INTEGER NOT NULL CHECK (owner_id > 0) REFERENCES users(id) ON DELETE SET NULL,"),
        ("block comment", "/* owner_id INTEGER REFERENCES users(id) */ SELECT 1;"),
        ("a guard's is not null", "IF to_regclass('t') IS NOT NULL THEN\n ALTER TABLE t ADD CONSTRAINT k FOREIGN KEY (a) "
                                  "REFERENCES users (id) ON DELETE SET NULL NOT VALID;"),
    ]) == ["bare", "set null where no null may go", "not null after it", "not null before a check"]


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

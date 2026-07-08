"""Summary version stamps (schema_version + prompt_version).

A generated Summary records the schema (sections taxonomy) and prompt version it was produced
under so a serializer/prompt change can identify and refresh stale rows instead of stranding a
pre-change ``business_overview`` (the ".;" post-mortem). These tests pin: the ORM columns exist on
a fresh DB, an existing summaries table self-heals them at startup, and the staleness rule.
"""
from sqlalchemy import create_engine, inspect, text

from app.database import _ADDITIVE_COLUMNS, ensure_additive_columns
from app.models import Base, Summary
from app.services.summary_versioning import (
    SUMMARY_PROMPT_VERSION,
    SUMMARY_SCHEMA_VERSION,
    is_stale,
)


def test_summary_orm_has_version_columns():
    # Fresh DBs get the columns from the ORM via create_all (no migration needed).
    cols = {c.name for c in Summary.__table__.columns}
    assert "schema_version" in cols
    assert "prompt_version" in cols


def test_additive_columns_self_heal_summaries():
    # An existing summaries table missing the stamps self-heals them at startup, idempotently.
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE summaries (id INTEGER PRIMARY KEY, filing_id INTEGER)"))
    specs = [
        (t, col, ddl) for (t, col, ddl) in _ADDITIVE_COLUMNS if t == "summaries"
    ]
    assert {(t, col) for t, col, _ in specs} == {
        ("summaries", "schema_version"),
        ("summaries", "prompt_version"),
    }
    ensure_additive_columns(bind=eng, specs=specs)
    names = {col["name"] for col in inspect(eng).get_columns("summaries")}
    assert {"schema_version", "prompt_version"} <= names
    # Idempotent second run must not raise.
    ensure_additive_columns(bind=eng, specs=specs)


def test_create_all_produces_version_columns():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng, tables=[Summary.__table__])
    names = {col["name"] for col in inspect(eng).get_columns("summaries")}
    assert {"schema_version", "prompt_version"} <= names


def test_is_stale_rule():
    # Current stamps are fresh; a missing or behind stamp is stale.
    assert is_stale(SUMMARY_SCHEMA_VERSION, SUMMARY_PROMPT_VERSION) is False
    assert is_stale(None, SUMMARY_PROMPT_VERSION) is True
    assert is_stale(SUMMARY_SCHEMA_VERSION, None) is True
    assert is_stale(SUMMARY_SCHEMA_VERSION - 1, SUMMARY_PROMPT_VERSION) is True
    assert is_stale(SUMMARY_SCHEMA_VERSION, "old-prompt") is True


def test_version_constants_types():
    assert isinstance(SUMMARY_SCHEMA_VERSION, int)
    assert isinstance(SUMMARY_PROMPT_VERSION, str) and SUMMARY_PROMPT_VERSION

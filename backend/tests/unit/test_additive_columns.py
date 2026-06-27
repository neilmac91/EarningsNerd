"""Startup self-heal for post-CREATE additive columns (database.ensure_additive_columns).

create_all() never ALTERs an existing table, so additive columns introduced after the original
CREATE (e.g. the FPI alert prefs notify_20f/notify_6k) are applied at startup. Idempotent and
non-fatal by construction.
"""
from sqlalchemy import create_engine, inspect, text

from app.database import ensure_additive_columns


def test_adds_missing_column_and_is_idempotent():
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))

    spec = [("t", "flag", "BOOLEAN NOT NULL DEFAULT TRUE")]
    ensure_additive_columns(bind=eng, specs=spec)
    assert "flag" in {col["name"] for col in inspect(eng).get_columns("t")}

    # Second run is a no-op (column already present) — must not raise.
    ensure_additive_columns(bind=eng, specs=spec)
    assert "flag" in {col["name"] for col in inspect(eng).get_columns("t")}


def test_missing_table_is_skipped_not_raised():
    eng = create_engine("sqlite://")
    # No such table — must be a quiet no-op, never raise (startup must not be blocked).
    ensure_additive_columns(bind=eng, specs=[("nope", "x", "BOOLEAN NOT NULL DEFAULT FALSE")])


def test_default_specs_target_fpi_pref_columns():
    from app.database import _ADDITIVE_COLUMNS

    cols = {(t, c) for t, c, _ in _ADDITIVE_COLUMNS}
    assert ("notification_preferences", "notify_20f") in cols
    assert ("notification_preferences", "notify_6k") in cols

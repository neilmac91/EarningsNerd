"""A companyfacts sync as production ran it before E198, for tests that plant the rows earlier syncs stored.

Until E198 a sync in USD alone (no currency but USD in the payload's pick or in a stored amount or per-share row of
the batch's concepts: ``facts/currency.py::_another_currency``) was the upsert alone: it protected no row and its
currency step returned before touching one, so it never converged a key. From #1583 (2026-11-01) a sync involving
another currency ran the currency step, as every sync runs it since E198. Every sync of a USD filer in production's
history ran as the upsert alone, so a test that plants the state those syncs left (a repair's or a preview's cohort,
a reader's stored rows) runs its syncs inside ``usd_syncs_before_e198``; a test of what a sync does now runs it as it
is. Retire with the last test that plants such a state.
"""
from __future__ import annotations

from typing import Any


def usd_syncs_before_e198(patch: Any) -> None:
    """Make ``patch`` (pytest's ``monkeypatch`` or one of its contexts) run each companyfacts sync as one before E198
    ran it: where ``_another_currency`` reads no other currency, the guard protects nothing and the currency step
    changes nothing, after the fact writers' company lock is taken as ``protected_rows`` took it; elsewhere both run
    as they do now."""
    from app.services.facts import currency, ingest
    from app.services.facts.upsert import _lock_fact_companies

    real_rows, real_step, alone = ingest.protected_rows, ingest.demote_convenience_rows, {}

    def rows(db, facts, view):
        if facts:
            _lock_fact_companies(db, facts)
        alone["now"] = bool(facts) and not currency._another_currency(db, facts, view)
        return currency.Guard(frozenset(), None, {}) if alone["now"] else real_rows(db, facts, view)

    def step(db, facts, view, guard):
        return 0 if alone.get("now") else real_step(db, facts, view, guard)

    patch.setattr(ingest, "protected_rows", rows)
    patch.setattr(ingest, "demote_convenience_rows", step)

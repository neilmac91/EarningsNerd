"""Notification-preference helpers shared by the alert engine and the prefs API.

Keeps the "what should this user be alerted about, and how" logic in one place:
- ``get_or_create_preferences`` — every user has well-defined defaults even without a row.
- ``coerce_to_entitlement`` — Pro-gated toggles (realtime, 8-K) are silently forced off for
  non-Pro users so the API never grants what billing doesn't allow.
- ``apply_preference_update`` — the prefs API's write: apply the change, coerce, commit.
- ``evaluate_delivery`` — given prefs + entitlements + a filing type, decide (eligible, realtime).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NotificationPreferences
from app.services.entitlements import Entitlements, get_entitlements
from app.models import User


def _preferences(db: Session, user_id: int) -> Optional[NotificationPreferences]:
    """The user's prefs row: the get-or-create's check."""
    return (
        db.query(NotificationPreferences)
        .filter(NotificationPreferences.user_id == user_id)
        .first()
    )


def get_or_create_preferences(db: Session, user_id: int, *, commit: bool = True) -> NotificationPreferences:
    """Return the user's prefs row, creating one with defaults if absent.

    Two callers can both find no row: two first requests of one account, which run at once in the
    thread pool or on the API's two instances, or a request and the alert scanner. The insert runs
    under a SAVEPOINT, so the second insert's clash on the unique ``user_id`` rolls back only that
    insert, and the caller reads the row the first one stored: PostgreSQL holds the second insert
    until the first's transaction ends, and the read after it sees that commit (READ COMMITTED).
    The caller's pending state is flushed first, so a clash caught here can only be this insert's.
    On SQLite (the tests), when the caller has written nothing yet, the SAVEPOINT opens the transaction
    and its RELEASE commits it, so there the update's ``commit=False`` insert is stored at once;
    PostgreSQL holds it until the caller commits."""
    prefs = _preferences(db, user_id)
    if prefs is not None:
        return prefs
    db.flush()
    prefs = NotificationPreferences(user_id=user_id)
    try:
        with db.begin_nested():  # SAVEPOINT: a unique-user_id clash must not poison the transaction
            db.add(prefs)
            db.flush()
    except IntegrityError:
        stored = _preferences(db, user_id)
        if stored is None:
            raise
        return stored
    if commit:
        db.commit()
        db.refresh(prefs)
    return prefs


def coerce_to_entitlement(prefs: NotificationPreferences, ent: Entitlements) -> NotificationPreferences:
    """Force Pro-gated toggles off if the plan doesn't allow them. Mutates and returns ``prefs``."""
    if not ent.realtime_alerts:
        prefs.realtime = False
    if not ent.eightk_coverage:
        prefs.notify_8k = False
    return prefs


def apply_preference_update(
    db: Session, prefs: NotificationPreferences, data: Dict[str, Any], current_user: User
) -> Entitlements:
    """Write already-validated preference changes, force Pro-only toggles off when the plan does
    not allow them, and commit. Returns the entitlements the response reports."""
    for field, value in data.items():
        setattr(prefs, field, value)

    ent = get_entitlements(current_user)
    coerce_to_entitlement(prefs, ent)  # force Pro-only toggles off if not entitled
    db.commit()
    db.refresh(prefs)
    return ent


def _is_six_k(filing_type: str) -> bool:
    ft = (filing_type or "").upper().replace(" ", "")
    return ft.startswith("6-K") or ft.startswith("6K")


def _filing_type_enabled(prefs: NotificationPreferences, ent: Entitlements, filing_type: str) -> bool:
    ft = (filing_type or "").upper().replace(" ", "")
    if ft.startswith("10-K") or ft.startswith("10K"):
        return bool(prefs.notify_10k)
    if ft.startswith("10-Q") or ft.startswith("10Q"):
        return bool(prefs.notify_10q)
    if ft.startswith("8-K") or ft.startswith("8K"):
        # 8-K is Pro-only: requires both the user's opt-in AND the entitlement.
        return bool(prefs.notify_8k and ent.eightk_coverage)
    # FPI forms (Phase 5). 20-F + 40-F (Canadian annual analogue) share one opt-in; 6-K is its own.
    if ft.startswith("20-F") or ft.startswith("20F") or ft.startswith("40-F") or ft.startswith("40F"):
        return bool(prefs.notify_20f)
    if _is_six_k(filing_type):  # _is_six_k normalizes; pass the raw value (ft is already normalized)
        return bool(prefs.notify_6k)
    return False


def evaluate_delivery(
    prefs: NotificationPreferences, ent: Entitlements, filing_type: str
) -> Tuple[bool, bool]:
    """Return ``(eligible, realtime)`` for a filing.

    eligible — should this user ever be alerted about this filing type?
    realtime — if eligible, send immediately (Pro + realtime opted in) vs queue for the digest.
    """
    if not _filing_type_enabled(prefs, ent, filing_type):
        return (False, False)
    # 6-Ks are frequent and heterogeneous (earnings vs governance vs press release), so they are
    # ALWAYS digest-only — never realtime even for a Pro user with realtime on — to avoid spam.
    realtime = bool(ent.realtime_alerts and prefs.realtime and not _is_six_k(filing_type))
    return (True, realtime)


def entitlements_for(user: User) -> Entitlements:
    """Thin pass-through so callers don't import two modules."""
    return get_entitlements(user)

"""Notification-preference helpers shared by the alert engine and the prefs API.

Keeps the "what should this user be alerted about, and how" logic in one place:
- ``get_or_create_preferences`` — every user has well-defined defaults even without a row.
- ``coerce_to_entitlement`` — Pro-gated toggles (realtime, 8-K) are silently forced off for
  non-Pro users so the API never grants what billing doesn't allow.
- ``evaluate_delivery`` — given prefs + entitlements + a filing type, decide (eligible, realtime).
"""
from __future__ import annotations

from typing import Tuple

from sqlalchemy.orm import Session

from app.models import NotificationPreferences
from app.services.entitlements import Entitlements, get_entitlements
from app.models import User


def get_or_create_preferences(db: Session, user_id: int, *, commit: bool = True) -> NotificationPreferences:
    """Return the user's prefs row, creating one with defaults if absent."""
    prefs = (
        db.query(NotificationPreferences)
        .filter(NotificationPreferences.user_id == user_id)
        .first()
    )
    if prefs is None:
        prefs = NotificationPreferences(user_id=user_id)
        db.add(prefs)
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
    if _is_six_k(ft):
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

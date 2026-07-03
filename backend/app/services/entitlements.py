"""Entitlements: the single source of truth for what a user's plan allows.

Resolution order (see :func:`get_plan`):
1. The user's ``Subscription`` row (``status ∈ {active, trialing}`` and any trial not expired) —
   this is the authoritative billing record, written only by the Stripe webhook.
2. Fallback to the ``User.is_pro`` denormalised mirror (kept in sync by the same webhook), so
   existing reads keep working and a missing/lazy subscription relationship never downgrades a
   paying user.

Feature gates should call :func:`get_entitlements` (or the ``require_entitlement`` FastAPI
dependency in ``app.dependencies``) rather than reading ``is_pro`` directly. Adding a tier or a
new gated capability is then a change to this module plus Stripe price wiring — not a hunt through
scattered ``if user.is_pro`` checks.

Note: ``monthly_summary_limit``, ``can_export`` and ``can_compare_filings`` are enforced today.
The remaining flags (alerts, 8-K, history, priority model) are forward-looking and consumed by
later phases; they intentionally do not yet change behaviour on their own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models import User

# Free-tier monthly summary cap. Single definition; ``subscription_service`` re-exports it for
# backwards compatibility with existing imports.
FREE_TIER_SUMMARY_LIMIT = 5

# Earnings-day alert caps (strategy §3.7). Free is a VISIBLE product surface (a conversion
# upsell); Pro's 100 is an INVISIBLE anti-abuse guardrail — nothing surfaces it, and only the
# attempt to enable the 101st returns a terse generic error.
FREE_EARNINGS_ALERT_LIMIT = 3
PRO_EARNINGS_ALERT_LIMIT = 100

# Statuses that grant Pro. Mirrors ``app.models.subscription.ACTIVE_STATUSES`` (kept local to avoid
# importing the model layer for a constant); ``trialing`` is the 7-day reverse trial.
_ACTIVE_STATUSES = frozenset({"active", "trialing"})


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"


@dataclass(frozen=True)
class Entitlements:
    plan: Plan
    monthly_summary_limit: Optional[int]  # None == unlimited
    can_compare_filings: bool
    can_export: bool
    can_save_summaries: bool
    watchlist_limit: Optional[int]  # None == unlimited
    # Max companies a user may have earnings-day alerts enabled for. Free 3 (visible upsell) /
    # Pro 100 (invisible guardrail). None would mean unlimited — deliberately not used.
    earnings_alert_limit: int = FREE_EARNINGS_ALERT_LIMIT
    # Forward-looking flags (Phases 2–4). Defaults keep older constructors valid.
    realtime_alerts: bool = False
    eightk_coverage: bool = False
    history_retention_days: Optional[int] = None  # None == full history
    priority_model: bool = False
    # "Ask this Filing" Copilot (A2). Pro-only grounded single-filing Q&A.
    copilot: bool = False
    # Free "taste" of Copilot (roadmap 2.2): a lifetime allowance of grounded questions for users
    # without the full `copilot` entitlement, after which they hit the upsell. 0 = no taste (Pro
    # doesn't need one — it's unlimited via `copilot=True`).
    copilot_free_taste: int = 0

    @property
    def has_unlimited_summaries(self) -> bool:
        return self.monthly_summary_limit is None


_FREE = Entitlements(
    plan=Plan.FREE,
    monthly_summary_limit=FREE_TIER_SUMMARY_LIMIT,
    can_compare_filings=True,
    can_export=False,
    can_save_summaries=True,
    # Unlimited watchlist on free is deliberate (discovery/habit drives the value loop); Pro
    # captures volume/depth/speed/breadth instead. See IMPLEMENTATION_PLAN §8.
    watchlist_limit=None,
    earnings_alert_limit=FREE_EARNINGS_ALERT_LIMIT,
    realtime_alerts=False,
    eightk_coverage=False,
    history_retention_days=90,
    priority_model=False,
    copilot=False,
    # 3 lifetime grounded Copilot questions as a taste before the upsell (roadmap 2.2).
    copilot_free_taste=3,
)

_PRO = Entitlements(
    plan=Plan.PRO,
    monthly_summary_limit=None,
    can_compare_filings=True,
    can_export=True,
    can_save_summaries=True,
    watchlist_limit=None,
    earnings_alert_limit=PRO_EARNINGS_ALERT_LIMIT,
    realtime_alerts=True,
    eightk_coverage=True,
    history_retention_days=None,
    priority_model=True,
    copilot=True,
)


def _is_in_future(dt: Optional[datetime]) -> bool:
    """tz-safe ``dt > now``. Treats a naive datetime (SQLite) as UTC to dodge the
    'can't compare offset-naive and offset-aware' pitfall Postgres-vs-SQLite would otherwise hit."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc)


def _subscription_grants_pro(user: User) -> Optional[bool]:
    """Return True/False from the user's Subscription row, or None if no usable row is present.

    Guards relationship access: a detached instance or a session without the relationship loaded
    should fall back to the ``is_pro`` mirror rather than raise.
    """
    try:
        sub = getattr(user, "subscription", None)
    except Exception:
        return None
    if sub is None:
        return None
    status = (getattr(sub, "status", None) or "").lower()
    if status not in _ACTIVE_STATUSES:
        return False
    # A trialing row whose trial has elapsed is no longer entitled (the webhook normally flips this,
    # but never trust a stale clock for access decisions).
    if status == "trialing" and getattr(sub, "trial_end", None) is not None:
        return _is_in_future(sub.trial_end)
    return True


def get_plan(user: User) -> Plan:
    """Resolve a user's plan: subscription row first, then the ``is_pro`` mirror."""
    from_sub = _subscription_grants_pro(user)
    if from_sub is not None:
        return Plan.PRO if from_sub else Plan.FREE
    return Plan.PRO if getattr(user, "is_pro", False) else Plan.FREE


def get_entitlements(user: User) -> Entitlements:
    """Resolve a user's entitlements from their plan."""
    return _PRO if get_plan(user) is Plan.PRO else _FREE


def is_pro_user(user: User) -> bool:
    """Convenience boolean for gates that only care about Pro-vs-not."""
    return get_plan(user) is Plan.PRO


def can_use_copilot(user: User) -> bool:
    """True if the user may ask a Copilot question right now: Pro (full entitlement) or a Free user
    still within their lifetime free-taste allowance (roadmap 2.2)."""
    ent = get_entitlements(user)
    if ent.copilot:
        return True
    used = getattr(user, "copilot_free_taste_used", 0) or 0
    return used < ent.copilot_free_taste

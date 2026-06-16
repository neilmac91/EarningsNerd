"""Entitlements: the single source of truth for what a user's plan allows.

Today the only monetization signal is ``User.is_pro``, so entitlements are derived from it.
Centralising the plan → limits/features mapping here means that turning on real monetization
later (more tiers, usage-based limits, team plans) becomes a change to this module plus Stripe
price wiring — not a hunt through scattered ``if user.is_pro`` checks across the codebase.

Feature gates should call :func:`get_entitlements` rather than reading ``is_pro`` directly.

Note: only ``monthly_summary_limit`` is enforced today (via ``subscription_service``). The other
fields are forward-looking metadata for upcoming gates and intentionally do not yet change any
behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.models import User

# Free-tier monthly summary cap. Single definition; ``subscription_service`` re-exports it for
# backwards compatibility with existing imports.
FREE_TIER_SUMMARY_LIMIT = 5


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

    @property
    def has_unlimited_summaries(self) -> bool:
        return self.monthly_summary_limit is None


_FREE = Entitlements(
    plan=Plan.FREE,
    monthly_summary_limit=FREE_TIER_SUMMARY_LIMIT,
    can_compare_filings=True,
    can_export=False,
    can_save_summaries=True,
    watchlist_limit=20,
)

_PRO = Entitlements(
    plan=Plan.PRO,
    monthly_summary_limit=None,
    can_compare_filings=True,
    can_export=True,
    can_save_summaries=True,
    watchlist_limit=None,
)


def get_plan(user: User) -> Plan:
    """Resolve a user's plan. Stub: derived from ``is_pro`` until real tiers exist."""
    return Plan.PRO if getattr(user, "is_pro", False) else Plan.FREE


def get_entitlements(user: User) -> Entitlements:
    """Resolve a user's entitlements from their plan."""
    return _PRO if getattr(user, "is_pro", False) else _FREE

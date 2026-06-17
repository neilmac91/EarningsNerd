"""Entitlement resolution: subscription status is the source of truth, is_pro is the fallback."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.entitlements import Plan, get_entitlements, get_plan, is_pro_user


def _user(is_pro=False, subscription=None):
    # SimpleNamespace mimics the attribute access get_plan/get_entitlements rely on, without a DB.
    return SimpleNamespace(is_pro=is_pro, subscription=subscription)


def _sub(status, trial_end=None):
    return SimpleNamespace(status=status, trial_end=trial_end)


def test_free_user_has_free_entitlements():
    ent = get_entitlements(_user(is_pro=False))
    assert ent.plan is Plan.FREE
    assert ent.monthly_summary_limit == 5
    assert ent.can_export is False
    assert ent.can_compare_filings is True
    assert ent.watchlist_limit is None  # unlimited on free, by design
    assert ent.realtime_alerts is False
    assert ent.eightk_coverage is False
    assert ent.history_retention_days == 90
    assert ent.priority_model is False


def test_is_pro_mirror_grants_pro_when_no_subscription_row():
    ent = get_entitlements(_user(is_pro=True, subscription=None))
    assert ent.plan is Plan.PRO
    assert ent.monthly_summary_limit is None
    assert ent.can_export is True
    assert ent.realtime_alerts is True
    assert ent.eightk_coverage is True
    assert ent.history_retention_days is None
    assert ent.priority_model is True


def test_active_subscription_grants_pro_even_if_mirror_false():
    # Subscription is authoritative; a stale is_pro=False must not downgrade an active sub.
    assert get_plan(_user(is_pro=False, subscription=_sub("active"))) is Plan.PRO


def test_trialing_subscription_with_future_trial_is_pro():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert is_pro_user(_user(is_pro=False, subscription=_sub("trialing", future))) is True


def test_trialing_subscription_with_expired_trial_is_free():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert get_plan(_user(is_pro=True, subscription=_sub("trialing", past))) is Plan.FREE


def test_trialing_naive_datetime_is_treated_as_utc():
    # SQLite returns naive datetimes; must not raise and must compare correctly.
    future_naive = (datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None)
    assert is_pro_user(_user(subscription=_sub("trialing", future_naive))) is True


@pytest.mark.parametrize("status", ["canceled", "past_due", "incomplete"])
def test_inactive_subscription_is_free_even_if_mirror_true(status):
    # Once a sub row exists, it overrides the mirror — canceled/past_due/incomplete = free.
    assert get_plan(_user(is_pro=True, subscription=_sub(status))) is Plan.FREE

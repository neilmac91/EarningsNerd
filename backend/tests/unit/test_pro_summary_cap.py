"""Pro summary fair-use ceiling (PRO_SUMMARY_MONTHLY_CAP).

Pro is billing-unlimited (entitlements keep ``monthly_summary_limit=None`` — see
``test_entitlements``), but ``check_usage_limit`` still applies an INVISIBLE anti-abuse ceiling so a
single compromised/scripted account can't drive unbounded LLM spend. These tests pin that ceiling
without touching a DB by stubbing the usage counter and the settings value.
"""
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import subscription_service
from app.services.subscription_service import check_usage_limit


def _pro_user():
    # Active subscription → Pro; get_entitlements resolves monthly_summary_limit=None.
    return SimpleNamespace(id=1, is_pro=True, subscription=SimpleNamespace(status="active", trial_end=None))


def _free_user():
    return SimpleNamespace(id=2, is_pro=False, subscription=None)


@pytest.fixture
def stub_usage(monkeypatch):
    """Return a setter that fixes the monthly summary_count check_usage_limit reads."""
    def _set(count):
        monkeypatch.setattr(subscription_service, "get_user_usage_count", lambda uid, month, db: count)
    return _set


@pytest.mark.parametrize("count", [0, 5, 299])
def test_pro_under_cap_is_allowed_and_reports_unlimited(monkeypatch, stub_usage, count):
    monkeypatch.setattr(settings, "PRO_SUMMARY_MONTHLY_CAP", 300)
    stub_usage(count)
    can, current, limit = check_usage_limit(_pro_user(), db=None)
    assert can is True
    # Under the ceiling Pro still reports as unlimited (None) so no UI advertises the invisible cap.
    assert limit is None


@pytest.mark.parametrize("count", [300, 301, 999])
def test_pro_at_or_over_cap_is_blocked_with_cap_as_limit(monkeypatch, stub_usage, count):
    monkeypatch.setattr(settings, "PRO_SUMMARY_MONTHLY_CAP", 300)
    stub_usage(count)
    can, current, limit = check_usage_limit(_pro_user(), db=None)
    assert can is False
    assert current == count
    assert limit == 300  # the caller renders a generic message, never an upsell


def test_pro_cap_zero_disables_the_ceiling(monkeypatch, stub_usage):
    # 0 means "no ceiling" — truly unlimited, and it must not even hit the usage counter.
    monkeypatch.setattr(settings, "PRO_SUMMARY_MONTHLY_CAP", 0)
    called = {"n": 0}

    def _boom(uid, month, db):
        called["n"] += 1
        return 10_000

    monkeypatch.setattr(subscription_service, "get_user_usage_count", _boom)
    can, current, limit = check_usage_limit(_pro_user(), db=None)
    assert can is True
    assert limit is None
    assert called["n"] == 0  # short-circuited before counting


def test_free_cap_is_unchanged(monkeypatch, stub_usage):
    # Regression guard: the Free path still enforces the 5/mo billing cap exactly as before.
    monkeypatch.setattr(settings, "PRO_SUMMARY_MONTHLY_CAP", 300)
    stub_usage(5)
    can, current, limit = check_usage_limit(_free_user(), db=None)
    assert can is False
    assert limit == 5

    stub_usage(4)
    can, _, limit = check_usage_limit(_free_user(), db=None)
    assert can is True
    assert limit == 5

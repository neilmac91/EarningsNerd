"""Pure-logic tests for notification delivery evaluation + entitlement coercion."""
from types import SimpleNamespace

from app.services.notification_service import coerce_to_entitlement, evaluate_delivery


def _prefs(**over):
    base = dict(notify_10k=True, notify_10q=True, notify_8k=False, realtime=False)
    base.update(over)
    return SimpleNamespace(**base)


def _ent(realtime_alerts=False, eightk_coverage=False):
    return SimpleNamespace(realtime_alerts=realtime_alerts, eightk_coverage=eightk_coverage)


def test_free_10q_eligible_but_not_realtime():
    assert evaluate_delivery(_prefs(), _ent(), "10-Q") == (True, False)


def test_pro_10q_realtime_when_opted_in():
    eligible, realtime = evaluate_delivery(
        _prefs(realtime=True), _ent(realtime_alerts=True), "10-Q"
    )
    assert (eligible, realtime) == (True, True)


def test_pro_realtime_opted_out_falls_to_digest():
    assert evaluate_delivery(_prefs(realtime=False), _ent(realtime_alerts=True), "10-K") == (True, False)


def test_8k_requires_pro_coverage():
    # Free can't get 8-K even if the pref is on.
    assert evaluate_delivery(_prefs(notify_8k=True), _ent(eightk_coverage=False), "8-K") == (False, False)
    # Pro with the pref on does.
    assert evaluate_delivery(
        _prefs(notify_8k=True, realtime=True), _ent(realtime_alerts=True, eightk_coverage=True), "8-K"
    ) == (True, True)


def test_form_type_pref_off_suppresses():
    assert evaluate_delivery(_prefs(notify_10q=False), _ent(realtime_alerts=True), "10-Q") == (False, False)


def test_unknown_form_type_not_eligible():
    assert evaluate_delivery(_prefs(), _ent(), "S-1") == (False, False)


def test_coerce_forces_pro_toggles_off_for_free():
    prefs = _prefs(realtime=True, notify_8k=True)
    coerce_to_entitlement(prefs, _ent(realtime_alerts=False, eightk_coverage=False))
    assert prefs.realtime is False
    assert prefs.notify_8k is False


def test_coerce_leaves_pro_toggles_for_pro():
    prefs = _prefs(realtime=True, notify_8k=True)
    coerce_to_entitlement(prefs, _ent(realtime_alerts=True, eightk_coverage=True))
    assert prefs.realtime is True
    assert prefs.notify_8k is True

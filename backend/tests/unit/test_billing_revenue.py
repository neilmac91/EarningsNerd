"""Observed allocation evidence, conservative attribution and report/deletion semantics."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import BillingPayment, InviteCode, Subscription, User
from app.services import billing_revenue_service as revenue

PAID_AT = 1788739200
SINCE = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 1, tzinfo=timezone.utc)


def payment_event(payment_id="inpay_one", invoice_id="in_one", amount=3900, **changes):
    obj = {
        "object": "invoice_payment", "id": payment_id, "invoice": invoice_id,
        "amount_paid": amount, "currency": "usd", "livemode": True, "status": "paid",
        "payment": {"type": "payment_intent", "payment_intent": "pi_one"},
        "status_transitions": {"paid_at": PAID_AT},
    }
    obj.update(changes)
    return {"id": "evt_" + payment_id, "type": "invoice_payment.paid", "livemode": obj["livemode"],
            "api_version": "2026-08-26.dahlia", "data": {"object": obj}}


def invoice(invoice_id="in_one", customer="cus_one", subscription="sub_one", **changes):
    result = {
        "id": invoice_id, "object": "invoice", "customer": customer, "currency": "usd", "livemode": True,
        "parent": {"type": "subscription_details", "subscription_details": {"subscription": subscription}},
        "lines": {"has_more": False, "data": [{"pricing": {"price_details": {"price": "price_month"}}}]},
        # Deliberately unrelated cumulative values: allocation evidence must use neither.
        "amount_paid": 999999, "amount_due": 999999,
    }
    result.update(changes)
    return result


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def user(db, suffix="one", **changes):
    obj = User(email=f"{suffix}@example.test", stripe_customer_id=f"cus_{suffix}", **changes)
    db.add(obj)
    db.commit()
    return obj


def record(db, event, invoice_obj, owner):
    evidence = revenue.with_invoice(revenue.payment_from_event(event), invoice_obj)
    analytics = revenue.record_payment(db, evidence, owner)
    db.commit()
    return evidence, analytics


@pytest.mark.parametrize("amount", [-1, True, None, 1.5, "3900", 9223372036854775808])
def test_invalid_minor_units_are_rejected(amount):
    with pytest.raises(ValueError, match="amount_paid"):
        revenue.payment_from_event(payment_event(amount=amount))


@pytest.mark.parametrize("change", [
    {"currency": "USD"}, {"status": "open"}, {"object": "invoice"},
    {"invoice": ""}, {"livemode": 1}, {"status_transitions": {"paid_at": True}},
    {"payment": {"type": "payment_intent"}},
])
def test_invalid_payment_identity_is_rejected(change):
    with pytest.raises(ValueError):
        revenue.payment_from_event(payment_event(**change))


def test_canonical_event_mode_and_account_boundaries():
    for change in ({"type": "invoice.paid"}, {"livemode": False}, {"account": "acct_other"}):
        event = payment_event()
        event.update(change)
        with pytest.raises(ValueError):
            revenue.payment_from_event(event)


def test_invoice_shapes_and_price_classification(monkeypatch):
    monkeypatch.setattr(revenue.settings, "STRIPE_PRICE_MONTHLY_ID", "price_month")
    monkeypatch.setattr(revenue.settings, "STRIPE_PRICE_YEARLY_ID", "price_year")
    base = revenue.payment_from_event(payment_event(invoice={"id": "in_one"}))
    modern = revenue.with_invoice(base, invoice())
    assert (modern.subscription_id, modern.billing_cycle) == ("sub_one", "monthly")
    legacy = invoice(parent=None, subscription="sub_one", lines={"has_more": False, "data": [{"price": {"id": "price_year"}}]})
    assert revenue.with_invoice(base, legacy).billing_cycle == "yearly"
    for lines in ({"has_more": True, "data": invoice()["lines"]["data"]},
                  {"has_more": False, "data": [{"price": "price_year"}, {"price": "price_month"}]},
                  {"has_more": False, "data": []}):
        assert revenue.with_invoice(base, invoice(lines=lines)).billing_cycle is None
    with pytest.raises(ValueError, match="Conflicting"):
        revenue.with_invoice(base, {**invoice(), "subscription": "sub_other"})
    for change in ({"id": "in_other"}, {"currency": "eur"}, {"livemode": False}):
        with pytest.raises(ValueError, match="does not match"):
            revenue.with_invoice(base, invoice(**change))


def test_payment_id_deduplicates_distinct_events_and_rejects_conflicting_money(db):
    owner = user(db)
    evidence, analytics = record(db, payment_event(), invoice(), owner)
    assert analytics[0:2] == (str(owner.id), "invoice_payment_recorded")
    assert analytics[2]["amount_minor"] == 3900
    assert revenue.record_payment(db, replace(evidence, event_id="evt_retry"), owner) is None
    db.commit()
    assert db.query(BillingPayment).count() == 1
    assert db.query(BillingPayment).one().amount_minor == 3900
    with pytest.raises(ValueError, match="Conflicting immutable"):
        revenue.record_payment(db, replace(evidence, amount_minor=7800), owner)


@pytest.mark.parametrize("conflict", ["customer", "subscription", "unknown", "missing"])
def test_conflicted_or_unknown_attribution_never_creates_a_person(db, conflict):
    owner = user(db)
    second = user(db, "two")
    source = invoice()
    if conflict == "customer":
        second.stripe_customer_id = owner.stripe_customer_id
    elif conflict == "subscription":
        second.stripe_subscription_id = "sub_one"
    elif conflict == "unknown":
        source["customer"] = "cus_unknown"
    else:
        source["customer"] = None
    db.commit()
    _, analytics = record(db, payment_event(), source, None)
    row = db.query(BillingPayment).one()
    assert row.user_id is None and analytics is None
    assert row.stripe_customer_id is None and row.stripe_subscription_id is None
    assert row.is_beta_observed is None and row.invite_cohort_observed is None
    assert row.attribution == {
        "customer": "customer_conflict", "subscription": "subscription_conflict",
        "unknown": "unknown_customer", "missing": "missing_customer",
    }[conflict]
    report = revenue.payment_report(db, SINCE, UNTIL)
    assert report["currencies"][0]["observed_paying_users"] == 0
    assert report["first_observed_payment_cohorts"] == []


def test_payment_for_old_subscription_never_changes_current_entitlements(db):
    owner = user(db, is_beta=True, is_pro=False, stripe_subscription_id="sub_new")
    sub = Subscription(user_id=owner.id, stripe_customer_id="cus_one", stripe_subscription_id="sub_new", status="past_due", plan="free")
    db.add(sub)
    db.add(InviteCode(code_hash="a" * 64, cohort="beta_wave", user_id=owner.id, used_at=SINCE, expires_at=UNTIL))
    db.commit()
    _, analytics = record(db, payment_event(), invoice(), owner)
    assert (sub.stripe_subscription_id, sub.status, sub.plan, owner.is_pro) == ("sub_new", "past_due", "free", False)
    assert analytics[2]["is_beta_observed"] is True
    assert analytics[2]["invite_cohort_observed"] == "beta_wave"


def test_report_counts_allocations_not_invoice_totals_and_separates_all_exclusions(db):
    owner = user(db, is_beta=True)
    record(db, payment_event(amount=1000), invoice(), owner)
    record(db, payment_event("inpay_two", amount=2900), invoice(), owner)
    record(db, payment_event("inpay_zero", "in_zero", 0), invoice("in_zero"), owner)
    record(db, payment_event("inpay_external", "in_ext", 900, payment={"type": "payment_record"}), invoice("in_ext"), owner)
    record(db, payment_event("inpay_unknown_type", "in_unk", 800, payment={"type": "future_kind"}), invoice("in_unk"), owner)
    record(db, payment_event("inpay_manual", "in_man", 700), invoice("in_man", parent=None), owner)
    record(db, payment_event("inpay_test", "in_test", 3900, livemode=False), invoice("in_test", livemode=False), owner)
    record(db, payment_event("inpay_eur", "in_eur", 3900, currency="eur"), invoice("in_eur", currency="eur"), owner)
    record(db, payment_event("inpay_unlinked", "in_unlinked", 500), invoice("in_unlinked", customer="cus_missing"), None)
    report = revenue.payment_report(db, SINCE, UNTIL)
    eur, usd = report["currencies"]
    assert eur["currency"] == "eur" and eur["amount_minor"] == 3900
    assert usd == {"currency": "usd", "amount_minor": 4400, "payment_count": 3,
                   "unattributed_amount_minor": 500, "unattributed_payment_count": 1,
                   "nonzero_invoice_count": 2, "observed_paying_users": 1}
    assert report["excluded_payment_counts"] == {"zero_amount": 1, "unsupported_payment_type": 2, "non_subscription_invoice": 1}
    assert report["first_observed_payment_cohorts"] == [{"month": "2026-09", "is_beta_observed": True, "invite_cohort_observed": None, "users": 1}]
    assert revenue.payment_report(db, SINCE, UNTIL, livemode=False)["currencies"][0]["amount_minor"] == 3900
    assert "MRR or ARR" in report["limits"][0]


def test_first_observed_cohort_uses_paid_time_not_arrival_or_report_window(db):
    owner = user(db)
    late = payment_event("inpay_later", "in_later")
    record(db, late, invoice("in_later"), owner)
    earlier = deepcopy(late)
    earlier["id"] = "evt_earlier"
    earlier["data"]["object"].update(id="inpay_earlier", invoice="in_earlier", status_transitions={"paid_at": int(SINCE.timestamp()) - 1})
    record(db, earlier, invoice("in_earlier"), owner)
    assert revenue.payment_report(db, SINCE, UNTIL)["first_observed_payment_cohorts"] == []


def test_account_deletion_erases_attributed_observation_without_retained_cohort(db):
    owner = user(db)
    record(db, payment_event(), invoice(), owner)
    db.delete(owner)  # Same ORM deletion used by DELETE /api/users/me; no external service calls.
    db.commit()
    assert db.query(BillingPayment).count() == 0
    assert revenue.payment_report(db, SINCE, UNTIL)["currencies"] == []

"""Adversarial Stripe identity/delivery sequences; existing webhook contracts stay locked."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Subscription, User
from app.services.entitlements import get_plan
from app.services.subscription_sync import (
    apply_checkout_completed,
    apply_subscription_deleted,
    apply_subscription_upsert,
)
from app.utils.datetimes import utcnow


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, Subscription.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def _user(db, number=1, **kwargs):
    user = User(email=f"identity-{number}@example.com", email_verified=True, **kwargs)
    db.add(user)
    db.commit()
    return user


def _checkout(user, sub_id="sub_a", customer="cus_a"):
    return {"subscription": sub_id, "customer": customer, "metadata": {"user_id": str(user.id)}}


def _apply(db, handler, obj):
    result = handler(db, obj)
    db.commit()
    db.expire_all()
    return result


def _state(user):
    sub = user.subscription
    return (
        user.stripe_customer_id, user.stripe_subscription_id, user.is_pro,
        get_plan(user).value,
        (sub.stripe_customer_id, sub.stripe_subscription_id, sub.plan, sub.status,
         sub.trial_end, sub.current_period_end, sub.cancel_at_period_end) if sub else None,
    )


@pytest.mark.parametrize("binding", ["user", "subscription"])
def test_checkout_cannot_replace_an_established_customer(db, binding):
    user = _user(db)
    if binding == "user":
        user.stripe_customer_id = "cus_existing"
    else:
        db.add(Subscription(user_id=user.id, stripe_customer_id="cus_existing", status="canceled"))
    db.commit()
    db.expire_all()
    before = _state(user)
    _apply(db, apply_checkout_completed, _checkout(user, customer="cus_conflicting"))
    assert _state(user) == before


@pytest.mark.parametrize("binding", ["user", "subscription"])
@pytest.mark.parametrize("field", ["stripe_customer_id", "stripe_subscription_id"])
def test_checkout_cannot_take_another_users_billing_identity(db, binding, field):
    owner = _user(db, 1)
    target = _user(db, 2)
    value = "cus_a" if field == "stripe_customer_id" else "sub_a"
    if binding == "user":
        setattr(owner, field, value)
    else:
        db.add(Subscription(user_id=owner.id, status="canceled", **{field: value}))
    db.commit()
    db.expire_all()
    before = (_state(owner), _state(target))
    _apply(db, apply_checkout_completed, _checkout(target))
    assert (_state(owner), _state(target)) == before


@pytest.mark.parametrize("status", ["trialing", "past_due", "canceled"])
def test_checkout_after_subscription_event_preserves_authoritative_state(db, status):
    user = _user(db, stripe_customer_id="cus_a")
    future = int((utcnow() + timedelta(days=7)).timestamp())
    _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": status,
        "trial_end": future if status == "trialing" else None,
        "items": {"data": [{"current_period_end": future, "price": {"id": "price_a"}}]},
        "cancel_at_period_end": True,
    })
    before = _state(user)
    result = _apply(db, apply_checkout_completed, _checkout(user))
    assert _state(user) == before
    assert get_plan(user).value == ("pro" if status == "trialing" else "free")
    assert result is (user if status == "trialing" else None)


@pytest.mark.parametrize("old_status", ["canceled", "past_due", "trialing"])
@pytest.mark.parametrize("late_event", ["checkout", "deletion"])
def test_eligible_replacement_survives_old_checkout_and_deletion(db, old_status, late_event):
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": old_status,
        "trial_end": int((utcnow() - timedelta(days=1)).timestamp()) if old_status == "trialing" else None,
    })
    assert get_plan(user).value == "free"
    _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_b"))
    assert user.subscription.stripe_subscription_id == "sub_b"
    assert get_plan(user).value == "pro"
    before = _state(user)

    if late_event == "checkout":
        _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_a"))
    else:
        _apply(db, apply_subscription_deleted, {"id": "sub_a", "customer": "cus_a"})
    assert _state(user) == before  # neither old event may change entitled replacement B

    _apply(db, apply_subscription_deleted, {"id": "sub_b", "customer": "cus_a"})
    assert user.subscription.status == "canceled"
    assert user.stripe_subscription_id is None
    assert user.is_pro is False
    assert get_plan(user).value == "free"


@pytest.mark.parametrize("late_status", ["unpaid", "past_due", "canceled", "incomplete_expired", "trialing"])
@pytest.mark.parametrize("then", ["bound_update", "bound_deletion", "newer_active"])
def test_late_old_update_cannot_unbind_entitled_replacement(db, late_status, then):
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {"id": "sub_a", "customer": "cus_a", "status": "past_due"})
    _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_b"))
    assert get_plan(user).value == "pro"
    before = _state(user)

    result = _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": late_status,
        # A late-delivered trial update carries a trial that has since elapsed: not entitling.
        "trial_end": int((utcnow() - timedelta(days=1)).timestamp()) if late_status == "trialing" else None,
    })
    assert _state(user) == before  # old A's dunning outcome or a late retry may not rebind or revoke B
    assert result is None

    # The guard shields only an entitled binding from another subscription: B's own events and a
    # newer entitling subscription still apply.
    if then == "bound_update":
        _apply(db, apply_subscription_upsert, {"id": "sub_b", "customer": "cus_a", "status": "past_due"})
        expected = ("sub_b", "past_due", False, "free")
    elif then == "bound_deletion":
        _apply(db, apply_subscription_deleted, {"id": "sub_b", "customer": "cus_a"})
        expected = (None, "canceled", False, "free")
    else:
        _apply(db, apply_subscription_upsert, {"id": "sub_c", "customer": "cus_a", "status": "active"})
        expected = ("sub_c", "active", True, "pro")
    assert (user.stripe_subscription_id, user.subscription.status, user.is_pro, get_plan(user).value) == expected


def test_unentitled_account_still_binds_a_new_non_active_subscription(db):
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {"id": "sub_a", "customer": "cus_a", "status": "past_due"})
    assert get_plan(user).value == "free"
    _apply(db, apply_subscription_upsert, {"id": "sub_b", "customer": "cus_a", "status": "incomplete"})
    # Nothing entitled to protect: B binds, so its later events are current-ID and read Stripe.
    assert (user.stripe_subscription_id, user.subscription.status, get_plan(user).value) == (
        "sub_b", "incomplete", "free")

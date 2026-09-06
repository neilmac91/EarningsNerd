"""Canonical invoice-payment evidence and a read-only, explicitly limited cohort report.

The webhook worker owns the transaction. This module neither grants entitlements nor makes
Stripe calls. Amounts are allocations in currency minor units, never cumulative invoice totals.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BillingPayment, InviteCode, Subscription, User
from app.services.posthog_client import EVENT_INVOICE_PAYMENT_RECORDED
from app.utils.datetimes import iso_z

COLLECTED_PAYMENT_TYPES = frozenset({"payment_intent", "charge"})
REPORT_LIMITS = [
    "Gross observed Stripe payment allocations before refunds, credit-note adjustments, disputes, fees and tax adjustments; not net revenue, MRR or ARR.",
    "No currency conversion. Amounts remain integer minor units; currencies are never summed together.",
    "Coverage starts with observed events, not account inception. Missing events and historical payments are not backfilled.",
    "First-payment cohorts mean first observed qualifying payment, not a proven first lifetime purchase or churn measure.",
    "Off-Stripe/unknown payment types, zero amounts and non-subscription invoices are excluded from collected subscription totals.",
    "Unattributed qualifying payments contribute to gross totals but never to paying-user or cohort counts.",
    "Beta and invite labels reflect observation-time data. Missing or ambiguous labels remain unknown.",
    "Account deletion removes attributed observations; this report is not a retained accounting record.",
    "PostHog is best-effort telemetry; the database observations, including omissions, define this report.",
]


@dataclass(frozen=True)
class PaymentEvidence:
    payment_id: str
    invoice_id: str
    event_id: str
    api_version: Optional[str]
    amount_minor: int
    currency: str
    payment_type: str
    livemode: bool
    paid_at: datetime
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    billing_cycle: Optional[str] = None


def _identifier(value: object, name: str, *, optional: bool = False) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("id")
    if optional and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,255}", value):
        raise ValueError(f"Invalid {name}")
    return value


def _mapping(value: object, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {name} object")
    return value


def payment_from_event(event: dict) -> PaymentEvidence:
    """Validate only the canonical event, before any optional provider read or database work."""
    if event.get("type") != "invoice_payment.paid" or event.get("account"):
        raise ValueError("Expected an account-local invoice_payment.paid event")
    obj = _mapping(_mapping(event.get("data"), "event data").get("object"), "InvoicePayment")
    if obj.get("object") != "invoice_payment" or obj.get("status") != "paid":
        raise ValueError("Expected a paid InvoicePayment")
    amount = obj.get("amount_paid")
    if type(amount) is not int or not 0 <= amount <= 9223372036854775807:
        raise ValueError("Invalid payment amount_paid")
    currency = obj.get("currency")
    if not isinstance(currency, str) or not re.fullmatch("[a-z]{3}", currency):
        raise ValueError("Invalid payment currency")
    live = obj.get("livemode")
    if type(live) is not bool or event.get("livemode") is not live:
        raise ValueError("Inconsistent payment livemode")
    payment = _mapping(obj.get("payment"), "payment")
    kind = payment.get("type")
    if not isinstance(kind, str) or not re.fullmatch(r"[a-z_]{1,80}", kind):
        raise ValueError("Invalid payment type")
    if kind in COLLECTED_PAYMENT_TYPES:
        _identifier(payment.get(kind), "payment reference")
    timestamp = _mapping(obj.get("status_transitions"), "status transitions").get("paid_at")
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError("Invalid payment paid_at")
    try:
        paid_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Invalid payment paid_at") from exc
    api_version = event.get("api_version")
    if api_version is not None and (not isinstance(api_version, str) or len(api_version) > 80):
        raise ValueError("Invalid event api_version")
    return PaymentEvidence(
        payment_id=_identifier(obj.get("id"), "payment id"),
        invoice_id=_identifier(obj.get("invoice"), "invoice id"),
        event_id=_identifier(event.get("id"), "event id"),
        api_version=api_version, amount_minor=amount, currency=currency,
        payment_type=kind, livemode=live, paid_at=paid_at,
    )


def with_invoice(evidence: PaymentEvidence, invoice: dict) -> PaymentEvidence:
    """Validate provider identity; accept current and explicit legacy subscription references."""
    if (invoice.get("object") != "invoice" or invoice.get("id") != evidence.invoice_id
            or invoice.get("currency") != evidence.currency
            or invoice.get("livemode") is not evidence.livemode):
        raise ValueError("Invoice does not match payment evidence")
    parent = _mapping(invoice.get("parent"), "invoice parent")
    current = _mapping(parent.get("subscription_details"), "subscription details").get("subscription")
    current = _identifier(current, "invoice parent subscription", optional=True)
    legacy = _identifier(invoice.get("subscription"), "legacy invoice subscription", optional=True)
    if current and legacy and current != legacy:
        raise ValueError("Conflicting invoice subscription references")
    customer = _identifier(invoice.get("customer"), "invoice customer", optional=True)
    # Classification is advisory. Never substitute today's user's subscription/price for this invoice.
    prices = set()
    lines = _mapping(invoice.get("lines"), "invoice lines")
    data = lines.get("data")
    if data is not None and not isinstance(data, list):
        raise ValueError("Invalid invoice line data")
    if "has_more" in lines and type(lines["has_more"]) is not bool:
        raise ValueError("Invalid invoice lines has_more")
    if isinstance(data, list) and data:
        for line in data:
            line = _mapping(line, "invoice line")
            pricing = _mapping(line.get("pricing"), "invoice line pricing")
            modern = _mapping(pricing.get("price_details"), "invoice price details").get("price")
            price = modern or line.get("price")
            if isinstance(price, dict):
                price = price.get("id")
            prices.add(price if isinstance(price, str) else None)
    cycle = None
    if lines.get("has_more") is False and len(prices) == 1:
        price = next(iter(prices))
        monthly, yearly = settings.STRIPE_PRICE_MONTHLY_ID, settings.STRIPE_PRICE_YEARLY_ID
        if price and monthly != yearly:
            cycle = "monthly" if price == monthly else "yearly" if price == yearly else None
    return replace(evidence, customer_id=customer, subscription_id=current or legacy, billing_cycle=cycle)


def payment_attribution(db: Session, evidence: PaymentEvidence) -> tuple[Optional[int], str]:
    """Never use a first-match customer lookup for financial attribution."""
    if not evidence.customer_id:
        return None, "missing_customer"
    customers = {row[0] for row in db.query(User.id).filter(User.stripe_customer_id == evidence.customer_id)}
    customers.update(row[0] for row in db.query(Subscription.user_id).filter(
        Subscription.stripe_customer_id == evidence.customer_id))
    if len(customers) != 1:
        return None, "customer_conflict" if customers else "unknown_customer"
    owner = next(iter(customers))
    if evidence.subscription_id:
        subs = {row[0] for row in db.query(User.id).filter(User.stripe_subscription_id == evidence.subscription_id)}
        subs.update(row[0] for row in db.query(Subscription.user_id).filter(
            Subscription.stripe_subscription_id == evidence.subscription_id))
        if subs - {owner}:
            return None, "subscription_conflict"
    return owner, "attributed"


def _utc(value: datetime) -> datetime:
    # SQLite loses the timezone marker on a timezone-aware column; the stored value remains UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def record_payment(db: Session, evidence: PaymentEvidence, user: Optional[User]) -> Optional[tuple]:
    """Caller holds any attributed User lock and commits payment plus StripeEvent together."""
    existing = db.get(BillingPayment, (evidence.payment_id, evidence.livemode))
    if existing:
        if (existing.stripe_invoice_id, existing.amount_minor, existing.currency,
            existing.payment_type, _utc(existing.paid_at)) != (
            evidence.invoice_id, evidence.amount_minor, evidence.currency,
            evidence.payment_type, evidence.paid_at,
        ):
            raise ValueError("Conflicting immutable InvoicePayment evidence")
        return None
    owner, attribution = payment_attribution(db, evidence)
    if owner != (user.id if user else None):
        raise RuntimeError("Payment attribution changed; retry with a fresh account lock")
    cohort = None
    if user:
        invites = db.query(InviteCode.cohort).filter(
            InviteCode.user_id == user.id, InviteCode.used_at.isnot(None)).all()
        if len(invites) == 1:
            cohort = invites[0][0]
    payment = BillingPayment(
        stripe_payment_id=evidence.payment_id, livemode=evidence.livemode,
        stripe_invoice_id=evidence.invoice_id, source_event_id=evidence.event_id,
        source_api_version=evidence.api_version, amount_minor=evidence.amount_minor,
        currency=evidence.currency, payment_type=evidence.payment_type, paid_at=evidence.paid_at,
        subscription_invoice=bool(evidence.subscription_id), user_id=owner, attribution=attribution,
        stripe_customer_id=evidence.customer_id if user else None,
        stripe_subscription_id=evidence.subscription_id if user else None,
        is_beta_observed=bool(user.is_beta) if user else None, invite_cohort_observed=cohort,
        billing_cycle=evidence.billing_cycle,
    )
    db.add(payment)
    if not user:
        return None  # No fabricated person identity in PostHog.
    return (str(user.id), EVENT_INVOICE_PAYMENT_RECORDED, {
        "stripe_invoice_payment_id": evidence.payment_id, "stripe_invoice_id": evidence.invoice_id,
        "amount_minor": evidence.amount_minor, "currency": evidence.currency,
        "payment_type": evidence.payment_type, "livemode": evidence.livemode,
        "paid_at": iso_z(evidence.paid_at), "is_beta_observed": payment.is_beta_observed,
        "invite_cohort_observed": cohort, "billing_cycle": evidence.billing_cycle,
        "subscription_invoice": payment.subscription_invoice,
    })


def payment_report(db: Session, since: datetime, until: datetime, *, livemode: bool = True) -> dict:
    """Aggregate a bounded payment-time window without extrapolation or provider calls."""
    if since.tzinfo is None or until.tzinfo is None or since >= until:
        raise ValueError("Report requires an increasing timezone-aware [since, until) window")
    qualifying = (
        BillingPayment.livemode == livemode, BillingPayment.amount_minor > 0,
        BillingPayment.payment_type.in_(COLLECTED_PAYMENT_TYPES), BillingPayment.subscription_invoice.is_(True),
    )
    # One statement snapshot: a new user's payment can commit while a report is running.
    # A separate first-timestamp query would miss that user before the window query sees them.
    first = db.query(
        BillingPayment.user_id.label("owner_id"), func.min(BillingPayment.paid_at).label("first_paid_at"),
    ).filter(*qualifying, BillingPayment.user_id.isnot(None)).group_by(BillingPayment.user_id).subquery()
    currencies, excluded, cohorts = {}, defaultdict(int), defaultdict(set)
    first_labels = defaultdict(set)
    observations = 0
    for row, first_paid_at in db.query(BillingPayment, first.c.first_paid_at).outerjoin(
        first, BillingPayment.user_id == first.c.owner_id,
    ).filter(
        BillingPayment.livemode == livemode, BillingPayment.paid_at >= since, BillingPayment.paid_at < until,
    ).yield_per(500):
        observations += 1
        reason = ("zero_amount" if row.amount_minor == 0 else
                  "unsupported_payment_type" if row.payment_type not in COLLECTED_PAYMENT_TYPES else
                  "non_subscription_invoice" if not row.subscription_invoice else None)
        if reason:
            excluded[reason] += 1
            continue
        group = currencies.setdefault(row.currency, {
            "amount_minor": 0, "payment_count": 0, "invoices": set(), "users": set(),
            "unattributed_amount_minor": 0, "unattributed_payment_count": 0,
            "billing_cycles": {},
        })
        group["amount_minor"] += row.amount_minor
        group["payment_count"] += 1
        group["invoices"].add(row.stripe_invoice_id)
        cycle = group["billing_cycles"].setdefault(row.billing_cycle or "unknown", {"payments": 0, "invoices": set()})
        cycle["payments"] += 1
        cycle["invoices"].add(row.stripe_invoice_id)
        if row.user_id is None:
            group["unattributed_amount_minor"] += row.amount_minor
            group["unattributed_payment_count"] += 1
        else:
            group["users"].add(row.user_id)
            if _utc(row.paid_at) == _utc(first_paid_at):
                first_labels[(row.user_id, _utc(row.paid_at).strftime("%Y-%m"))].add(
                    (row.is_beta_observed, row.invite_cohort_observed))
    for (user_id, month), labels in first_labels.items():
        beta, invite = next(iter(labels)) if len(labels) == 1 else (None, None)
        cohorts[(month, beta, invite)].add(user_id)
    result_currencies = []
    for currency, group in sorted(currencies.items()):
        invoices, users = group.pop("invoices"), group.pop("users")
        cycles = group.pop("billing_cycles")
        result_currencies.append({"currency": currency, **group,
                                  "billing_cycle_counts": [
                                      {"billing_cycle": name, "payment_count": values["payments"],
                                       "invoice_count": len(values["invoices"])}
                                      for name, values in sorted(cycles.items())],
                                  "nonzero_invoice_count": len(invoices), "observed_paying_users": len(users)})
    # Coverage metadata is a later statement; it is not an atomic snapshot of the whole report.
    observed_from = db.query(func.min(BillingPayment.observed_at)).filter(BillingPayment.livemode == livemode).scalar()
    return {
        "since_inclusive": iso_z(since), "until_exclusive": iso_z(until), "livemode": livemode,
        "earliest_retained_observation": iso_z(_utc(observed_from)) if observed_from else None,
        "observations_in_window": observations, "excluded_payment_counts": dict(sorted(excluded.items())),
        "currencies": result_currencies,
        "first_observed_payment_cohorts": [
            {"month": key[0], "is_beta_observed": key[1], "invite_cohort_observed": key[2], "users": len(users)}
            for key, users in sorted(cohorts.items(), key=lambda item: str(item[0]))
        ],
        "limits": REPORT_LIMITS,
    }

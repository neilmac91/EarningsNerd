"""What the serving checkout charges for Pro: the bound Stripe Prices' amounts, never their IDs.

The pricing page shows ``PRO_PRICING`` (``frontend/app/pricing/prices.ts``); checkout charges the
Price that ``STRIPE_PRICE_MONTHLY_ID`` or ``STRIPE_PRICE_YEARLY_ID`` selects, and an operator sets
those on the service outside CI. Only this process holds both the bindings and the Stripe key, so it
reports what they charge, and the agreement check compares the report with the page
(``npm run check:pricing -- --serving``; ``docs/PRICING_OFFER.md``, "Machine checks"). The amounts
are the published offer, so the report is public. Price and Product IDs stay out of it: catalog
identifiers belong in the private operator receipt.

Stripe never changes a Price's amount or recurrence, and the bindings are fixed for a process, so a
report of two charges is kept for ``GOOD_TTL_SECONDS`` (an archived Price still shows within that);
anything less is read again after ``RETRY_TTL_SECONDS``. One read runs at a time, and no request waits
on another request's read: it gets the previous report, or "unavailable" when there is none. The
request that reads waits on Stripe itself, within the reader's connect and read limits. So however
much traffic the public route gets, a process reads Stripe at most once per expiry.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.config import settings
from app.services.stripe_subscription_reader import (
    SubscriptionReconciliationUnavailable,
    retrieve_price_snapshot,
)

logger = logging.getLogger(__name__)

CYCLES = ("monthly", "yearly")
GOOD_TTL_SECONDS = 600.0
RETRY_TTL_SECONDS = 60.0
_INTERVALS = frozenset({"day", "week", "month", "year"})
_CURRENCY = re.compile(r"[a-z]{3}")


def _charge(price: dict) -> dict:
    """The fixed amount one unit costs each period, or the reason the Price has none."""
    if price.get("active") is not True:
        return {"problem": "inactive"}
    if price.get("livemode") is not True:
        return {"problem": "test_mode"}
    recurring = price.get("recurring")
    amount = price.get("unit_amount")
    if (
        price.get("type") != "recurring"
        or price.get("billing_scheme") != "per_unit"
        or price.get("custom_unit_amount") is not None
        or price.get("transform_quantity") is not None
        or not isinstance(recurring, dict)
        or recurring.get("usage_type") != "licensed"
        or type(amount) is not int
        or amount < 0
    ):
        return {"problem": "not_fixed_recurring"}
    currency, interval, count = price.get("currency"), recurring.get("interval"), recurring.get("interval_count")
    if (
        not isinstance(currency, str)
        or not _CURRENCY.fullmatch(currency)
        or not isinstance(interval, str)
        or interval not in _INTERVALS
        or type(count) is not int
        or count < 1
    ):
        return {"problem": "not_fixed_recurring"}
    return {"amount_cents": amount, "currency": currency, "interval": interval, "interval_count": count}


def _read(cycle: str, price_id: str) -> dict:
    if not price_id:
        return {"problem": "unconfigured"}
    try:
        return _charge(retrieve_price_snapshot(price_id))
    except SubscriptionReconciliationUnavailable as exc:
        # The cause's type only: this line carries no provider text.
        logger.warning("Serving %s Price could not be read (%s)", cycle, type(exc.__cause__).__name__)
        return {"problem": "unavailable"}


@dataclass(frozen=True)
class _Report:
    bindings: tuple[str, str]
    expires: float
    charges: dict


class ServingPrices:
    """One process's report; the module docstring says when it reads Stripe."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._refresh = threading.Lock()
        self._report: _Report | None = None

    def _held(self, bindings: tuple[str, str]) -> _Report | None:
        report = self._report
        return report if report is not None and report.bindings == bindings else None

    def report(self) -> dict:
        bindings = (settings.STRIPE_PRICE_MONTHLY_ID, settings.STRIPE_PRICE_YEARLY_ID)
        held = self._held(bindings)
        if held is not None and self._clock() < held.expires:
            return held.charges
        if not self._refresh.acquire(blocking=False):
            return held.charges if held is not None else {cycle: {"problem": "unavailable"} for cycle in CYCLES}
        try:
            # Another request may have finished a read since the check above.
            held = self._held(bindings)
            if held is not None and self._clock() < held.expires:
                return held.charges
            charges = {cycle: _read(cycle, price_id) for cycle, price_id in zip(CYCLES, bindings)}
            good = all("amount_cents" in charge for charge in charges.values())
            ttl = GOOD_TTL_SECONDS if good else RETRY_TTL_SECONDS
            self._report = _Report(bindings, self._clock() + ttl, charges)
            return charges
        finally:
            self._refresh.release()


_serving_prices = ServingPrices()


def serving_pro_prices() -> dict:
    """Per cycle, what checkout charges for Pro now, or why it charges no fixed amount. Blocking."""
    return _serving_prices.report()

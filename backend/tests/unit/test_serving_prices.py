"""The serving-charge report: what checkout charges for Pro, read from the bound Prices (no IDs).

The agreement check compares this public report with the pricing page (docs/PRICING_OFFER.md,
"Machine checks"). Pinned here: the real SDK read goes through the bounded reader; only a fixed,
licensed, recurring, active live-mode Price reports an amount, and every other shape names its
problem; nothing in the report or the route's body is a Stripe identifier; a report of two charges
is kept for its TTL and anything less is retried sooner; and a request that arrives during a read
never waits on Stripe or starts a second read. No test reaches the network.
"""
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import main
from app.config import settings
from app.routers import subscriptions
from app.services import billing_serving_prices as serving
from app.services import stripe_subscription_reader as reader


def _price(cycle="monthly", **overrides):
    price = {
        "object": "price", "id": f"price_{cycle}", "product": "prod_pro", "active": True, "livemode": True,
        "currency": "usd", "type": "recurring", "billing_scheme": "per_unit", "custom_unit_amount": None,
        "transform_quantity": None, "unit_amount": 2500 if cycle == "monthly" else 24000,
        "unit_amount_decimal": "2500" if cycle == "monthly" else "24000",
        "recurring": {"interval": "month" if cycle == "monthly" else "year", "interval_count": 1, "usage_type": "licensed"},
    }
    price.update(overrides)
    return price


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def bound(monkeypatch):
    """Bindings set, a fresh report with a hand-moved clock, and a fake exact-ID Price read."""
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly")
    monkeypatch.setattr(settings, "STRIPE_PRICE_YEARLY_ID", "price_yearly")
    clock = _Clock()
    monkeypatch.setattr(serving, "_serving_prices", serving.ServingPrices(clock=clock))
    catalog = {"price_monthly": _price("monthly"), "price_yearly": _price("yearly")}
    read = Mock(side_effect=lambda price_id: catalog[price_id])
    monkeypatch.setattr(serving, "retrieve_price_snapshot", read)
    return SimpleNamespace(clock=clock, catalog=catalog, read=read)


AGREEING = {
    "monthly": {"amount_cents": 2500, "currency": "usd", "interval": "month", "interval_count": 1},
    "yearly": {"amount_cents": 24000, "currency": "usd", "interval": "year", "interval_count": 1},
}


def test_reports_each_bound_price_as_a_fixed_charge(bound):
    assert serving.serving_pro_prices() == AGREEING
    assert [call.args for call in bound.read.call_args_list] == [("price_monthly",), ("price_yearly",)]


@pytest.mark.parametrize("overrides,problem", [
    ({"active": False}, "inactive"),
    ({"livemode": False}, "test_mode"),
    ({"type": "one_time", "recurring": None}, "not_fixed_recurring"),
    ({"billing_scheme": "tiered", "unit_amount": None}, "not_fixed_recurring"),
    ({"custom_unit_amount": {"enabled": True}}, "not_fixed_recurring"),
    ({"transform_quantity": {"divide_by": 10, "round": "up"}}, "not_fixed_recurring"),
    ({"recurring": {"interval": "month", "interval_count": 1, "usage_type": "metered"}}, "not_fixed_recurring"),
    ({"recurring": None}, "not_fixed_recurring"),
    ({"unit_amount": None, "unit_amount_decimal": "2500.5"}, "not_fixed_recurring"),
    ({"unit_amount": 2500.0}, "not_fixed_recurring"),
    ({"unit_amount": True}, "not_fixed_recurring"),
    ({"unit_amount": "2500"}, "not_fixed_recurring"),
    ({"unit_amount": -1}, "not_fixed_recurring"),
    ({"currency": "USD"}, "not_fixed_recurring"),
    ({"currency": None}, "not_fixed_recurring"),
    ({"recurring": {"interval": "fortnight", "interval_count": 1, "usage_type": "licensed"}}, "not_fixed_recurring"),
    ({"recurring": {"interval": "month", "interval_count": 0, "usage_type": "licensed"}}, "not_fixed_recurring"),
    ({"recurring": {"interval": "month", "interval_count": "1", "usage_type": "licensed"}}, "not_fixed_recurring"),
    ({"recurring": {"interval": ["month"], "interval_count": 1, "usage_type": "licensed"}}, "not_fixed_recurring"),
    ({"recurring": {"interval": {"month": 1}, "interval_count": 1, "usage_type": "licensed"}}, "not_fixed_recurring"),
])
def test_a_price_without_one_fixed_charge_per_period_names_its_problem(bound, overrides, problem):
    bound.catalog["price_monthly"] = _price("monthly", **overrides)
    report = serving.serving_pro_prices()
    assert report["monthly"] == {"problem": problem}
    assert report["yearly"] == AGREEING["yearly"]


def test_a_charge_reports_its_own_recurrence_for_the_check_to_judge(bound):
    # The page's cycles are once a month and once a year; the check, not the report, decides that a
    # quarterly Price or a yearly Price bound as monthly disagrees with them.
    bound.catalog["price_monthly"] = _price("monthly", recurring={"interval": "month", "interval_count": 3, "usage_type": "licensed"})
    bound.catalog["price_yearly"] = _price("yearly", recurring={"interval": "month", "interval_count": 1, "usage_type": "licensed"})
    report = serving.serving_pro_prices()
    assert report["monthly"]["interval_count"] == 3
    assert report["yearly"]["interval"] == "month"


def test_an_unset_binding_is_unconfigured_without_a_stripe_read(bound, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_PRICE_YEARLY_ID", "")
    report = serving.serving_pro_prices()
    assert report["yearly"] == {"problem": "unconfigured"}
    assert [call.args for call in bound.read.call_args_list] == [("price_monthly",)]


def test_a_failed_read_is_unavailable_and_logs_no_provider_text(bound, caplog):
    def fail(price_id):
        try:
            raise RuntimeError("Invalid API Key provided: sk_live_SECRET")
        except RuntimeError as exc:
            raise reader.SubscriptionReconciliationUnavailable("Current Stripe price state is unavailable") from exc

    bound.read.side_effect = fail
    with caplog.at_level("WARNING", logger=serving.__name__):
        report = serving.serving_pro_prices()
    assert report == {"monthly": {"problem": "unavailable"}, "yearly": {"problem": "unavailable"}}
    assert "RuntimeError" in caplog.text
    assert "sk_live" not in caplog.text and "Invalid API Key" not in caplog.text


def test_two_charges_are_kept_for_the_good_ttl(bound):
    first = serving.serving_pro_prices()
    bound.clock.now += serving.GOOD_TTL_SECONDS - 1
    assert serving.serving_pro_prices() == first
    assert bound.read.call_count == 2
    bound.clock.now += 1
    serving.serving_pro_prices()
    assert bound.read.call_count == 4


def test_anything_less_than_two_charges_is_read_again_after_the_retry_ttl(bound):
    bound.catalog["price_yearly"] = _price("yearly", active=False)
    assert serving.serving_pro_prices()["yearly"] == {"problem": "inactive"}
    bound.clock.now += serving.RETRY_TTL_SECONDS - 1
    serving.serving_pro_prices()
    assert bound.read.call_count == 2
    bound.catalog["price_yearly"] = _price("yearly")
    bound.clock.now += 1
    assert serving.serving_pro_prices() == AGREEING
    assert bound.read.call_count == 4
    assert serving.RETRY_TTL_SECONDS < serving.GOOD_TTL_SECONDS


def test_new_bindings_are_read_at_once(bound, monkeypatch):
    serving.serving_pro_prices()
    bound.catalog["price_monthly_v2"] = _price("monthly", id="price_monthly_v2", unit_amount=2000)
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_v2")
    assert serving.serving_pro_prices()["monthly"]["amount_cents"] == 2000


def test_a_request_during_a_read_neither_waits_nor_reads_again(bound):
    entered, release = threading.Event(), threading.Event()
    real = bound.read.side_effect

    def slow(price_id):
        entered.set()
        assert release.wait(5)
        return real(price_id)

    bound.read.side_effect = slow
    results = []
    reading = threading.Thread(target=lambda: results.append(serving.serving_pro_prices()))
    reading.start()
    try:
        assert entered.wait(5)
        # Nothing held yet: "unavailable", at once, without touching Stripe.
        assert serving.serving_pro_prices() == {"monthly": {"problem": "unavailable"}, "yearly": {"problem": "unavailable"}}
        assert bound.read.call_count == 1
    finally:
        release.set()
        reading.join(5)
    assert results == [AGREEING]

    # With a report held but expired, a request during the refresh gets the held report.
    bound.clock.now += serving.GOOD_TTL_SECONDS
    entered.clear()
    release.clear()
    reading = threading.Thread(target=serving.serving_pro_prices)
    reading.start()
    try:
        assert entered.wait(5)
        assert serving.serving_pro_prices() == AGREEING
        assert bound.read.call_count == 3
    finally:
        release.set()
        reading.join(5)


def test_a_read_finished_between_the_check_and_the_lock_is_not_repeated(bound):
    serving.serving_pro_prices()
    bound.clock.now += serving.GOOD_TTL_SECONDS
    instance = serving._serving_prices
    real_clock, armed = instance._clock, [True]

    def clock():
        # This request has found the report stale; before it takes the lock, another request
        # completes a whole read.
        if armed[0]:
            armed[0] = False
            instance.report()
        return real_clock()

    instance._clock = clock
    reads = bound.read.call_count
    assert serving.serving_pro_prices() == AGREEING
    assert bound.read.call_count == reads + 2  # the other request's read only


def test_the_real_sdk_read_uses_the_bounded_reader(monkeypatch):
    """Real StripeClient/RequestsClient with a fake requests session: the URL, limits and identity."""
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_reader")
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS", 1.25)
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS", 2.5)
    response = SimpleNamespace(content=json.dumps(_price("monthly")).encode(), status_code=200, headers={})
    session = SimpleNamespace(request=Mock(return_value=response), close=Mock())
    real_transport, real_client = reader.stripe.RequestsClient, reader.stripe.StripeClient
    client_spy = Mock(side_effect=real_client)
    monkeypatch.setattr(reader.stripe, "RequestsClient", lambda **kwargs: real_transport(session=session, **kwargs))
    monkeypatch.setattr(reader.stripe, "StripeClient", client_spy)

    assert reader.retrieve_price_snapshot("price_monthly")["unit_amount"] == 2500
    assert session.request.call_args.args[:2] == ("get", "https://api.stripe.com/v1/prices/price_monthly")
    assert session.request.call_args.kwargs["timeout"] == (1.25, 2.5)
    assert client_spy.call_args.kwargs["max_network_retries"] == 0
    session.close.assert_called_once()

    # A readback of another Price is not this binding's evidence.
    response.content = json.dumps(_price("monthly", id="price_other")).encode()
    with pytest.raises(reader.SubscriptionReconciliationUnavailable):
        reader.retrieve_price_snapshot("price_monthly")
    assert session.close.call_count == 2


def test_the_public_route_carries_charges_and_problems_but_no_identifiers(bound, monkeypatch):
    bound.catalog["price_yearly"] = _price("yearly", active=False)
    hops = []
    real_hop = subscriptions.run_in_threadpool

    async def hop(func, *args, **kwargs):  # the Stripe read must stay off the event loop
        hops.append(func)
        return await real_hop(func, *args, **kwargs)

    monkeypatch.setattr(subscriptions, "run_in_threadpool", hop)
    response = TestClient(main.app).get("/api/subscriptions/prices")  # no credentials: public
    assert hops == [subscriptions.serving_pro_prices]
    assert response.status_code == 200
    assert response.json() == {"monthly": AGREEING["monthly"], "yearly": {"problem": "inactive"}}
    assert "price_" not in response.text and "prod_" not in response.text


def test_the_route_is_one_public_get():
    routes = [route for route in subscriptions.router.routes if getattr(route, "path", "") == "/prices"]
    assert len(routes) == 1 and routes[0].methods == {"GET"}
    assert routes[0].endpoint is subscriptions.get_serving_prices
    assert not routes[0].dependant.dependencies  # no auth or DB dependency
    assert "/api/subscriptions/prices" in main.app.openapi()["paths"]

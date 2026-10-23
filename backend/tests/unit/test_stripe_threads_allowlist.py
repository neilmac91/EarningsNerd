"""Gate for lessons/ops-stripe-calls-wait-on-threads-of-their-own.md: a call through stripe-python's
global client runs on the Stripe threads (``app/services/stripe_threads.py``), never on the event loop
or on anyio's default worker threads (E170).

The global client waits up to 80 s a call and retries twice (``stripe.max_network_retries``). On anyio's
default worker threads, 40 tokens a process that the auth lookups and every route's thread-pool units
also take, a Stripe brownout with 40 such calls in flight on one instance would hold every token.

One rule, two halves in this one module:

- Structure: the scan reads every module under ``app/`` through ``ast`` and lists each Stripe API
  operation it names: an attribute chain from the stripe module, under any name a module imports it or
  one of its members by, through a capitalized resource class to a lowercase method
  (``stripe.Customer.create``, ``stripe.billing_portal.Session.create``), called or passed.
  ``stripe.Webhook``'s methods check a signature locally, so they are not operations. A site passes when
  its chain is the first positional argument of a ``run_on_stripe_threads`` call. ``SITES`` names each
  other site by file, the outermost function holding it and its chain, with why; a new site fails until
  it is listed, and a listed site that is gone fails until its line is.
- Behaviour: 48 billing-portal sessions held inside Stripe take the eight Stripe threads and none of
  anyio's, so an unrelated usage read still answers while they wait.

Out of reach, so review holds them: an operation reached through a value rather than the module (a
result's own methods, such as a list's ``auto_paging_iter`` pages, and a ``StripeClient``'s services,
which ``stripe_subscription_reader.py`` bounds to seconds), a resource class held in a variable or
reached through ``getattr``, and a callable handed to ``run_on_stripe_threads`` that makes other Stripe
calls of its own.
"""

from __future__ import annotations

import ast
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from anyio.to_thread import current_default_thread_limiter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from main import app

BACKEND_DIR = Path(__file__).resolve().parents[2]

_DELETION = "the account deletion's, on the event loop until E171 moves its units and Stripe calls off it"
SITES: dict[tuple[str, str, str], str] = {
    ("app/routers/users.py", "delete_user_account", "stripe.Subscription.list"): _DELETION,
    ("app/routers/users.py", "delete_user_account", "stripe.Subscription.delete"): _DELETION,
}


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def stripe_operation_sites(source: str, file: str = "probe.py") -> list[tuple[str, str, str]]:
    """Each Stripe API operation ``source`` names off the Stripe threads, as (file, function, chain)."""
    tree = ast.parse(source)
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "stripe" or alias.name.startswith("stripe."):
                    # ``import stripe.checkout`` binds ``stripe``; with ``as``, the name is the submodule.
                    bound[alias.asname or "stripe"] = alias.name if alias.asname else "stripe"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and (
                node.module == "stripe" or node.module.startswith("stripe.")):
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def chain(node: ast.AST) -> str | None:
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name) and node.id in bound:
            return ".".join([bound[node.id], *reversed(parts)])
        return None

    def operation(path: str) -> bool:
        *owner, method = path.split(".")
        return len(owner) >= 2 and owner[-1][:1].isupper() and owner[-1] != "Webhook" and method[:1].islower()

    sites: list[tuple[str, str, str]] = []

    def visit(node: ast.AST, function: str, handed: ast.AST | None) -> None:
        for child in ast.iter_child_nodes(node):
            outer = function
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and function == "<module>":
                outer = child.name
            if isinstance(child, ast.Attribute) and (path := chain(child)) is not None:
                # A chain's own attributes are part of it, so the walk does not go inside.
                if operation(path) and child is not handed:
                    sites.append((file, outer, path))
                continue
            on_stripe_threads = (
                isinstance(child, ast.Call) and _tail(child.func) == "run_on_stripe_threads" and child.args)
            visit(child, outer, child.args[0] if on_stripe_threads else handed)

    visit(tree, "<module>", None)
    return sites


def test_every_stripe_call_off_the_stripe_threads_is_listed_with_its_reason():
    found: list[tuple[str, str, str]] = []
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        file = path.relative_to(BACKEND_DIR).as_posix()
        found.extend(stripe_operation_sites(path.read_text(encoding="utf-8"), file))
    new = sorted(set(found) - set(SITES))
    gone = sorted(set(SITES) - set(found))
    assert not new, (
        f"Stripe calls off the Stripe threads at {new}. Hand each to run_on_stripe_threads "
        "(lessons/ops-stripe-calls-wait-on-threads-of-their-own.md), or list it in SITES with the reason."
    )
    assert not gone, f"Listed sites no longer found: {gone}. Remove their lines."


def test_the_scan_reads_each_form_it_claims():
    probe = '''
import stripe
import stripe as billing
import stripe.checkout
from stripe import Customer
from stripe import billing_portal as portals
from stripe.checkout import Session as CheckoutSession

async def on_the_loop(customer_id):
    stripe.Customer.retrieve(customer_id)
    billing.Subscription.list(customer=customer_id).auto_paging_iter()
    Customer.create(email="payer@example.com")

async def default_threads(customer_id):
    await run_in_threadpool(stripe.checkout.Session.create, customer=customer_id)
    await run_in_threadpool(portals.Session.create, customer=customer_id)
    await run_on_stripe_threads(func=CheckoutSession.create, customer=customer_id)
    await run_on_stripe_threads(stripe.Customer.retrieve(customer_id).delete)

async def stripe_threads(customer_id):
    await run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    await run_on_stripe_threads(portals.Session.create, customer=customer_id)

def not_operations(payload, signature, secret):
    stripe.api_key = secret
    stripe.Webhook.construct_event(payload, signature, secret)
    client = stripe.StripeClient(secret, max_network_retries=0)
    client.v1.subscriptions.retrieve("sub_1")
    resource = stripe.Customer
    try:
        resource.create()
    except stripe.error.StripeError:
        pass

stripe.Subscription.delete("sub_2")
'''
    assert stripe_operation_sites(probe) == [
        ("probe.py", "on_the_loop", "stripe.Customer.retrieve"),
        ("probe.py", "on_the_loop", "stripe.Subscription.list"),
        ("probe.py", "on_the_loop", "stripe.Customer.create"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create"),
        ("probe.py", "default_threads", "stripe.billing_portal.Session.create"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve"),
        ("probe.py", "<module>", "stripe.Subscription.delete"),
    ]


@pytest.mark.asyncio
async def test_portal_sessions_held_in_stripe_leave_the_default_worker_threads_free(monkeypatch, tmp_path):
    """48 billing-portal sessions whose Stripe call does not return: each reaches Stripe, eight run on the
    eight Stripe threads while the rest wait for one, no Stripe call holds a default worker token, and an
    unrelated usage read answers before any of them returns; then all 48 answer 200."""
    import stripe

    from app.models import User
    from app.routers import auth

    # A slot for every request, so no unit waits for one: this case measures threads, not the pool (on four
    # slots, 44 lookups waiting for one would hold every default token that the slot holders need next).
    engine = create_engine(
        f"sqlite:///{tmp_path / 'stripe-threads.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=49,
        max_overflow=0,
        pool_timeout=5.0,
    )
    database.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(User(email="payer@example.com", is_active=True, email_verified=True, stripe_customer_id="cus_payer"))
        db.commit()

    release = threading.Event()
    lock = threading.Lock()
    in_stripe: list[str] = []
    reached = 0

    def held_in_stripe(**_: Any) -> SimpleNamespace:
        with lock:
            in_stripe.append(threading.current_thread().name)
        # Bounded, so a failing run still ends.
        assert release.wait(20), "the test never released Stripe"
        return SimpleNamespace(url="https://portal.stripe.test/s")

    class PortalSessions:
        @property
        def create(self):
            # Read on the loop as the route hands the call to its thread: one more session at Stripe.
            nonlocal reached
            reached += 1
            return held_in_stripe

    monkeypatch.setattr(stripe.billing_portal, "Session", PortalSessions())
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    headers = {"Authorization": f"Bearer {auth.create_access_token({'sub': 'payer@example.com'})}"}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    loop = asyncio.get_running_loop()

    async def call(method: str, path: str) -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            return await client.request(method, path)

    portals = [asyncio.ensure_future(call("POST", "/api/subscriptions/create-portal-session")) for _ in range(48)]
    try:
        deadline = loop.time() + 10
        while reached < 48 or len(in_stripe) < 8:
            assert loop.time() < deadline, (
                f"{reached} of 48 portal sessions reached Stripe and {len(in_stripe)} calls are in it: the calls "
                "held in Stripe keep the rest from their units")
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)
        assert len(in_stripe) == 8, f"{len(in_stripe)} Stripe calls ran at once, not the eight Stripe threads"
        assert current_default_thread_limiter().statistics().borrowed_tokens == 0
        usage = await asyncio.wait_for(call("GET", "/api/subscriptions/usage"), timeout=5)
        assert usage.status_code == 200, usage.text
        assert not release.is_set() and len(in_stripe) == 8
    finally:
        release.set()
        responses = await asyncio.gather(*portals, return_exceptions=True)
        engine.dispose()
    assert [getattr(response, "status_code", response) for response in responses] == [200] * 48
    assert len(in_stripe) == 48
    assert {name.rsplit("_", 1)[0] for name in in_stripe} == {"stripe_call"}

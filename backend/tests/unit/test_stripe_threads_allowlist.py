"""Gate for lessons/ops-stripe-calls-wait-on-threads-of-their-own.md: a call through stripe-python's
global client runs on the Stripe threads (``app/services/stripe_threads.py``), never on the event loop
or on anyio's default worker threads (E170).

The global client waits up to 80 s to connect and 80 s for each read, and retries twice
(``stripe.max_network_retries``). On anyio's default worker threads, 40 tokens a process that the auth
lookups and every route's thread-pool units also take, a Stripe brownout with 40 such calls in flight
on one instance would hold every token.

One rule, two halves in this one module:

- Structure: the scan reads every module under ``app/`` and the backend's top-level modules
  (``main.py``, ``task_worker_main.py``) through ``ast`` and lists each Stripe call it can see: an
  attribute chain from the stripe module, under any name a module imports it or one of its members by,
  through a capitalized resource class to a lowercase method (``stripe.Customer.create``,
  ``stripe.billing_portal.Session.create``), called or passed, and each ``auto_paging_iter()``,
  ``next_page()`` or ``previous_page()`` call, which fetches a list's other pages. ``stripe.Webhook``'s
  methods check a signature locally, so they are not calls. A call passes when its chain is the first
  positional argument of a ``run_on_stripe_threads`` call, or when it sits in a lambda that is that first
  argument or in a def that the module only ever hands, by name, as that first argument: the lambda or
  def then runs whole on the Stripe threads. ``SITES`` names each other call by file, the outermost
  function holding it, the call and its form (``called`` where it stands, ``handed to <callee>``,
  ``handed by keyword to <callee>``, or ``named``), with why. A new call fails until it is listed, a
  listed call that is gone or changed its form fails until its line is, and two calls with one key fail,
  since a line excuses one call.
- Behaviour: 48 billing-portal sessions held inside Stripe take the eight Stripe threads and none of
  anyio's, each in its request's context, so an unrelated usage read still answers while they wait.

Out of reach, so review holds them: a call reached through a value rather than the module (a result's
own methods other than ``auto_paging_iter``, and a ``StripeClient``'s services, such as
``stripe_subscription_reader.py``'s), a resource class held in a variable or reached through
``getattr``, a def handed through an attribute or a variable, and a def handed by name that something
calls through another name or from another module.
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
from app.services import logging_service
from main import app

BACKEND_DIR = Path(__file__).resolve().parents[2]

_DELETION = "the account deletion's, on the event loop until E171 hands its whole cancellation to the Stripe threads"
SITES: dict[tuple[str, str, str, str], str] = {
    ("app/routers/users.py", "delete_user_account", "stripe.Subscription.list", "called"): _DELETION,
    ("app/routers/users.py", "delete_user_account", "auto_paging_iter", "called"): _DELETION,
    ("app/routers/users.py", "delete_user_account", "stripe.Subscription.delete", "called"): _DELETION,
}

_ON_STRIPE_THREADS = "run_on_stripe_threads"
# A list's methods that fetch its other pages from Stripe.
_PAGE_METHODS = frozenset({"auto_paging_iter", "next_page", "previous_page"})


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def stripe_operation_sites(source: str, file: str = "probe.py") -> list[tuple[str, str, str, str]]:
    """Each Stripe call ``source`` makes off the Stripe threads, as (file, function, call, form)."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
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

    def handed(node: ast.AST) -> bool:
        call = parents.get(node)
        return (isinstance(call, ast.Call) and _tail(call.func) == _ON_STRIPE_THREADS
                and bool(call.args) and call.args[0] is node)

    # A def runs whole on the Stripe threads when every use of its name hands it there.
    handed_whole = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and handed(node)}
    handed_whole -= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and not handed(node)}

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

    def form(node: ast.AST) -> str:
        parent = parents.get(node)
        if isinstance(parent, ast.Call):
            return "called" if parent.func is node else f"handed to {_tail(parent.func)}"
        if isinstance(parent, ast.keyword) and isinstance(parents.get(parent), ast.Call):
            return f"handed by keyword to {_tail(parents[parent].func)}"
        return "named"

    sites: list[tuple[str, str, str, str]] = []

    def visit(node: ast.AST, function: str, whole: bool) -> None:
        for child in ast.iter_child_nodes(node):
            outer, inside = function, whole
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                outer = child.name if function == "<module>" else function
                inside = whole or child.name in handed_whole
            elif isinstance(child, ast.Lambda) and handed(child):
                inside = True
            if isinstance(child, ast.Attribute) and (path := chain(child)) is not None:
                # A chain's own attributes are part of it, so the walk does not go inside.
                if operation(path) and not inside and not handed(child):
                    sites.append((file, outer, path, form(child)))
                continue
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                    and child.func.attr in _PAGE_METHODS and not inside):
                sites.append((file, outer, child.func.attr, "called"))
            visit(child, outer, inside)

    visit(tree, "<module>", False)
    return sites


def test_every_stripe_call_off_the_stripe_threads_is_listed_with_its_reason():
    found: list[tuple[str, str, str, str]] = []
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")) + sorted(BACKEND_DIR.glob("*.py")):
        file = path.relative_to(BACKEND_DIR).as_posix()
        found.extend(stripe_operation_sites(path.read_text(encoding="utf-8"), file))
    new = sorted(site for site in found if site not in SITES)
    gone = sorted(set(SITES) - set(found))
    assert not new, (
        f"Stripe calls not handed to {_ON_STRIPE_THREADS} at {new}. Hand each call, or the def that makes it, "
        "to run_on_stripe_threads (lessons/ops-stripe-calls-wait-on-threads-of-their-own.md), or list it in "
        "SITES with the reason."
    )
    assert not gone, f"Listed calls no longer found in that form: {gone}. Remove their lines."
    shared = sorted({site for site in found if found.count(site) > 1})
    assert not shared, f"Listed calls that share a key: {shared}. A SITES line excuses one call; hand the others over."


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
    for subscription in billing.Subscription.list(customer=customer_id).auto_paging_iter():
        Customer.create(email="payer@example.com")

async def default_threads(customer_id):
    await run_in_threadpool(stripe.checkout.Session.create, customer=customer_id)
    await run_in_threadpool(portals.Session.create, customer=customer_id)
    await run_on_stripe_threads(func=CheckoutSession.create, customer=customer_id)
    await run_on_stripe_threads(stripe.Customer.retrieve(customer_id).delete)
    retrieve = stripe.Customer.retrieve

async def stripe_threads(customer_id):
    await run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    await run_on_stripe_threads(portals.Session.create, customer=customer_id)

    def cancel_all():
        for subscription in stripe.Subscription.list(customer=customer_id).auto_paging_iter():
            stripe.Subscription.delete(subscription.id)

    await run_on_stripe_threads(cancel_all)

def _cancel_one(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _also_on_the_loop(customer_id):
    stripe.Customer.retrieve(customer_id)

async def handed_whole(customer_id):
    await run_on_stripe_threads(_cancel_one, "sub_1")
    await run_on_stripe_threads(_also_on_the_loop, customer_id)
    _also_on_the_loop(customer_id)

async def lambdas_and_pages(customer_id, page):
    await run_on_stripe_threads(lambda: stripe.Customer.create(email="payer@example.com"))
    await run_on_stripe_threads(functools.partial(stripe.Customer.retrieve, customer_id))
    page.next_page()
    await run_on_stripe_threads(lambda: page.previous_page())

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
        ("probe.py", "on_the_loop", "stripe.Customer.retrieve", "called"),
        ("probe.py", "on_the_loop", "auto_paging_iter", "called"),
        ("probe.py", "on_the_loop", "stripe.Subscription.list", "called"),
        ("probe.py", "on_the_loop", "stripe.Customer.create", "called"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create", "handed to run_in_threadpool"),
        ("probe.py", "default_threads", "stripe.billing_portal.Session.create", "handed to run_in_threadpool"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create", "handed by keyword to run_on_stripe_threads"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve", "called"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve", "named"),
        ("probe.py", "_also_on_the_loop", "stripe.Customer.retrieve", "called"),
        ("probe.py", "lambdas_and_pages", "stripe.Customer.retrieve", "handed to partial"),
        ("probe.py", "lambdas_and_pages", "next_page", "called"),
        ("probe.py", "<module>", "stripe.Subscription.delete", "called"),
    ]


@pytest.mark.asyncio
async def test_portal_sessions_held_in_stripe_leave_the_default_worker_threads_free(monkeypatch, tmp_path):
    """48 billing-portal sessions whose Stripe call does not return: each reaches Stripe, eight run on the
    eight Stripe threads while the rest wait for one, no Stripe call holds a default worker token, and an
    unrelated usage read answers before any of them returns; then all 48 answer 200, each call having run
    in its own request's context (its correlation id)."""
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

    loop_thread = threading.get_ident()
    release = threading.Event()
    lock = threading.Lock()
    in_stripe: list[tuple[str, str | None]] = []
    reached = 0

    def held_in_stripe(**_: Any) -> SimpleNamespace:
        # On the loop, the wait below would freeze it, and every other session with it.
        assert threading.get_ident() != loop_thread, "a Stripe call ran on the event loop"
        with lock:
            in_stripe.append((threading.current_thread().name, logging_service.get_correlation_id()))
        # Bounded, so a failing run still ends.
        assert release.wait(20), "the test never released Stripe"
        return SimpleNamespace(url="https://portal.stripe.test/s")

    class PortalSessions:
        @property
        def create(self):
            # The route reads this on the loop as it hands the call over: one more session at Stripe.
            nonlocal reached
            reached += 1
            return held_in_stripe

    monkeypatch.setattr(stripe.billing_portal, "Session", PortalSessions())
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    token = auth.create_access_token({"sub": "payer@example.com"})
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def call(method: str, path: str, correlation_id: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}", "X-Correlation-ID": correlation_id}
        async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            return await client.request(method, path)

    portals = [asyncio.ensure_future(call("POST", "/api/subscriptions/create-portal-session", f"portal-{i}"))
               for i in range(48)]
    try:
        try:
            async with asyncio.timeout(10):  # a hang guard only; nothing below races it
                while reached < 48 or len(in_stripe) < 8:
                    await asyncio.sleep(0.01)
        except TimeoutError:
            answered = sorted({task.result().status_code for task in portals if task.done() and not task.exception()})
            if answered:
                why = f"some answered while Stripe held the others (statuses {answered})"
            elif reached < 48:
                why = "the calls held in Stripe keep the rest from their units"
            else:
                why = "fewer calls run at once than the eight Stripe threads"
            pytest.fail(f"{reached} of 48 portal sessions reached Stripe and {len(in_stripe)} calls are in it: {why}")
        await asyncio.sleep(0.1)
        assert len(in_stripe) == 8, f"{len(in_stripe)} Stripe calls ran at once, not the eight Stripe threads"
        assert current_default_thread_limiter().statistics().borrowed_tokens == 0
        usage = await asyncio.wait_for(call("GET", "/api/subscriptions/usage", "usage"), timeout=5)
        assert usage.status_code == 200, usage.text
        assert not release.is_set() and len(in_stripe) == 8
    finally:
        release.set()
        responses = await asyncio.gather(*portals, return_exceptions=True)
        engine.dispose()
    assert [getattr(response, "status_code", response) for response in responses] == [200] * 48
    assert {name.rsplit("_", 1)[0] for name, _ in in_stripe} == {"stripe_call"}
    assert sorted(correlation_id for _, correlation_id in in_stripe) == sorted(f"portal-{i}" for i in range(48))

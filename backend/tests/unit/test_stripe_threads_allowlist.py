"""Gate for lessons/ops-stripe-calls-wait-on-threads-of-their-own.md: a call through stripe-python's
global client runs on the Stripe threads (``app/services/stripe_threads.py``), never on the event loop
or on anyio's default worker threads (E170).

The global client waits up to 80 s to connect and 80 s for each read, and retries twice
(``stripe.max_network_retries``). On anyio's default worker threads, 40 tokens a process that the auth
lookups and every route's thread-pool units also take, a Stripe brownout with 40 such calls in flight
on one instance would hold every token.

One rule, two halves in this one module:

- Structure: the scan reads every module under ``app/`` and the backend's top-level modules (``main.py``,
  ``task_worker_main.py``) through ``ast`` and lists each Stripe call it can see: an attribute chain from the
  stripe module, under any name a module imports it or one of its members by, through a capitalized resource
  class to a lowercase method (``stripe.Customer.create``, ``stripe.billing_portal.Session.create``), called
  or passed, and each ``auto_paging_iter()``, ``next_page()``, ``previous_page()`` or
  ``next_search_result_page()`` call, which fetches a list's or a search's other pages. ``stripe.Webhook``'s
  methods check a signature locally, so they are not calls. A call passes when its chain is the first
  positional argument of a ``run_on_stripe_threads`` call, or when it sits in the body of a lambda that is
  that first argument, or of a plain def that the module only ever hands there by name: calling either runs
  its body on the Stripe threads. A generator def or lambda, an async def, a method and a decorated def do not
  count, since their bodies run where they are iterated, awaited or called, or as their decorator decides;
  neither do a def's decorators and a def's or lambda's defaults, which run where it is defined, nor a def or
  lambda nested in a handed body, which can be returned and called anywhere. In a handed body only a call made
  there counts: a Stripe method handed on or returned is called wherever it ends up, and a generator
  expression's element, conditions and later loops run wherever it is iterated. A walk counts only where it is
  used up in place: as a ``for`` loop's or a list, set or dict comprehension's iterable, or as a positional
  argument of a consumer (a builtin such as ``list``, ``sorted`` or ``sum`` by its bare name, ``_CONSUMERS``,
  or a ``join`` or ``deque`` method, as ``str.join`` and ``collections.deque``, ``_CONSUMER_METHODS``) or of a
  call that is itself used up in place (``for s in filter(live, walk)``). One returned, yielded, held or kept by
  any other call (``filter``, ``itertools.islice``, a container, a method sharing a builtin's name) fetches its
  later pages wherever it is iterated, and so does a ``*auto_paging_iter`` chain handed over itself. A page
  method handed over or named, not called where it stands, is listed in a handed body or not, except a
  ``next_page``, ``previous_page`` or ``next_search_result_page`` handed to ``run_on_stripe_threads`` itself,
  which fetches at once. At run time ``run_on_stripe_threads`` also refuses a generator, coroutine or async
  generator function, and a result that is a coroutine, an async generator or an iterator from stripe-python,
  the builtins or ``itertools``, any of which may hold a walk, so such work from a def the scan cannot read (one
  handed through an attribute) raises where a test drives it with stripe-python's own objects (a mock passes).
  The real-tree case fails on any call the scan lists: there is no allowlist. Its failure names each call by
  file, the outermost function holding it, the call and its form (``called`` where it stands,
  ``handed to <callee>``, ``handed by keyword to <callee>``, or ``named``), which ends with where the code around
  it runs: `` on the loop`` in an async def's own body; `` in <def>`` or `` in a lambda`` in the body of one
  inside that function, and `` in a generator expression`` in a generator expression's element, conditions or
  later loops; and nothing in a plain def's own body or at module level (``called on the loop``,
  ``called in cancel_billable``). No key records where its call runs: a def's or lambda's body runs wherever it
  is called, a generator expression's later parts and a walk's later pages wherever they are iterated, and a
  named or handed method wherever its taker calls it. So an allowlist line could go on excusing a call moved onto
  the loop, and an exception is a change to this gate, in review. The real-tree case also checks that it read
  the top-level modules, the billing and users routers, the helper and more than 250 modules, and that it sees
  the billing router's five calls and the account deletion's three once they are handed anywhere else, so it
  keeps a floor.
- Behaviour: 48 billing-portal sessions held inside Stripe take the eight Stripe threads and none of
  anyio's, each in its request's context, so an unrelated usage read still answers while they wait.

The planted forms score each rule both ways, and they mark what the scan cannot hold. Gaps, which break the
rule but pass, so review holds them, each planted in ``known_gaps`` where one module can show it: a result's
methods other than its page methods (``customer.delete()``), a resource class held in a variable or reached
through ``getattr``, a resource instance built from its class (``stripe.Subscription(sid).delete()``), the
stripe module held in a name or a parameter's default (``api = stripe``), a def handed by name that something
also calls through another name or from another module, a walk handed to a call used up in place that keeps it
rather than consuming it (``itertools.tee``), an async page method (``next_page_async``), which waits on the
loop and holds no thread, a consumer's builtin name rebound, or a ``join`` or ``deque`` method, that keeps a
walk lazy, and a callable that is named ``run_on_stripe_threads`` but is not the helper. Outside the rule: a
``StripeClient``'s services, which do not use the global client (``stripe_subscription_reader.py``'s keep the
default threads, for the reasons in the lesson), and other SDKs. Strict, so their writers rewrite them in place,
each planted in ``strict_forms`` or a def it hands: a walk held in a variable before a loop uses it up, a
generator expression of a walk handed to a consumer or looped over by a ``for``, a walk unpacked into a display
(``[*walk]``), a search result's ``next_page`` field, a string, read as a page method, a Stripe method or def
handed over through ``functools.partial(...)``, a def called in a handed lambda, and a def handed through a
variable or an attribute. A def defined in another module is listed there too, and so is a walk handed to a
function the scan does not know (``_cancel_each`` in ``lazy_wrappers``), whether that function uses it up or
not. A resource method that makes no request (``stripe.Subscription.construct_from``) is listed as well; it
belongs beside ``stripe.Webhook``'s in ``operation``'s exemptions.
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


_ON_STRIPE_THREADS = "run_on_stripe_threads"
# A list's or a search result's methods that fetch its other pages from Stripe.
_PAGE_METHODS = frozenset({"auto_paging_iter", "next_page", "previous_page", "next_search_result_page"})
# Builtins that use up an iterable handed to them where they stand, by their bare names, and the two methods that do
# (``str.join``, ``collections.deque``). Any other callee may keep a walk lazy (``filter``, ``map``,
# ``itertools.islice``, a container, a method sharing a builtin's name), so a walk handed to one is used up only
# where that call is.
_CONSUMERS = frozenset({"list", "tuple", "set", "frozenset", "dict", "sorted", "sum", "min", "max", "any", "all",
                        "next", "deque"})
_CONSUMER_METHODS = frozenset({"join", "deque"})


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _consumes(func: ast.AST) -> bool:
    return (isinstance(func, ast.Name) and func.id in _CONSUMERS) or (
        isinstance(func, ast.Attribute) and func.attr in _CONSUMER_METHODS)


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

    def own_nodes(function: ast.AST):
        """A def's or lambda's own body: not the defs, lambdas and classes inside it."""
        stack = list(function.body) if isinstance(function.body, list) else [function.body]
        while stack:
            node = stack.pop()
            yield node
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.extend(ast.iter_child_nodes(node))

    def generator(function: ast.AST) -> bool:
        return any(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in own_nodes(function))

    # A def's body runs on the Stripe threads when every use of its name hands it there and calling it runs the
    # body: not an async def or a generator, whose body runs where it is awaited or iterated, nor a method, nor a
    # decorated def, whose decorator decides what calling it does.
    defs = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    handed_whole = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and handed(node)}
    handed_whole -= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and not handed(node)}
    handed_whole -= {fn.name for fn in defs if isinstance(fn, ast.AsyncFunctionDef) or fn.decorator_list
                     or isinstance(parents.get(fn), ast.ClassDef) or generator(fn)}

    def used_up(call: ast.AST) -> bool:
        """Whether a walk's pages are fetched where it stands: a for loop's or a list, set or dict comprehension's
        iterable, or a positional argument of a consumer or of a call that is itself used up in place, as in
        ``for s in filter(live, walk)``. A walk returned, yielded, held or kept by another call is iterated
        elsewhere."""
        parent = parents.get(call)
        if isinstance(parent, ast.For) and parent.iter is call:
            return True
        if isinstance(parent, ast.comprehension) and parent.iter is call:
            return not isinstance(parents.get(parent), ast.GeneratorExp)
        return isinstance(parent, ast.Call) and call in parent.args and (_consumes(parent.func) or used_up(parent))

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

    def visit(node: ast.AST, function: str, inside: bool, within: str = "") -> None:
        """``inside``: the node runs on the Stripe threads, in the body of a lambda or def handed there.
        ``within``: where the code around the node runs, which ends the form of each call found there: `` on the
        loop`` in an async def's own body, `` in <def>`` or `` in a lambda`` in a body inside ``function``, and
        `` in a generator expression`` in a generator expression's later parts, which run wherever they are called
        or iterated, and nothing in a plain def's own body or at module level."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Its decorators and defaults run where it is defined; its body runs on the Stripe threads only if it
            # is handed there itself, since a def nested in a handed body can be returned and called anywhere.
            if isinstance(node, ast.Lambda):
                head, body, on_threads = [node.args], [node.body], handed(node) and not generator(node)
                nested = " in a lambda"
            else:
                outermost = function == "<module>"
                own = " on the loop" if isinstance(node, ast.AsyncFunctionDef) else ""
                nested = own if outermost else f" in {node.name}"
                function = node.name if outermost else function
                head = [*node.decorator_list, node.args, *([node.returns] if node.returns else [])]
                body, on_threads = node.body, node.name in handed_whole
            for part in head:
                visit(part, function, inside, within)
            for part in body:
                visit(part, function, on_threads, nested)
            return
        if isinstance(node, ast.GeneratorExp):
            # Only its first iterable is evaluated where it stands; the rest runs wherever it is iterated, off the
            # Stripe threads even in a handed body.
            first, *rest = node.generators
            visit(first.iter, function, inside, within)
            for part in [node.elt, first.target, *first.ifs, *rest]:
                visit(part, function, False, " in a generator expression")
            return
        if isinstance(node, ast.Attribute) and (path := chain(node)) is not None:
            # A chain's own attributes are part of it, so the walk does not go inside. In a handed body only a
            # call made there runs there: a chain handed on or returned is called wherever it ends up. A
            # ``*auto_paging_iter`` chain is a walk: handed over itself, or unused where it stands, it is
            # iterated elsewhere.
            called = isinstance(parents.get(node), ast.Call) and parents[node].func is node
            walk = path.endswith("auto_paging_iter")
            lazy = walk and (handed(node) or (inside and not used_up(parents.get(node))))
            if operation(path) and ((not inside and not handed(node)) or (inside and not called) or lazy):
                sites.append((file, function, path, form(node) + within))
            return
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _PAGE_METHODS
                and (not inside or (node.func.attr == "auto_paging_iter" and not used_up(node)))):
            sites.append((file, function, node.func.attr, "called" + within))
        if (isinstance(node, ast.Attribute) and node.attr in _PAGE_METHODS
                and not (isinstance(parents.get(node), ast.Call) and parents[node].func is node)
                and (node.attr == "auto_paging_iter" or not handed(node))):
            # A page method handed over or named, not called where it stands, in a handed body or not: called
            # elsewhere, a walk's later pages come wherever it is iterated, and another page wherever that call runs.
            sites.append((file, function, node.attr, form(node) + within))
        for child in ast.iter_child_nodes(node):
            visit(child, function, inside, within)

    visit(tree, "<module>", False)
    return sites


def test_every_stripe_call_runs_on_the_stripe_threads():
    paths = sorted((BACKEND_DIR / "app").rglob("*.py")) + sorted(BACKEND_DIR.glob("*.py"))
    files = [path.relative_to(BACKEND_DIR).as_posix() for path in paths]
    # The whole backend, not a corner of it: the top-level modules, the routers and the services.
    read = {"main.py", "task_worker_main.py", "app/routers/subscriptions.py", "app/routers/users.py",
            "app/services/stripe_threads.py"}
    assert read <= set(files), f"the scan did not read {sorted(read - set(files))}"
    assert len(files) > 250, f"the scan read only {len(files)} modules"
    found: list[tuple[str, str, str, str]] = []
    for path, file in zip(paths, files):
        found.extend(stripe_operation_sites(path.read_text(encoding="utf-8"), file))
    # It sees the real code's calls too, not just its files: handed anywhere else, the billing router's five and the
    # account deletion's three are listed.
    for module, calls in (("app/routers/subscriptions.py", 5), ("app/routers/users.py", 3)):
        source = (BACKEND_DIR / module).read_text(encoding="utf-8")
        elsewhere = stripe_operation_sites(source.replace("run_on_stripe_threads(", "run_in_threadpool("))
        assert len(elsewhere) >= calls, f"the scan sees {len(elsewhere)} of {module}'s {calls} Stripe calls"
    assert not found, (
        f"Stripe calls not handed to {_ON_STRIPE_THREADS} at {sorted(found)}. Hand each call to run_on_stripe_threads, "
        "or a plain def that makes it, defined in the module that hands it and used nowhere but there, by name; in a "
        "def or lambda handed there, call each Stripe method in its body and finish each walk in place, in a for loop, "
        "a list, set or dict comprehension, or list(...) (lessons/ops-stripe-calls-wait-on-threads-of-their-own.md). "
        "There is no allowlist: no key records where its call runs, so an exception is a change to this gate, and a "
        "method that makes no request goes beside stripe.Webhook's in operation()'s exemptions."
    )


def test_the_scan_reads_each_form_it_claims():
    probe = '''
import stripe
import stripe as billing
import stripe.checkout
from stripe import Customer
from stripe import billing_portal as portals
from stripe.checkout import Session as CheckoutSession
from .stripe import Charge as LocalCharge
import stripe_fixtures
import stripe_fixtures as fixtures
from stripe_fixtures import Customer as FixtureCustomer

async def on_the_loop(customer_id):
    stripe.Customer.retrieve(customer_id)
    for subscription in billing.Subscription.list(customer=customer_id).auto_paging_iter():
        Customer.create(email="payer@example.com")

async def default_threads(customer_id):
    await run_in_threadpool(stripe.checkout.Session.create, customer=customer_id)
    await run_in_threadpool(portals.Session.create, customer=customer_id)
    await run_on_stripe_threads(func=CheckoutSession.create, customer=customer_id)
    await run_on_stripe_threads(stripe.Customer.retrieve(customer_id).delete)
    await run_on_stripe_threads(functools.partial, stripe.Customer.retrieve, customer_id)
    retrieve = stripe.Customer.retrieve

async def default_thread_units(customer_id):
    def cancel_billable():
        for subscription in stripe.Subscription.list(customer=customer_id).auto_paging_iter():
            stripe.Subscription.delete(subscription.id)
    await run_in_threadpool(cancel_billable)
    subscriptions = await run_in_threadpool(lambda: stripe.Subscription.list(customer=customer_id))
    for subscription in subscriptions.auto_paging_iter():
        await run_in_threadpool(lambda: stripe.Subscription.delete(subscription.id))
    await run_in_threadpool(
        list, (stripe.Subscription.delete(s.id) for s in stripe.Subscription.list().auto_paging_iter()))

async def stripe_threads(customer_id):
    await run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    await run_on_stripe_threads(portals.Session.create, customer=customer_id)

    def cancel_all():
        for subscription in stripe.Subscription.list(customer=customer_id).auto_paging_iter():
            stripe.Subscription.delete(subscription.id)
        for subscription in filter(None, stripe.Subscription.list(customer=customer_id).auto_paging_iter()):
            stripe.Subscription.delete(subscription.id)

    await run_on_stripe_threads(cancel_all)
    await stripe_threads.run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    await run_on_stripe_threads(lambda: sorted(map(str, stripe.Customer.search_auto_paging_iter(query="q"))))
    await run_on_stripe_threads(lambda: list(stripe.Subscription.list(customer=customer_id).auto_paging_iter()))
    await run_on_stripe_threads(lambda: sorted(s.id for s in stripe.Subscription.list(customer=customer_id).data))
    await run_on_stripe_threads(lambda: {s.id for s in stripe.Subscription.list().auto_paging_iter()})
    await run_on_stripe_threads(lambda: {s.id: s for s in stripe.Subscription.list().auto_paging_iter()})

def _cancel_one(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _with_a_nested_generator(customer_id):
    def ids(items):
        yield from items
    async def later_ids(items):
        yield items
    stripe.Customer.retrieve(customer_id)

def _with_a_generator_lambda(customer_id):
    later = lambda: (yield None)
    stripe.Customer.retrieve(customer_id)

def _with_a_decorated_helper(customer_id):
    @cached(stripe.Customer.retrieve(customer_id))
    def helper():
        return None
    return helper

def _annotated(subscription_id) -> stripe.Customer.retrieve("cus_1"):
    stripe.Subscription.delete(subscription_id)

def _also_on_the_loop(customer_id):
    stripe.Customer.retrieve(customer_id)

def _also_on_the_default_threads(customer_id):
    stripe.Customer.retrieve(customer_id)

def _also_held(customer_id):
    stripe.Customer.retrieve(customer_id)

def _also_at_a_later_slot(customer_id):
    stripe.Customer.retrieve(customer_id)

async def handed_whole(customer_id):
    await run_on_stripe_threads(_cancel_one, "sub_1")
    await run_on_stripe_threads(_with_a_nested_generator, customer_id)
    await run_on_stripe_threads(_with_a_generator_lambda, customer_id)
    await run_on_stripe_threads(_with_a_decorated_helper, customer_id)
    await run_on_stripe_threads(_annotated, "sub_1")
    await run_on_stripe_threads(_also_on_the_loop, customer_id)
    _also_on_the_loop(customer_id)
    await run_on_stripe_threads(_also_on_the_default_threads, customer_id)
    await run_in_threadpool(_also_on_the_default_threads, customer_id)
    await run_on_stripe_threads(_also_held, customer_id)
    kept = _also_held
    await run_on_stripe_threads(_also_at_a_later_slot, customer_id)
    await run_on_stripe_threads(functools.partial, _also_at_a_later_slot, customer_id)

async def lambdas_and_pages(customer_id, page):
    await run_on_stripe_threads(lambda: stripe.Customer.create(email="payer@example.com"))
    page.next_page()
    await run_on_stripe_threads(lambda: page.previous_page())

def _pages_lazily(customer_id):
    return stripe.Subscription.list(customer=customer_id).auto_paging_iter()

def _live_subscriptions(customer_id):
    for subscription in stripe.Subscription.list(customer=customer_id).auto_paging_iter():
        yield subscription

async def _cancel_later(subscription_id):
    stripe.Subscription.delete(subscription_id)

class Billing:
    def cancel(self, subscription_id):
        stripe.Subscription.delete(subscription_id)

def _with_a_default(subscription_id, customer=stripe.Customer.retrieve("cus_1")):
    stripe.Subscription.delete(subscription_id)

async def lazy_walks(customer_id, page):
    await run_on_stripe_threads(_pages_lazily, customer_id)
    await run_on_stripe_threads(_live_subscriptions, customer_id)
    await run_on_stripe_threads(_cancel_later, "sub_1")
    await run_on_stripe_threads(cancel, "sub_1")
    await run_on_stripe_threads(_with_a_default, "sub_1")
    await run_on_stripe_threads(lambda: page.auto_paging_iter())
    await run_on_stripe_threads(lambda: [item for item in page.auto_paging_iter()])
    await run_on_stripe_threads(stripe.Customer.search_auto_paging_iter, query="email:'payer@example.com'")
    await run_on_stripe_threads(lambda: functools.partial(stripe.Customer.retrieve, customer_id))

async def page_methods_handed(page, subscriptions):
    await run_on_stripe_threads(subscriptions.auto_paging_iter)
    await run_in_threadpool(subscriptions.next_page)
    await run_on_stripe_threads(page.next_page)
    await run_on_stripe_threads(lambda: (stripe.Subscription.delete(s) for s in page.data))
    await run_on_stripe_threads(lambda: [stripe.Subscription.delete(s) for s in page.data])

def _nested_helper(customer_id):
    def retrieve():
        return stripe.Invoice.retrieve(customer_id)
    return retrieve

def _from_a_walk(customer_id):
    yield from stripe.Invoice.list(customer=customer_id).auto_paging_iter()

@cached(stripe.Price.retrieve("price_1"))
def _decorated(subscription_id):
    stripe.Subscription.delete(subscription_id)

async def nested_and_lazy(customer_id, page):
    await run_on_stripe_threads(_nested_helper, customer_id)
    await run_on_stripe_threads(_from_a_walk, customer_id)
    await run_on_stripe_threads(_decorated, "sub_1")
    await run_on_stripe_threads(lambda customer=stripe.Coupon.retrieve("co_1"): customer.id)
    await run_on_stripe_threads(lambda: lambda: stripe.Product.retrieve("prod_1"))
    await run_on_stripe_threads(lambda: (yield stripe.Plan.retrieve("plan_1")))
    await run_in_threadpool(lambda: stripe.Refund.create(charge="ch_1"))
    await run_on_stripe_threads(lambda: (s.id for s in page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: (s for s in page.data if stripe.Payout.retrieve(s)))
    await run_on_stripe_threads(lambda: (t for s in page.data for t in stripe.Transfer.list(destination=s)))
    await run_on_stripe_threads(lambda: stripe.Charge.search_auto_paging_iter(query="q"))
    await run_on_stripe_threads(lambda: functools.partial(page.previous_page))

async def walks_by_keyword(page):
    await run_on_stripe_threads(lambda: dict(pages=page.auto_paging_iter()))

def _next_page_later(page):
    return page.next_page

async def page_method_returned(page):
    await run_on_stripe_threads(_next_page_later, page)

async def lazy_wrappers(page):
    await run_on_stripe_threads(lambda: filter(None, stripe.Invoice.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: itertools.islice(stripe.Price.search_auto_paging_iter(query="q"), 10))
    await run_on_stripe_threads(lambda: {"live": map(str, stripe.Product.search_auto_paging_iter(query="q"))})
    await run_on_stripe_threads(lambda: _cancel_each(stripe.Subscription.search_auto_paging_iter(query="q")))

async def wrapped_page(page):
    await run_on_stripe_threads(lambda: filter(None, page.auto_paging_iter()))

async def more_wrappers(ids):
    await run_on_stripe_threads(lambda: zip(ids, stripe.Invoice.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: enumerate(stripe.Price.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: itertools.chain(ids, stripe.Product.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: iter(stripe.Customer.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: reversed(stripe.Charge.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: functools.partial(list, stripe.Subscription.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: itertools.tee(stripe.PaymentIntent.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: islice(stripe.Invoice.search_auto_paging_iter(query="q"), 10))
    await run_on_stripe_threads(lambda: chain(ids, stripe.Price.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: tee(stripe.Product.search_auto_paging_iter(query="q")))
    await run_on_stripe_threads(lambda: partial(list, stripe.Customer.search_auto_paging_iter(query="q")))

def _cancel_second(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _held(customer_id):
    subscriptions = stripe.Subscription.list(customer=customer_id).auto_paging_iter()
    return {"subscriptions": subscriptions}

async def held_and_returned(customer_id):
    await run_on_stripe_threads(_held, customer_id)
    await run_on_stripe_threads(lambda: stripe.Customer.retrieve)
    await run_on_stripe_threads(functools.partial, lambda: stripe.Subscription.delete("sub_1"))
    await run_on_stripe_threads(functools.partial, _cancel_second, "sub_1")
    await run_on_stripe_threads(func=lambda: stripe.Refund.retrieve("re_1"))

async def consumers(page):
    await run_on_stripe_threads(lambda: tuple(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: set(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: frozenset(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: dict(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: sum(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: min(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: max(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: any(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: all(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: next(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: ",".join(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: deque(page.auto_paging_iter(), maxlen=0))
    await run_on_stripe_threads(lambda: collections.deque(page.auto_paging_iter(), maxlen=0))

async def shared_names(page):
    await run_on_stripe_threads(lambda: _PENDING.set(page.auto_paging_iter()))

async def search_pages(search):
    search.next_search_result_page()
    await run_on_stripe_threads(search.next_search_result_page)

# Strict: the scan lists each of these, though none makes a Stripe request off the Stripe threads; its writer rewrites
# it in place, or puts a method that makes no request (construct_from) beside stripe.Webhook's in operation().
def _walk_then_loop(customer_id):
    subscriptions = stripe.Subscription.list(customer=customer_id).auto_paging_iter()
    for subscription in subscriptions:
        stripe.Subscription.delete(subscription.id)

def _loop_over_a_genexp(page):
    for subscription in (s for s in page.auto_paging_iter() if s.status == "active"):
        stripe.Subscription.delete(subscription.id)

def _through_a_variable(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _through_an_attribute(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _through_partial(subscription_id):
    stripe.Subscription.delete(subscription_id)

def _called_in_a_lambda(subscription_id):
    stripe.Subscription.delete(subscription_id)

async def strict_forms(search, page):
    await run_on_stripe_threads(_walk_then_loop, "cus_1")
    await run_on_stripe_threads(_loop_over_a_genexp, page)
    await run_on_stripe_threads(lambda: any(s.status for s in stripe.Charge.list().auto_paging_iter()))
    await run_on_stripe_threads(lambda: [*page.auto_paging_iter()])
    token = search.next_page
    deferred = _through_a_variable
    await run_on_stripe_threads(deferred, "sub_1")
    await run_on_stripe_threads(billing_helpers._through_an_attribute, "sub_1")
    await run_on_stripe_threads(functools.partial(stripe.Customer.retrieve, "cus_1"))
    await run_on_stripe_threads(functools.partial(_through_partial, "sub_1"))
    await run_on_stripe_threads(lambda: _called_in_a_lambda("sub_1"))
    stripe.Subscription.construct_from({"id": "sub_1"}, "sk_test")

# Gaps: each of these breaks the rule, but the scan passes it; the header names each, and review holds them.
def _cancel_aliased(subscription_id):
    stripe.Subscription.delete(subscription_id)

async def known_gaps(customer_id, page, payments=stripe):
    customer = await run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    customer.delete()
    resource = stripe.Customer
    resource.create()
    getattr(stripe, "Customer").create()
    await run_on_stripe_threads(_cancel_aliased, "sub_1")
    globals()["_cancel_aliased"]("sub_2")
    await run_on_stripe_threads(lambda: [walk for walk in itertools.tee(page.auto_paging_iter())])
    await page.next_page_async()
    list = filter
    await run_on_stripe_threads(lambda: list(None, page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: pending.join(page.auto_paging_iter()))
    await run_on_stripe_threads(lambda: pending.deque(page.auto_paging_iter()))
    await other_helpers.run_on_stripe_threads(stripe.Customer.retrieve, customer_id)
    stripe.Subscription("sub_1").delete()
    api = stripe
    api.Subscription.delete("sub_1")
    payments.Subscription.delete("sub_2")

def not_operations(payload, signature, secret, subscription):
    stripe.api_key = secret
    stripe.Webhook.construct_event(payload, signature, secret)
    client = stripe.StripeClient(secret, max_network_retries=0)
    client.v1.subscriptions.retrieve("sub_1")
    try:
        assert subscription.object == stripe.Subscription.OBJECT_NAME
        stripe.util.convert_to_stripe_object({})
        LocalCharge.create()
        stripe_fixtures.Customer.create()
        fixtures.Customer.create()
        FixtureCustomer.create()
    except stripe.error.StripeError:
        pass

stripe.Subscription.delete("sub_2")
'''
    assert stripe_operation_sites(probe) == [
        ("probe.py", "on_the_loop", "stripe.Customer.retrieve", "called on the loop"),
        ("probe.py", "on_the_loop", "auto_paging_iter", "called on the loop"),
        ("probe.py", "on_the_loop", "stripe.Subscription.list", "called on the loop"),
        ("probe.py", "on_the_loop", "stripe.Customer.create", "called on the loop"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create",
         "handed to run_in_threadpool on the loop"),
        ("probe.py", "default_threads", "stripe.billing_portal.Session.create",
         "handed to run_in_threadpool on the loop"),
        ("probe.py", "default_threads", "stripe.checkout.Session.create",
         "handed by keyword to run_on_stripe_threads on the loop"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve", "called on the loop"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve", "handed to run_on_stripe_threads on the loop"),
        ("probe.py", "default_threads", "stripe.Customer.retrieve", "named on the loop"),
        ("probe.py", "default_thread_units", "auto_paging_iter", "called in cancel_billable"),
        ("probe.py", "default_thread_units", "stripe.Subscription.list", "called in cancel_billable"),
        ("probe.py", "default_thread_units", "stripe.Subscription.delete", "called in cancel_billable"),
        ("probe.py", "default_thread_units", "stripe.Subscription.list", "called in a lambda"),
        ("probe.py", "default_thread_units", "auto_paging_iter", "called on the loop"),
        ("probe.py", "default_thread_units", "stripe.Subscription.delete", "called in a lambda"),
        ("probe.py", "default_thread_units", "auto_paging_iter", "called on the loop"),
        ("probe.py", "default_thread_units", "stripe.Subscription.list", "called on the loop"),
        ("probe.py", "default_thread_units", "stripe.Subscription.delete", "called in a generator expression"),
        ("probe.py", "_annotated", "stripe.Customer.retrieve", "called"),
        ("probe.py", "_also_on_the_loop", "stripe.Customer.retrieve", "called"),
        ("probe.py", "_also_on_the_default_threads", "stripe.Customer.retrieve", "called"),
        ("probe.py", "_also_held", "stripe.Customer.retrieve", "called"),
        ("probe.py", "_also_at_a_later_slot", "stripe.Customer.retrieve", "called"),
        ("probe.py", "lambdas_and_pages", "next_page", "called on the loop"),
        ("probe.py", "_pages_lazily", "auto_paging_iter", "called"),
        ("probe.py", "_live_subscriptions", "auto_paging_iter", "called"),
        ("probe.py", "_live_subscriptions", "stripe.Subscription.list", "called"),
        ("probe.py", "_cancel_later", "stripe.Subscription.delete", "called on the loop"),
        ("probe.py", "cancel", "stripe.Subscription.delete", "called"),
        ("probe.py", "_with_a_default", "stripe.Customer.retrieve", "called"),
        ("probe.py", "lazy_walks", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "lazy_walks", "stripe.Customer.search_auto_paging_iter",
         "handed to run_on_stripe_threads on the loop"),
        ("probe.py", "lazy_walks", "stripe.Customer.retrieve", "handed to partial in a lambda"),
        ("probe.py", "page_methods_handed", "auto_paging_iter", "handed to run_on_stripe_threads on the loop"),
        ("probe.py", "page_methods_handed", "next_page", "handed to run_in_threadpool on the loop"),
        ("probe.py", "page_methods_handed", "stripe.Subscription.delete", "called in a generator expression"),
        ("probe.py", "_nested_helper", "stripe.Invoice.retrieve", "called in retrieve"),
        ("probe.py", "_from_a_walk", "auto_paging_iter", "called"),
        ("probe.py", "_from_a_walk", "stripe.Invoice.list", "called"),
        ("probe.py", "_decorated", "stripe.Price.retrieve", "called"),
        ("probe.py", "_decorated", "stripe.Subscription.delete", "called"),
        ("probe.py", "nested_and_lazy", "stripe.Coupon.retrieve", "called on the loop"),
        ("probe.py", "nested_and_lazy", "stripe.Product.retrieve", "called in a lambda"),
        ("probe.py", "nested_and_lazy", "stripe.Plan.retrieve", "called in a lambda"),
        ("probe.py", "nested_and_lazy", "stripe.Refund.create", "called in a lambda"),
        ("probe.py", "nested_and_lazy", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "nested_and_lazy", "stripe.Payout.retrieve", "called in a generator expression"),
        ("probe.py", "nested_and_lazy", "stripe.Transfer.list", "called in a generator expression"),
        ("probe.py", "nested_and_lazy", "stripe.Charge.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "nested_and_lazy", "previous_page", "handed to partial in a lambda"),
        ("probe.py", "walks_by_keyword", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "_next_page_later", "next_page", "named"),
        ("probe.py", "lazy_wrappers", "stripe.Invoice.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "lazy_wrappers", "stripe.Price.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "lazy_wrappers", "stripe.Product.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "lazy_wrappers", "stripe.Subscription.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "wrapped_page", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Invoice.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Price.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Product.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Customer.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Charge.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Subscription.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.PaymentIntent.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Invoice.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Price.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Product.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "more_wrappers", "stripe.Customer.search_auto_paging_iter", "called in a lambda"),
        ("probe.py", "_cancel_second", "stripe.Subscription.delete", "called"),
        ("probe.py", "_held", "auto_paging_iter", "called"),
        ("probe.py", "held_and_returned", "stripe.Customer.retrieve", "named in a lambda"),
        ("probe.py", "held_and_returned", "stripe.Subscription.delete", "called in a lambda"),
        ("probe.py", "held_and_returned", "stripe.Refund.retrieve", "called in a lambda"),
        ("probe.py", "shared_names", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "search_pages", "next_search_result_page", "called on the loop"),
        ("probe.py", "_walk_then_loop", "auto_paging_iter", "called"),
        ("probe.py", "_loop_over_a_genexp", "auto_paging_iter", "called"),
        ("probe.py", "_through_a_variable", "stripe.Subscription.delete", "called"),
        ("probe.py", "_through_an_attribute", "stripe.Subscription.delete", "called"),
        ("probe.py", "_through_partial", "stripe.Subscription.delete", "called"),
        ("probe.py", "_called_in_a_lambda", "stripe.Subscription.delete", "called"),
        ("probe.py", "strict_forms", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "strict_forms", "auto_paging_iter", "called in a lambda"),
        ("probe.py", "strict_forms", "next_page", "named on the loop"),
        ("probe.py", "strict_forms", "stripe.Customer.retrieve", "handed to partial on the loop"),
        ("probe.py", "strict_forms", "stripe.Subscription.construct_from", "called on the loop"),
        ("probe.py", "<module>", "stripe.Subscription.delete", "called"),
    ]
    # A dotted import binds its own name: ``import stripe.checkout`` binds ``stripe``, and with ``as`` the name is
    # the submodule. Without ``import stripe`` beside them, each must be read on its own.
    dotted = '''
import stripe.checkout
import stripe.billing_portal as portals

async def dotted(customer_id):
    stripe.checkout.Session.create(customer=customer_id)
    portals.Session.create(customer=customer_id)
'''
    assert stripe_operation_sites(dotted) == [
        ("probe.py", "dotted", "stripe.checkout.Session.create", "called on the loop"),
        ("probe.py", "dotted", "stripe.billing_portal.Session.create", "called on the loop"),
    ]


@pytest.mark.asyncio
@pytest.mark.filterwarnings("error")
async def test_run_on_stripe_threads_refuses_work_that_may_fetch_after_it_returns():
    """A generator, coroutine or async generator function, and a result that is a coroutine, an async generator
    or an iterator from stripe-python, the builtins or itertools (a walk, bare or wrapped), may make their
    Stripe requests where the result is used, on the event loop; finished work, a list object and the route
    tests' mocks pass through."""
    import itertools
    from unittest.mock import MagicMock

    import stripe

    from app.services.stripe_threads import run_on_stripe_threads

    def pages():
        yield "page"

    async def later():
        return "page"

    async def pages_later():
        yield "page"

    listed = stripe.ListObject.construct_from(
        {"object": "list", "data": [], "has_more": False, "url": "/v1/subscriptions"}, "sk_test_fake")
    # Refused before the call, so nothing runs; then refused by what the call returned.
    for func in (pages, later, pages_later, lambda: (yield "page")):
        with pytest.raises(TypeError, match="runs where it is iterated or awaited"):
            await run_on_stripe_threads(func)
    returned = {
        "an iterator": (
            lambda: (page for page in ["page"]), listed.auto_paging_iter,
            lambda: filter(None, listed.auto_paging_iter()), lambda: map(str, listed.auto_paging_iter()),
            lambda: itertools.islice(listed.auto_paging_iter(), 1),
        ),
        "a coroutine": (lambda: later(),),
        "an async generator": (lambda: pages_later(),),
    }
    for kind, funcs in returned.items():
        for func in funcs:
            with pytest.raises(TypeError, match=f"returned {kind}"):
                await run_on_stripe_threads(func)
    assert await run_on_stripe_threads(lambda pages: list(pages), iter(["page", "page"])) == ["page", "page"]
    assert await run_on_stripe_threads(lambda: listed) is listed
    mock = MagicMock()
    assert await run_on_stripe_threads(lambda: mock) is mock


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
    on_loop: list[int] = []
    reached = 0

    def held_in_stripe(**_: Any) -> SimpleNamespace:
        # On the loop, the wait below would freeze it, and every other session with it.
        if threading.get_ident() == loop_thread:
            on_loop.append(1)
            raise AssertionError("a Stripe call ran on the event loop")
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
                while (reached < 48 or len(in_stripe) < 8) and not on_loop:
                    await asyncio.sleep(0.01)
        except TimeoutError:
            answered = sorted({task.result().status_code for task in portals if task.done() and not task.exception()})
            if answered:
                why = f"some answered before eight calls were held in Stripe (statuses {answered})"
            elif reached < 48:
                why = "the calls held in Stripe keep the rest from their units"
            else:
                why = "fewer calls run at once than the eight Stripe threads"
            pytest.fail(f"{reached} of 48 portal sessions reached Stripe and {len(in_stripe)} calls are in it: {why}")
        assert not on_loop, f"{len(on_loop)} Stripe calls ran on the event loop"
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
    correlation_ids = [correlation_id for _, correlation_id in in_stripe]
    assert None not in correlation_ids, "a Stripe call ran outside its request's context"
    assert sorted(correlation_ids) == sorted(f"portal-{i}" for i in range(48))

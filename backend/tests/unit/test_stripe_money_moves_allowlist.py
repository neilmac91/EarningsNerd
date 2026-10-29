"""Gate: the backend cancels, refunds or voids nothing in Stripe outside the one site a user's own deletion uses (F18).

`docs/ops/account-deletion.md` states the policy: the code issues no automatic refund, blanket cancellation or orphan
sweep, and any financial correction is a manual founder action in Stripe's console. The one money-moving call the code
makes is the account deletion's cancellation of that account's own billable subscriptions
(`routers/users.py::_cancel_billable_subscriptions`). This gate reads every Python file that can reach Stripe with the
app's key (the backend outside its tests and evals, and `ops/`) and holds each such call to the allowlist below, by
file, function and call. A new one fails here until it is reviewed and listed.

It matches the SDK's two spellings by name: the resource classes (`stripe.Subscription.delete`, `stripe.Refund.create`)
and the client services (`client.subscriptions.cancel`, `client.v1.refunds.create`), each with or without the SDK's
`_async` suffix, under a name a `from stripe import ... as ...` binds, on an instance built from its class
(`stripe.Subscription(sid).delete()`) or fetched in the same expression (`stripe.Subscription.retrieve(x).delete()`,
`client.v1.subscriptions.retrieve(x).delete()`, awaited or not; a service's fetch is read as its resource class's
instance), and called or passed uncalled, as the app hands Stripe calls to `run_on_stripe_threads`. `void_invoice`,
`mark_uncollectible`, `void_credit_note` and `void_grant`, which only Stripe's objects have, count on any receiver. What
it cannot see, left to review: an instance's other method on a name, an attribute or an item (`subscription.cancel()`,
`event.data.object.cancel()`, `page.data[0].delete()`), which reads like any other object's `delete` (a session's, for
one), or on the result of a call it does not read as a fetch (one handed to `run_on_stripe_threads`); a resource class
or a service bound to a name (`Sub = stripe.Subscription`, `subs = client.v1.subscriptions`); the customer service's
update (`client.v1.customers.update(cus, params={"balance": -500})`, a credit), whose name a Python set's or dict's
`update` shares (`billing_revenue_service.py` holds a set of customers), though `stripe.Customer.modify` is seen; a
fetched object changed and saved (`s.cancel_at_period_end = True; s.save()`); a call made through `getattr` or a name
computed at run time; and a request sent through `raw_request` or raw HTTP. Each is planted in the self-check's
`stated_gaps`.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOTS = [REPO / "backend", REPO / "ops"]
SKIP = {"tests", "evals", ".venv", "venv", "node_modules", "__pycache__"}

# (resource, method) pairs that cancel, refund, void, credit or end a billing relationship; None matches every
# method. An update or create counts where its parameters can cancel or credit (a subscription's or schedule's
# cancellation, an item's quantity at 0, a customer's negative balance, a negative invoice item, a credit grant).
# The last rows end disputes, payouts and transfers, which the app never calls, so any such call would be new.
# Calls that charge (an invoice's pay, a payment intent's or charge's capture) are outside the rule.
MONEY_MOVES = {
    ("Subscription", "delete"), ("Subscription", "cancel"), ("Subscription", "modify"), ("Subscription", "pause"),
    ("subscriptions", "cancel"), ("subscriptions", "update"), ("subscriptions", "pause"),
    ("SubscriptionItem", "delete"), ("SubscriptionItem", "modify"),
    ("subscription_items", "delete"), ("subscription_items", "update"),
    ("SubscriptionSchedule", "cancel"), ("SubscriptionSchedule", "modify"),
    ("subscription_schedules", "cancel"), ("subscription_schedules", "update"),
    ("Refund", None), ("refunds", None), ("ApplicationFee", "create_refund"), ("ApplicationFee", "refund"),
    ("CreditNote", None), ("credit_notes", None),
    ("CreditGrant", "create"), ("CreditGrant", "void_grant"), ("CreditGrant", "expire"),
    ("credit_grants", "create"), ("credit_grants", "void_grant"), ("credit_grants", "expire"),
    ("Customer", "create_balance_transaction"), ("balance_transactions", "create"), ("Customer", "modify"),
    ("Customer", "delete"), ("customers", "delete"),
    ("Invoice", "void_invoice"), ("Invoice", "mark_uncollectible"),
    ("invoices", "void_invoice"), ("invoices", "mark_uncollectible"),
    ("Invoice", "delete"), ("invoices", "delete"),
    ("InvoiceItem", "create"), ("InvoiceItem", "delete"), ("invoice_items", "create"), ("invoice_items", "delete"),
    ("PaymentIntent", "cancel"), ("payment_intents", "cancel"),
    ("Reader", "refund_payment"), ("readers", "refund_payment"),
    ("Dispute", "close"), ("disputes", "close"),
    ("Transfer", "create_reversal"), ("reversals", "create"),
    ("Payout", "cancel"), ("Payout", "reverse"), ("payouts", "cancel"), ("payouts", "reverse"),
}

ALLOWED = {
    # A user's own deletion cancels that account's billable subscriptions, walking every page (E170, F19).
    ("backend/app/routers/users.py", "_cancel_billable_subscriptions", "Subscription.delete"): 1,
}


# Methods only Stripe's objects have: a call of one moves money whatever the receiver, an instance on a name included.
STRIPE_ONLY_METHODS = {"void_invoice", "mark_uncollectible", "void_credit_note", "void_grant"}

# A client service's fetch returns its resource class's instance, whose methods are the class's
# (`client.v1.subscriptions.retrieve(x).delete()` deletes, though the service has no delete).
SERVICE_RESOURCES = {
    "subscriptions": "Subscription", "subscription_items": "SubscriptionItem",
    "subscription_schedules": "SubscriptionSchedule", "invoices": "Invoice", "invoice_items": "InvoiceItem",
    "payment_intents": "PaymentIntent", "customers": "Customer", "refunds": "Refund", "credit_notes": "CreditNote",
    "credit_grants": "CreditGrant", "application_fees": "ApplicationFee", "disputes": "Dispute", "payouts": "Payout",
    "transfers": "Transfer", "readers": "Reader",
}


def _resource(owner: ast.AST, aliases: dict[str, str]):
    """The resource a method is reached on: `stripe.Subscription`, `client.v1.subscriptions`, a name a
    `from stripe import` binds, an instance built from its class (`stripe.Subscription(sid)`), or the resource a
    same-expression fetch returns (`stripe.Subscription.retrieve(x)`, `client.v1.subscriptions.retrieve(x)`, awaited
    or not)."""
    if isinstance(owner, ast.Await):
        owner = owner.value
    if isinstance(owner, ast.Call):
        func = owner.func
        if isinstance(func, ast.Name):
            return aliases.get(func.id, func.id)
        if isinstance(func, ast.Attribute) and func.attr[:1].isupper():
            return func.attr
        if isinstance(func, ast.Attribute):
            fetched = _resource(func.value, aliases)
            return SERVICE_RESOURCES.get(fetched, fetched)
        return None
    if isinstance(owner, ast.Attribute):
        return owner.attr
    return aliases.get(owner.id, owner.id) if isinstance(owner, ast.Name) else None


def _money_moves(source: str) -> list[tuple[str, str]]:
    """Each (enclosing function, `Resource.method`) reference in ``source`` that MONEY_MOVES names, called or
    passed: a call counts once, at the method it calls, except that a fetch from a resource listed for every method
    counts too (`stripe.Refund.retrieve(x).cancel()` gives `Refund.cancel` and `Refund.retrieve`), which fails
    closed."""
    tree = ast.parse(source)
    aliases = {
        alias.asname: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "stripe"
        for alias in node.names if alias.asname
    }
    found: list[tuple[str, str]] = []

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                method = child.attr.removesuffix("_async")
                resource = _resource(child.value, aliases)
                if ((resource, method) in MONEY_MOVES or (resource, None) in MONEY_MOVES
                        or method in STRIPE_ONLY_METHODS):
                    found.append((function, f"{resource}.{method}"))
            visit(child, function)

    visit(tree, "<module>")
    return found


def _sources():
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            if not SKIP.intersection(path.relative_to(REPO).parts):
                yield path.relative_to(REPO).as_posix(), path.read_text(encoding="utf-8")


def test_the_reader_sees_each_spelling_and_nothing_else():
    planted = '''
import functools
import stripe
from stripe import Subscription as Sub
def resource_forms():
    stripe.Subscription.delete("sub_1")
    stripe.Refund.create(payment_intent="pi_1")
    stripe.Customer.delete("cus_1")
    Sub.delete("sub_1")
def client_forms(client):
    client.subscriptions.cancel("sub_1")
    client.v1.refunds.create(params={})
    client.invoices.void_invoice("in_1")
async def async_forms(client):
    await stripe.Subscription.cancel_async("sub_1")
    await stripe.Customer.delete_async("cus_1")
    await client.v1.subscriptions.cancel_async("sub_1")
    await stripe.Invoice.void_invoice_async("in_1")
    await (await stripe.Subscription.retrieve_async("sub_1")).cancel_async()
    await (await client.v1.subscriptions.retrieve_async("sub_1")).delete_async()
def fetched_then_moved(client, invoice, grant, note):
    stripe.Subscription.retrieve("sub_1").delete()
    client.v1.subscriptions.retrieve("sub_1").delete()
    invoice.void_invoice()
    invoice.mark_uncollectible_async()
    grant.void_grant()
    note.void_credit_note()
def constructed(client):
    stripe.Subscription("sub_1").delete()
    Sub("sub_1").cancel()
async def handed_over(client):
    await run_on_stripe_threads(stripe.Subscription.delete, "sub_1")
    await run_in_threadpool(stripe.Refund.create, charge="ch_1")
    functools.partial(client.v1.subscription_schedules.cancel, "sub_sched_1")
def sdk_16_moves(client):
    stripe.SubscriptionSchedule.cancel("sub_sched_1")
    client.v1.billing.credit_grants.void_grant("credgr_1")
    stripe.ApplicationFee.create_refund("fee_1")
    client.v1.subscriptions.pause("sub_1")
    client.v1.subscription_items.delete("si_1")
    client.v1.customers.balance_transactions.create("cus_1", params={"amount": -500, "currency": "usd"})
    stripe.Dispute.close("dp_1")
    client.v1.billing.credit_grants.expire("credgr_1")
    client.v1.invoices.delete("in_1")
    client.v1.terminal.readers.refund_payment("tmr_1")
def cancel_or_credit_by_update(client):
    stripe.SubscriptionSchedule.modify("sub_sched_1", end_behavior="cancel")
    client.v1.subscription_schedules.update("sub_sched_1", params={"end_behavior": "cancel"})
    stripe.SubscriptionItem.modify("si_1", quantity=0)
    client.v1.subscription_items.update("si_1", params={"quantity": 0})
    stripe.billing.CreditGrant.create(customer="cus_1")
    client.v1.billing.credit_grants.create(params={"customer": "cus_1"})
    stripe.Customer.modify("cus_1", balance=-500)
    stripe.InvoiceItem.create(customer="cus_1", amount=-500)
    client.v1.invoice_items.create(params={"customer": "cus_1", "amount": -500})
def reads(client, db, row):
    stripe.Subscription.list(customer="cus_1")
    stripe.Subscription.retrieve("sub_1")
    client.customers.retrieve("cus_1")
    run_on_stripe_threads(stripe.Customer.retrieve, "cus_1")
    client.v1.subscriptions.retrieve("sub_1").items
    client.v1.invoices.pay("in_1")
    db.delete(row)
async def stated_gaps(client, subscription):
    subscription.cancel()
    subscription.delete()
    subscription.pause()
    event.data.object.cancel()
    page.data[0].delete()
    (await run_on_stripe_threads(stripe.Subscription.retrieve, "sub_1")).delete()
    Bound = stripe.Subscription
    Bound.delete("sub_1")
    subs = client.v1.subscriptions
    subs.cancel("sub_1")
    client.v1.customers.update("cus_1", params={"balance": -500})
    fetched = stripe.Subscription.retrieve("sub_1")
    fetched.cancel_at_period_end = True
    fetched.save()
    getattr(stripe.Subscription, "del" + "ete")("sub_1")
    client.raw_request("delete", "/v1/subscriptions/sub_1")
    httpx.delete("https://api.stripe.com/v1/subscriptions/sub_1")
'''
    assert _money_moves(planted) == [
        ("resource_forms", "Subscription.delete"), ("resource_forms", "Refund.create"),
        ("resource_forms", "Customer.delete"), ("resource_forms", "Subscription.delete"),
        ("client_forms", "subscriptions.cancel"), ("client_forms", "refunds.create"),
        ("client_forms", "invoices.void_invoice"),
        ("async_forms", "Subscription.cancel"), ("async_forms", "Customer.delete"),
        ("async_forms", "subscriptions.cancel"), ("async_forms", "Invoice.void_invoice"),
        ("async_forms", "Subscription.cancel"),
        ("async_forms", "Subscription.delete"),
        ("fetched_then_moved", "Subscription.delete"), ("fetched_then_moved", "Subscription.delete"),
        ("fetched_then_moved", "invoice.void_invoice"), ("fetched_then_moved", "invoice.mark_uncollectible"),
        ("fetched_then_moved", "grant.void_grant"), ("fetched_then_moved", "note.void_credit_note"),
        ("constructed", "Subscription.delete"), ("constructed", "Subscription.cancel"),
        ("handed_over", "Subscription.delete"), ("handed_over", "Refund.create"),
        ("handed_over", "subscription_schedules.cancel"),
        ("sdk_16_moves", "SubscriptionSchedule.cancel"), ("sdk_16_moves", "credit_grants.void_grant"),
        ("sdk_16_moves", "ApplicationFee.create_refund"), ("sdk_16_moves", "subscriptions.pause"),
        ("sdk_16_moves", "subscription_items.delete"), ("sdk_16_moves", "balance_transactions.create"),
        ("sdk_16_moves", "Dispute.close"), ("sdk_16_moves", "credit_grants.expire"),
        ("sdk_16_moves", "invoices.delete"), ("sdk_16_moves", "readers.refund_payment"),
        ("cancel_or_credit_by_update", "SubscriptionSchedule.modify"),
        ("cancel_or_credit_by_update", "subscription_schedules.update"),
        ("cancel_or_credit_by_update", "SubscriptionItem.modify"),
        ("cancel_or_credit_by_update", "subscription_items.update"),
        ("cancel_or_credit_by_update", "CreditGrant.create"), ("cancel_or_credit_by_update", "credit_grants.create"),
        ("cancel_or_credit_by_update", "Customer.modify"), ("cancel_or_credit_by_update", "InvoiceItem.create"),
        ("cancel_or_credit_by_update", "invoice_items.create"),
    ]


def test_stripe_money_moves_stay_on_the_allowlist():
    counts: dict[tuple[str, str, str], int] = {}
    for rel, source in _sources():
        for function, call in _money_moves(source):
            counts[(rel, function, call)] = counts.get((rel, function, call), 0) + 1
    assert counts == ALLOWED, (
        "A Stripe call that cancels, refunds or voids is new or gone. Corrections stay manual founder actions "
        "(docs/ops/account-deletion.md §5): review the call, then list it in ALLOWED with why."
    )

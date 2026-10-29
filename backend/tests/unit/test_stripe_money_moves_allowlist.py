"""Gate: the backend cancels, refunds or voids nothing in Stripe outside the one site a user's own deletion uses (F18).

`docs/ops/account-deletion.md` states the policy: the code issues no automatic refund, blanket cancellation or orphan
sweep, and any financial correction is a manual founder action in Stripe's console. The one money-moving call the
code makes is the account deletion's cancellation of that account's own billable subscriptions
(`routers/users.py::_cancel_billable_subscriptions`). This gate reads every Python file that can reach Stripe with
the app's key (the backend outside its tests, and `ops/`) and holds each such call to the allowlist below, by file,
function and call. A new one fails here until it is reviewed and listed.

It matches the SDK's two spellings by name: the resource classes (`stripe.Subscription.delete`, `stripe.Refund.create`)
and the client services (`client.subscriptions.cancel`, `client.v1.refunds.create`), each with or without the SDK's
`_async` suffix, under a name a `from stripe import ... as ...` binds, on a resource fetched in the same expression
(`stripe.Subscription.retrieve(x).delete()`, awaited or not), and called or passed uncalled, as the app hands Stripe
calls to `run_on_stripe_threads`. `void_invoice` and `mark_uncollectible`, which only Stripe's invoices have, count
on any receiver. What it cannot see, left to review: an instance's `cancel()` or `delete()` on a name
(`subscription.cancel()`), which reads like any other object's `delete` (a session's, for one); a service bound to a
name (`subs = client.v1.subscriptions`, then `subs.cancel(...)`); a fetched object changed and saved
(`s.cancel_at_period_end = True; s.save()`); a call made through `getattr` or a name computed at run time; and a
request sent through `raw_request` or raw HTTP. Each is planted in the self-check's `stated_gaps`.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOTS = [REPO / "backend", REPO / "ops"]
SKIP = {"tests", "evals", ".venv", "venv", "node_modules", "__pycache__"}

# (resource, method) pairs that move money or end a billing relationship; None matches every method. The last rows
# are Connect's: the app holds no connected account, so any such call would be new.
MONEY_MOVES = {
    ("Subscription", "delete"), ("Subscription", "cancel"), ("Subscription", "modify"), ("Subscription", "pause"),
    ("subscriptions", "cancel"), ("subscriptions", "update"), ("subscriptions", "pause"),
    ("SubscriptionItem", "delete"), ("subscription_items", "delete"),
    ("SubscriptionSchedule", "cancel"), ("subscription_schedules", "cancel"),
    ("Refund", None), ("refunds", None), ("ApplicationFee", "create_refund"), ("ApplicationFee", "refund"),
    ("CreditNote", None), ("credit_notes", None),
    ("CreditGrant", "void_grant"), ("credit_grants", "void_grant"),
    ("Customer", "create_balance_transaction"), ("balance_transactions", "create"),
    ("Customer", "delete"), ("customers", "delete"),
    ("Invoice", "void_invoice"), ("Invoice", "mark_uncollectible"),
    ("invoices", "void_invoice"), ("invoices", "mark_uncollectible"),
    ("PaymentIntent", "cancel"), ("payment_intents", "cancel"),
    ("Dispute", "close"), ("disputes", "close"),
    ("Transfer", "create_reversal"), ("reversals", "create"),
    ("Payout", "cancel"), ("Payout", "reverse"), ("payouts", "cancel"), ("payouts", "reverse"),
}

ALLOWED = {
    # A user's own deletion cancels that account's billable subscriptions, walking every page (E170, F19).
    ("backend/app/routers/users.py", "_cancel_billable_subscriptions", "Subscription.delete"): 1,
}


# Invoice methods only Stripe has: a call of either moves money whatever the receiver.
STRIPE_ONLY_METHODS = {"void_invoice", "mark_uncollectible"}


def _resource(owner: ast.AST, aliases: dict[str, str]):
    """The resource a method is reached on: `stripe.Subscription`, `client.v1.subscriptions`, a name a
    `from stripe import` binds, or the resource a same-expression fetch returns (`stripe.Subscription.retrieve(x)`,
    or `await stripe.Subscription.retrieve_async(x)`)."""
    if isinstance(owner, ast.Await):
        owner = owner.value
    if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute):
        owner = owner.func.value
    if isinstance(owner, ast.Attribute):
        return owner.attr
    return aliases.get(owner.id, owner.id) if isinstance(owner, ast.Name) else None


def _money_moves(source: str) -> list[tuple[str, str]]:
    """Each (enclosing function, `Resource.method`) reference in ``source`` that MONEY_MOVES names, called or
    passed: a call counts once, at the method it calls."""
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
def fetched_then_moved(invoice):
    stripe.Subscription.retrieve("sub_1").delete()
    invoice.void_invoice()
    invoice.mark_uncollectible_async()
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
def reads(client, db, row):
    stripe.Subscription.list(customer="cus_1")
    stripe.Subscription.retrieve("sub_1")
    client.customers.retrieve("cus_1")
    run_on_stripe_threads(stripe.Customer.retrieve, "cus_1")
    db.delete(row)
def stated_gaps(client, subscription):
    subscription.cancel()
    subscription.delete()
    subs = client.v1.subscriptions
    subs.cancel("sub_1")
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
        ("fetched_then_moved", "Subscription.delete"), ("fetched_then_moved", "invoice.void_invoice"),
        ("fetched_then_moved", "invoice.mark_uncollectible"),
        ("handed_over", "Subscription.delete"), ("handed_over", "Refund.create"),
        ("handed_over", "subscription_schedules.cancel"),
        ("sdk_16_moves", "SubscriptionSchedule.cancel"), ("sdk_16_moves", "credit_grants.void_grant"),
        ("sdk_16_moves", "ApplicationFee.create_refund"), ("sdk_16_moves", "subscriptions.pause"),
        ("sdk_16_moves", "subscription_items.delete"), ("sdk_16_moves", "balance_transactions.create"),
        ("sdk_16_moves", "Dispute.close"),
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

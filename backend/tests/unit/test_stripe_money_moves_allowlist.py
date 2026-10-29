"""Gate: the backend cancels, refunds or voids nothing in Stripe outside the one site a user's own deletion uses (F18).

`docs/ops/account-deletion.md` states the policy: the code issues no automatic refund, blanket cancellation or orphan
sweep, and any financial correction is a manual founder action in Stripe's console. The one money-moving call the
code makes is the account deletion's cancellation of that account's own billable subscriptions
(`routers/users.py::_cancel_billable_subscriptions`). This gate reads every Python file that can reach Stripe with
the app's key (the backend outside its tests, and `ops/`) and holds each such call to the allowlist below, by file,
function and call. A new one fails here until it is reviewed and listed.

It matches the SDK's two spellings by name: the resource classes (`stripe.Subscription.delete`, `stripe.Refund.create`)
and the client services (`client.subscriptions.cancel`, `client.v1.refunds.create`), each with or without the SDK's
`_async` suffix, and a call on a resource fetched in the same expression (`stripe.Subscription.retrieve(x).delete()`).
`void_invoice` and `mark_uncollectible`, which only Stripe's invoices have, count on any receiver. What it cannot see,
left to review: an instance's `cancel()` or `delete()` on a name (`subscription.cancel()`), which reads like any other
object's `delete` (a session's, for one); a call made through `getattr` or a name computed at run time; and a raw HTTP
request to Stripe's API.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOTS = [REPO / "backend", REPO / "ops"]
SKIP = {"tests", "evals", ".venv", "venv", "node_modules", "__pycache__"}

# (resource, method) pairs that move money or end a billing relationship; None matches every method.
MONEY_MOVES = {
    ("Subscription", "delete"), ("Subscription", "cancel"), ("Subscription", "modify"),
    ("subscriptions", "cancel"), ("subscriptions", "update"),
    ("Refund", None), ("refunds", None),
    ("CreditNote", None), ("credit_notes", None),
    ("Customer", "delete"), ("customers", "delete"),
    ("Invoice", "void_invoice"), ("Invoice", "mark_uncollectible"),
    ("invoices", "void_invoice"), ("invoices", "mark_uncollectible"),
    ("PaymentIntent", "cancel"), ("payment_intents", "cancel"),
}

ALLOWED = {
    # A user's own deletion cancels that account's billable subscriptions, walking every page (E170, F19).
    ("backend/app/routers/users.py", "_cancel_billable_subscriptions", "Subscription.delete"): 1,
}


# Invoice methods only Stripe has: a call of either moves money whatever the receiver.
STRIPE_ONLY_METHODS = {"void_invoice", "mark_uncollectible"}


def _resource(owner: ast.AST):
    """The resource a method is called on: `stripe.Subscription`, `client.v1.subscriptions`, or the resource a
    same-expression fetch returns (`stripe.Subscription.retrieve(x)`)."""
    if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute):
        owner = owner.func.value
    return owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", None)


def _money_moves(source: str) -> list[tuple[str, str]]:
    """Each (enclosing function, `Resource.method`) call in ``source`` that MONEY_MOVES names."""
    found: list[tuple[str, str]] = []

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                method = child.func.attr.removesuffix("_async")
                resource = _resource(child.func.value)
                if ((resource, method) in MONEY_MOVES or (resource, None) in MONEY_MOVES
                        or method in STRIPE_ONLY_METHODS):
                    found.append((function, f"{resource}.{method}"))
            visit(child, function)

    visit(ast.parse(source), "<module>")
    return found


def _sources():
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            if not SKIP.intersection(path.relative_to(REPO).parts):
                yield path.relative_to(REPO).as_posix(), path.read_text(encoding="utf-8")


def test_the_reader_sees_each_spelling_and_nothing_else():
    planted = '''
import stripe
def resource_forms():
    stripe.Subscription.delete("sub_1")
    stripe.Refund.create(payment_intent="pi_1")
    stripe.Customer.delete("cus_1")
def client_forms(client):
    client.subscriptions.cancel("sub_1")
    client.v1.refunds.create(params={})
    client.invoices.void_invoice("in_1")
async def async_forms(client):
    await stripe.Subscription.cancel_async("sub_1")
    await stripe.Customer.delete_async("cus_1")
    await client.v1.subscriptions.cancel_async("sub_1")
    await stripe.Invoice.void_invoice_async("in_1")
def fetched_then_moved(invoice):
    stripe.Subscription.retrieve("sub_1").delete()
    invoice.void_invoice()
    invoice.mark_uncollectible_async()
def reads(client, db, row):
    stripe.Subscription.list(customer="cus_1")
    stripe.Subscription.retrieve("sub_1")
    client.customers.retrieve("cus_1")
    db.delete(row)
def stated_gaps(subscription):
    subscription.cancel()
    subscription.delete()
    getattr(stripe.Subscription, "del" + "ete")("sub_1")
'''
    assert _money_moves(planted) == [
        ("resource_forms", "Subscription.delete"), ("resource_forms", "Refund.create"),
        ("resource_forms", "Customer.delete"), ("client_forms", "subscriptions.cancel"),
        ("client_forms", "refunds.create"), ("client_forms", "invoices.void_invoice"),
        ("async_forms", "Subscription.cancel"), ("async_forms", "Customer.delete"),
        ("async_forms", "subscriptions.cancel"), ("async_forms", "Invoice.void_invoice"),
        ("fetched_then_moved", "Subscription.delete"), ("fetched_then_moved", "invoice.void_invoice"),
        ("fetched_then_moved", "invoice.mark_uncollectible"),
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

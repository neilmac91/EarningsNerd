"""Gate: the backend cancels, refunds or voids nothing in Stripe outside the one site a user's own deletion uses (F18).

`docs/ops/account-deletion.md` states the policy: the code issues no automatic refund, blanket cancellation or orphan
sweep, and any financial correction is a manual founder action in Stripe's console. The one money-moving call the code
makes is the account deletion's cancellation of that account's own billable subscriptions
(`routers/users.py::_cancel_billable_subscriptions`). This gate reads every Python file that can reach Stripe with the
app's key (the backend outside its tests and evals, and `ops/`) and holds each such call to the allowlist below, by
file, function and call. A new one fails here until it is reviewed and listed.

It matches the SDK's two spellings by name: the resource classes (`stripe.Subscription.delete`, `stripe.Refund.create`)
and the client services (`client.subscriptions.cancel`, `client.v1.refunds.create`), each with or without the SDK's
`_async` suffix or its private `_cls_` prefix, under a name a `from stripe import ... as ...` binds, on an instance
built from its class (`stripe.Subscription(sid).delete()`) or fetched in the same expression
(`stripe.Subscription.retrieve(x).delete()`, `client.v1.subscriptions.retrieve(x).delete()`, awaited or not; a service's
fetch is read as its resource class's instance, and a nested list, `stripe.Customer.list_balance_transactions(c)`, as
its nested service, whose `create` posts to it), and called or passed uncalled, as the app hands Stripe calls to
`run_on_stripe_threads`. `void_invoice`, `mark_uncollectible`, `void_credit_note` and `void_grant`, which only Stripe's
objects have, count on any receiver, and so do the nested-resource request helpers (`stripe.Customer.sources_request`),
which send any method to any URL. A service's pair counts only when the service is reached as an attribute
(`client.v1.customers.update`): a bare lowercase name is a local value (`billing_revenue_service.py`'s set of
`customers`). Matching by name fails closed: an attribute or a `list_*` result under a listed service's name counts
whatever it holds (a dict's `update` included), and so does a class named like a resource; such a hit is reviewed and
listed, or renamed. What it cannot see, left to review: an instance's other method on a name, an attribute or an item
(`subscription.cancel()`, `event.data.object.cancel()`, `page.data[0].delete()`), which reads like any other object's
`delete` (a session's, for one), or on the result of a call it does not read as a fetch (one handed to
`run_on_stripe_threads`); a resource class or a service bound to a name, the service's own name included (`Sub =
stripe.Subscription`, `customers = client.v1.customers`), or returned by a call (`_subscriptions(client).cancel(x)`); a
customer created with a balance through the resource class (`stripe.Customer.create(balance=-500)`, a credit), since by
name it is also the checkout's own customer (`routers/subscriptions.py`); a fetched object changed and saved
(`s.cancel_at_period_end = True; s.save()`); a call made through `getattr` or a name computed at run time; and a request
sent through `raw_request`, the SDK's private `_static_request` or an object's `_request`, or raw HTTP. Each is planted
in the self-check's `stated_gaps`. The rule's own exclusions are planted in `outside_the_rule`, uncounted.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOTS = [REPO / "backend", REPO / "ops"]
SKIP = {"tests", "evals", ".venv", "venv", "node_modules", "__pycache__"}

# (resource, method) pairs that cancel, pause or end billing, refund, void, write off, credit, or reverse a movement of
# funds; None matches every method (a read included, which fails closed). An update or create counts where its
# parameters can do one of those: a subscription's or schedule's cancellation or end, an item's quantity at 0, a
# negative balance, invoice item, invoice line or added invoice item, a credit grant or its expiry, an invoice paid out
# of band or forgiven, a usage event cancelled. Cancelling or reversing the platform's own movements counts as well (a
# payout, top-up, transfer, Treasury flow or climate order), which the app never does, so any such call would be new;
# creating one is outside the rule. So are, left to review: a pricing change that lowers what a customer pays (a coupon,
# promotion code, price, plan, trial offer, or a discount on an invoice or quote); the trial terms a checkout session or
# payment link sets for the subscription it creates (`subscription_data.trial_settings`, which can have Stripe cancel a
# trial that ends with no card on file, as the app's own card-required trial does in `routers/subscriptions.py`: Stripe
# applies the subscription's terms, the code cancels nothing); a capture of less than was authorized; a payment method
# detached; a payment or refund made elsewhere and recorded (`attach_payment`, `report_refund`); a Connect account
# ended; and the calls that charge.
# A void (`void_invoice`, `void_grant`, `void_credit_note`) and `mark_uncollectible` are STRIPE_ONLY_METHODS below,
# counted on any receiver, so they need no row.
MONEY_MOVES = {
    ("Subscription", "create"), ("Subscription", "delete"), ("Subscription", "cancel"), ("Subscription", "modify"),
    ("Subscription", "pause"),
    ("subscriptions", "create"), ("subscriptions", "cancel"), ("subscriptions", "update"), ("subscriptions", "pause"),
    ("SubscriptionItem", "delete"), ("SubscriptionItem", "modify"),
    ("subscription_items", "delete"), ("subscription_items", "update"),
    ("SubscriptionSchedule", "create"), ("SubscriptionSchedule", "cancel"), ("SubscriptionSchedule", "modify"),
    ("subscription_schedules", "create"), ("subscription_schedules", "cancel"), ("subscription_schedules", "update"),
    ("Refund", None), ("refunds", None), ("ApplicationFee", "create_refund"), ("ApplicationFee", "refund"),
    ("CreditNote", None), ("credit_notes", None),
    ("CreditGrant", "create"), ("CreditGrant", "modify"), ("CreditGrant", "expire"),
    ("credit_grants", "create"), ("credit_grants", "update"), ("credit_grants", "expire"),
    ("MeterEventAdjustment", "create"), ("meter_event_adjustments", "create"),
    ("Meter", "deactivate"), ("meters", "deactivate"),
    ("Customer", "create_balance_transaction"), ("balance_transactions", "create"), ("Customer", "modify"),
    ("Customer", "delete"), ("customers", "create"), ("customers", "update"), ("customers", "delete"),
    ("Invoice", "pay"), ("invoices", "pay"), ("Invoice", "delete"), ("invoices", "delete"),
    ("Invoice", "add_lines"), ("Invoice", "update_lines"), ("Invoice", "remove_lines"),
    ("invoices", "add_lines"), ("invoices", "update_lines"), ("invoices", "remove_lines"),
    ("InvoiceLineItem", "modify"), ("line_items", "update"),
    ("InvoiceItem", "create"), ("InvoiceItem", "modify"), ("InvoiceItem", "delete"),
    ("invoice_items", "create"), ("invoice_items", "update"), ("invoice_items", "delete"),
    ("PaymentIntent", "cancel"), ("payment_intents", "cancel"),
    ("Reader", "refund_payment"), ("readers", "refund_payment"),
    ("Dispute", "close"), ("disputes", "close"),
    ("Transfer", "create_reversal"), ("reversals", "create"),
    ("Payout", "cancel"), ("Payout", "reverse"), ("payouts", "cancel"), ("payouts", "reverse"),
    ("Topup", "cancel"), ("topups", "cancel"), ("Order", "cancel"), ("orders", "cancel"),
    ("OutboundPayment", "cancel"), ("outbound_payments", "cancel"),
    ("OutboundTransfer", "cancel"), ("outbound_transfers", "cancel"),
    ("InboundTransfer", "cancel"), ("inbound_transfers", "cancel"),
    ("CreditReversal", "create"), ("credit_reversals", "create"),
    ("DebitReversal", "create"), ("debit_reversals", "create"),
}

ALLOWED = {
    # A user's own deletion cancels that account's billable subscriptions, walking every page (E170, F19).
    ("backend/app/routers/users.py", "_cancel_billable_subscriptions", "Subscription.delete"): 1,
}


# Methods only Stripe's objects have: a call of one moves money whatever the receiver, an instance on a name included.
# The nested-resource request helpers send any method to any URL with the app's key, so each counts too.
NESTED_REQUEST_HELPERS = {
    "balance_transactions_request", "cash_balance_transactions_request", "sources_request", "tax_ids_request",
    "refunds_request", "reversals_request", "lines_request", "amount_details_line_items_request",
    "features_request", "capabilitys_request", "external_accounts_request", "login_links_request", "persons_request",
    "event_summarys_request",
}
STRIPE_ONLY_METHODS = {"void_invoice", "mark_uncollectible", "void_credit_note", "void_grant"} | NESTED_REQUEST_HELPERS

# A client service's fetch returns its resource class's instance, whose methods are the class's
# (`client.v1.subscriptions.retrieve(x).delete()` deletes, though the service has no delete).
SERVICE_RESOURCES = {
    "subscriptions": "Subscription", "subscription_items": "SubscriptionItem",
    "subscription_schedules": "SubscriptionSchedule", "invoices": "Invoice", "invoice_items": "InvoiceItem",
    "payment_intents": "PaymentIntent", "customers": "Customer", "refunds": "Refund", "credit_notes": "CreditNote",
    "credit_grants": "CreditGrant", "application_fees": "ApplicationFee", "disputes": "Dispute", "payouts": "Payout",
    "transfers": "Transfer", "readers": "Reader", "topups": "Topup", "meters": "Meter", "orders": "Order",
    "outbound_payments": "OutboundPayment", "outbound_transfers": "OutboundTransfer",
    "inbound_transfers": "InboundTransfer", "credit_reversals": "CreditReversal", "debit_reversals": "DebitReversal",
}


def _resource(owner: ast.AST, aliases: dict[str, str]):
    """The resource a method is reached on: `stripe.Subscription`, `client.v1.subscriptions`, a name a
    `from stripe import` binds, an instance built from its class (`stripe.Subscription(sid)`), the resource a
    same-expression fetch returns (`stripe.Subscription.retrieve(x)`, `client.v1.subscriptions.retrieve(x)`, awaited
    or not), or the nested service a nested list posts to (`stripe.Customer.list_balance_transactions(c)`)."""
    if isinstance(owner, ast.Await):
        owner = owner.value
    if isinstance(owner, ast.Call):
        func = owner.func
        if isinstance(func, ast.Name):
            return aliases.get(func.id, func.id)
        if isinstance(func, ast.Attribute) and func.attr[:1].isupper():
            return func.attr
        if isinstance(func, ast.Attribute) and func.attr.removesuffix("_async").startswith("list_"):
            return func.attr.removesuffix("_async").removeprefix("list_")  # a nested list posts to its service
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
                method = child.attr.removesuffix("_async").removeprefix("_cls_")
                resource = _resource(child.value, aliases)
                # A bare lowercase name that no `from stripe import` binds is a local value, not a service.
                local = (isinstance(child.value, ast.Name) and child.value.id not in aliases
                         and not child.value.id[:1].isupper())
                if ((not local and ((resource, method) in MONEY_MOVES or (resource, None) in MONEY_MOVES))
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
from stripe import Refund
from stripe import Subscription as Sub
from stripe import Subscription as sub
def resource_forms():
    stripe.Subscription.delete("sub_1")
    stripe.Refund.create(payment_intent="pi_1")
    stripe.Customer.delete("cus_1")
    Sub.delete("sub_1")
    Refund.create(charge="ch_1")
    sub.cancel("sub_1")
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
    stripe.InvoiceItem.modify("ii_1", amount=-500)
    client.v1.invoice_items.update("ii_1", params={"amount": -500})
    stripe.Invoice.add_lines("in_1", lines=[{"amount": -500}])
    client.v1.invoices.add_lines("in_1", params={"lines": [{"amount": -500}]})
    stripe.Invoice.update_lines("in_1", lines=[{"id": "il_1", "amount": -500}])
    client.v1.invoices.update_lines("in_1", params={"lines": [{"id": "il_1", "amount": -500}]})
    stripe.Invoice.remove_lines("in_1", lines=[{"id": "il_1", "behavior": "delete"}])
    client.v1.invoices.remove_lines("in_1", params={"lines": [{"id": "il_1", "behavior": "delete"}]})
    stripe.InvoiceLineItem.modify("in_1", "il_1", amount=-500)
    client.v1.invoices.line_items.update("in_1", "il_1", params={"amount": -500})
    client.v1.customers.update("cus_1", params={"balance": -500})
    client.v1.customers.create(params={"balance": -500})
def the_swept_surface(client):
    stripe.Subscription.create(customer="cus_1", add_invoice_items=[{"price_data": {"unit_amount": -500}}])
    client.v1.subscriptions.create(params={"customer": "cus_1", "cancel_at_period_end": True})
    stripe.SubscriptionSchedule.create(customer="cus_1", end_behavior="cancel")
    client.v1.subscription_schedules.create(params={"customer": "cus_1", "end_behavior": "cancel"})
    stripe.Invoice.pay("in_1", forgive=True)
    client.v1.invoices.pay("in_1", params={"paid_out_of_band": True})
    stripe.billing.CreditGrant.modify("credgr_1", expires_at=1)
    client.v1.billing.credit_grants.update("credgr_1", params={"expires_at": ""})
    stripe.billing.MeterEventAdjustment.create(event_name="api_calls", type="cancel")
    client.v2.billing.meter_event_adjustments.create(params={"type": "cancel"})
    stripe.billing.Meter.deactivate("mtr_1")
    client.v1.billing.meters.deactivate("mtr_1")
    stripe.climate.Order.cancel("climorder_1")
    client.v1.climate.orders.cancel("climorder_1")
    stripe.Topup.cancel("tu_1")
    client.v1.topups.cancel("tu_1")
    stripe.treasury.OutboundPayment.cancel("obp_1")
    client.v1.treasury.outbound_transfers.cancel("obt_1")
    stripe.treasury.InboundTransfer.cancel("ibt_1")
    client.v1.treasury.credit_reversals.create(params={"received_credit": "rc_1"})
    stripe.treasury.DebitReversal.create(received_debit="rd_1")
    client.v1.topups.retrieve("tu_1").cancel()
    stripe.Customer.sources_request("delete", "/v1/subscriptions/sub_1")
    stripe.Customer.balance_transactions_request("post", "/v1/customers/cus_1/balance_transactions")
    stripe.Customer.list_balance_transactions("cus_1").create(amount=-500, currency="usd")
    stripe.ApplicationFee.list_refunds("fee_1").create(amount=100)
    stripe.Transfer.list_reversals("tr_1").create()
    stripe.Subscription._cls_cancel("sub_1")
    await_later = stripe.Invoice._cls_void_invoice_async("in_1")
def each_other_row(client):
    stripe.ApplicationFee.refund("fee_1")
    stripe.billing.CreditGrant.expire("credgr_1")
    stripe.billing.CreditGrant.void_grant("credgr_1")
    stripe.CreditNote.create(invoice="in_1")
    stripe.treasury.CreditReversal.create(received_credit="rc_1")
    stripe.Customer.create_balance_transaction("cus_1", amount=-500, currency="usd")
    stripe.Invoice.delete("in_1")
    stripe.Invoice.mark_uncollectible("in_1")
    stripe.InvoiceItem.delete("ii_1")
    stripe.treasury.OutboundTransfer.cancel("obt_1")
    stripe.PaymentIntent.cancel("pi_1")
    stripe.Payout.cancel("po_1")
    stripe.Payout.reverse("po_1")
    stripe.terminal.Reader.refund_payment("tmr_1")
    stripe.Subscription.modify("sub_1", cancel_at_period_end=True)
    stripe.Subscription.pause("sub_1")
    stripe.SubscriptionItem.delete("si_1")
    stripe.Transfer.create_reversal("tr_1")
    client.v1.credit_notes.create(params={"invoice": "in_1"})
    client.v1.customers.delete("cus_1")
    client.v1.treasury.debit_reversals.create(params={"received_debit": "rd_1"})
    client.v1.disputes.close("dp_1")
    client.v1.treasury.inbound_transfers.cancel("ibt_1")
    client.v1.invoice_items.delete("ii_1")
    client.v1.invoices.mark_uncollectible("in_1")
    client.v1.treasury.outbound_payments.cancel("obp_1")
    client.v1.payment_intents.cancel("pi_1")
    client.v1.payouts.cancel("po_1")
    client.v1.payouts.reverse("po_1")
    client.v1.subscriptions.update("sub_1", params={"cancel_at_period_end": True})
    stripe.Customer.tax_ids_request("post", "/v1/customers/cus_1/tax_ids")
    stripe.Customer.cash_balance_transactions_request("get", "/v1/customers/cus_1/cash_balance_transactions")
    stripe.PaymentIntent.amount_details_line_items_request("get", "/v1/payment_intents/pi_1/amount_details_line_items")
    stripe.Account.capabilitys_request("post", "/v1/accounts/acct_1/capabilities/card_payments")
    stripe.Account.external_accounts_request("delete", "/v1/accounts/acct_1/external_accounts/ba_1")
    stripe.Account.login_links_request("post", "/v1/accounts/acct_1/login_links")
    stripe.Account.persons_request("delete", "/v1/accounts/acct_1/persons/person_1")
    stripe.billing.Meter.event_summarys_request("get", "/v1/billing/meters/mtr_1/event_summaries")
    stripe.Product.features_request("post", "/v1/products/prod_1/features")
    stripe.Invoice.lines_request("post", "/v1/invoices/in_1/lines")
    stripe.Charge.refunds_request("post", "/v1/charges/ch_1/refunds")
    stripe.Transfer.reversals_request("post", "/v1/transfers/tr_1/reversals")
def reads(client, db, row):
    stripe.Subscription.list(customer="cus_1")
    stripe.Subscription.retrieve("sub_1")
    client.customers.retrieve("cus_1")
    run_on_stripe_threads(stripe.Customer.retrieve, "cus_1")
    client.v1.subscriptions.retrieve("sub_1").items
    db.delete(row)
    customers = {"cus_1"}
    customers.update({"cus_2"})
    stripe.Customer.list_balance_transactions("cus_1")
def outside_the_rule(client):
    stripe.checkout.Session.create(mode="subscription", subscription_data={
        "trial_period_days": 7, "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}}})
    stripe.Coupon.create(percent_off=50)
    client.v1.promotion_codes.create(params={"coupon": "co_1"})
    stripe.Topup.create(amount=100, currency="usd")
    stripe.PaymentIntent.capture("pi_1", amount_to_capture=50)
    stripe.PaymentMethod.detach("pm_1")
    client.v1.invoices.attach_payment("in_1", params={"payment_record": "pr_1"})
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
    customers = client.v1.customers
    customers.update("cus_1", params={"balance": -500})
    _subscriptions(client).cancel("sub_1")
    stripe.Customer.create(balance=-500)
    fetched = stripe.Subscription.retrieve("sub_1")
    fetched.cancel_at_period_end = True
    fetched.save()
    getattr(stripe.Subscription, "del" + "ete")("sub_1")
    client.raw_request("delete", "/v1/subscriptions/sub_1")
    stripe.Subscription._static_request("delete", "/v1/subscriptions/sub_1")
    stripe.Subscription.retrieve("sub_1")._request("delete", "/v1/subscriptions/sub_1")
    httpx.delete("https://api.stripe.com/v1/subscriptions/sub_1")
'''
    assert _money_moves(planted) == [
        ("resource_forms", "Subscription.delete"), ("resource_forms", "Refund.create"),
        ("resource_forms", "Customer.delete"), ("resource_forms", "Subscription.delete"),
        ("resource_forms", "Refund.create"), ("resource_forms", "Subscription.cancel"),
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
        ("cancel_or_credit_by_update", "InvoiceItem.modify"), ("cancel_or_credit_by_update", "invoice_items.update"),
        ("cancel_or_credit_by_update", "Invoice.add_lines"), ("cancel_or_credit_by_update", "invoices.add_lines"),
        ("cancel_or_credit_by_update", "Invoice.update_lines"), ("cancel_or_credit_by_update", "invoices.update_lines"),
        ("cancel_or_credit_by_update", "Invoice.remove_lines"), ("cancel_or_credit_by_update", "invoices.remove_lines"),
        ("cancel_or_credit_by_update", "InvoiceLineItem.modify"), ("cancel_or_credit_by_update", "line_items.update"),
        ("cancel_or_credit_by_update", "customers.update"), ("cancel_or_credit_by_update", "customers.create"),
        ("the_swept_surface", "Subscription.create"), ("the_swept_surface", "subscriptions.create"),
        ("the_swept_surface", "SubscriptionSchedule.create"), ("the_swept_surface", "subscription_schedules.create"),
        ("the_swept_surface", "Invoice.pay"), ("the_swept_surface", "invoices.pay"),
        ("the_swept_surface", "CreditGrant.modify"), ("the_swept_surface", "credit_grants.update"),
        ("the_swept_surface", "MeterEventAdjustment.create"),
        ("the_swept_surface", "meter_event_adjustments.create"),
        ("the_swept_surface", "Meter.deactivate"), ("the_swept_surface", "meters.deactivate"),
        ("the_swept_surface", "Order.cancel"), ("the_swept_surface", "orders.cancel"),
        ("the_swept_surface", "Topup.cancel"), ("the_swept_surface", "topups.cancel"),
        ("the_swept_surface", "OutboundPayment.cancel"), ("the_swept_surface", "outbound_transfers.cancel"),
        ("the_swept_surface", "InboundTransfer.cancel"), ("the_swept_surface", "credit_reversals.create"),
        ("the_swept_surface", "DebitReversal.create"), ("the_swept_surface", "Topup.cancel"),
        ("the_swept_surface", "Customer.sources_request"),
        ("the_swept_surface", "Customer.balance_transactions_request"),
        ("the_swept_surface", "balance_transactions.create"), ("the_swept_surface", "refunds.create"),
        ("the_swept_surface", "reversals.create"),
        ("the_swept_surface", "Subscription.cancel"), ("the_swept_surface", "Invoice.void_invoice"),
        ("each_other_row", "ApplicationFee.refund"),
        ("each_other_row", "CreditGrant.expire"),
        ("each_other_row", "CreditGrant.void_grant"),
        ("each_other_row", "CreditNote.create"),
        ("each_other_row", "CreditReversal.create"),
        ("each_other_row", "Customer.create_balance_transaction"),
        ("each_other_row", "Invoice.delete"),
        ("each_other_row", "Invoice.mark_uncollectible"),
        ("each_other_row", "InvoiceItem.delete"),
        ("each_other_row", "OutboundTransfer.cancel"),
        ("each_other_row", "PaymentIntent.cancel"),
        ("each_other_row", "Payout.cancel"),
        ("each_other_row", "Payout.reverse"),
        ("each_other_row", "Reader.refund_payment"),
        ("each_other_row", "Subscription.modify"),
        ("each_other_row", "Subscription.pause"),
        ("each_other_row", "SubscriptionItem.delete"),
        ("each_other_row", "Transfer.create_reversal"),
        ("each_other_row", "credit_notes.create"),
        ("each_other_row", "customers.delete"),
        ("each_other_row", "debit_reversals.create"),
        ("each_other_row", "disputes.close"),
        ("each_other_row", "inbound_transfers.cancel"),
        ("each_other_row", "invoice_items.delete"),
        ("each_other_row", "invoices.mark_uncollectible"),
        ("each_other_row", "outbound_payments.cancel"),
        ("each_other_row", "payment_intents.cancel"),
        ("each_other_row", "payouts.cancel"),
        ("each_other_row", "payouts.reverse"),
        ("each_other_row", "subscriptions.update"),
        ("each_other_row", "Customer.tax_ids_request"),
        ("each_other_row", "Customer.cash_balance_transactions_request"),
        ("each_other_row", "PaymentIntent.amount_details_line_items_request"),
        ("each_other_row", "Account.capabilitys_request"),
        ("each_other_row", "Account.external_accounts_request"),
        ("each_other_row", "Account.login_links_request"),
        ("each_other_row", "Account.persons_request"),
        ("each_other_row", "Meter.event_summarys_request"),
        ("each_other_row", "Product.features_request"),
        ("each_other_row", "Invoice.lines_request"),
        ("each_other_row", "Charge.refunds_request"),
        ("each_other_row", "Transfer.reversals_request"),
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

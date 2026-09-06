# Observed invoice payments

E06 adds forward payment evidence for a bounded report. It does not establish current MRR,
ARR, net revenue, churn or historical completeness. Checkout completion and a $0 beta invoice
are not proof of a paying subscriber.

## Event and transaction boundary

Only `invoice_payment.paid` writes `earningsnerd_billing_payments`. The signed InvoicePayment
supplies its allocation amount, currency, payment type, mode and paid timestamp. The invoice
read supplies customer/subscription references and advisory billing-cycle classification.
The shared bounded Stripe reader makes one invoice request with zero SDK retries and closes
its dedicated transport on success or failure. Connect/read limits are phase/inactivity limits,
not a total deadline. A missing or invalid provider response returns retryable HTTP 503 and
records neither the payment nor its event receipt. Invalid signed payment evidence returns 400.

The existing webhook worker owns the session and transaction. It releases the receipt-read
transaction before retrieving the invoice, then locks any unambiguously attributed User and
rechecks ownership. Invoice enrichment does not update entitlements; it does not need the
subscription reconciler's lock-before-provider ordering. Payment and StripeEvent commit together.
The `(stripe_payment_id, livemode)` primary key also deduplicates separate event IDs for the same
allocation. Account-lock contention returns 503; another database failure rolls back and returns
500 for Stripe retry. A repeated processed event performs no provider read. Best-effort PostHog
capture happens after commit and session closure; the database is the report's source.

Customer matches across User and Subscription must resolve to exactly one account, without a
conflicting subscription owner. Missing/ambiguous attribution retains only the payment/invoice
and event references required for evidence and dedup, amount/time/classification fields, and
an explicit reason. It stores no customer/subscription ID, beta/invite label or synthetic person.
A late payment for an old subscription can belong to the same customer without changing the
account's current subscription. No billing replacement policy follows from this telemetry.

## Reading the report

From `backend`, against an authorized database:

```bash
python scripts/billing_revenue_report.py --since 2026-09-01 --until 2026-10-01
```

The read-only interval is `[since, until)` by payment time; date-only arguments mean UTC.
`--test-mode` reports only test-mode observations. Default output includes live mode only.
Amounts remain integer currency minor units: never assume two decimals or add currencies.

Collected subscription totals include positive `payment_intent` and `charge` allocations with
an invoice subscription reference. Zero amounts, external `payment_record`/unknown types and
manual/non-subscription invoices remain stored but are excluded, with exclusion counts. Gross
qualifying unattributed amounts remain visible separately and never create a paying-user count.
Distinct users mean observed subscription payers in the window, not currently active subscribers.
First observed payment cohorts use the earliest retained qualifying paid timestamp, even when
an earlier payment arrives later. Window rows and their first-payment timestamps share one SQL
statement snapshot. Earliest retained observation is a separate coverage-metadata read and can
see a later commit; the report does not claim a transaction-wide atomic snapshot. Beta/invite labels are observation-time labels, not a proof of
historical enrollment. Conflicting labels at a tied first timestamp remain unknown.

Billing-cycle payment/invoice counts are grouped within each currency. Classification requires
a complete invoice line page and one configured monthly/yearly price ID. Truncated, missing,
mixed or unknown prices remain unknown. Separate allocations for an edited invoice can carry
different observed classifications; category invoice counts are not guaranteed additive.

Refunds, credit notes, disputes, tax adjustments and fees are not netted. Events not delivered
and past payments are not backfilled. Account deletion cascades attributed rows through the
existing account-erasure flow, so historical app totals can change. This is not an accounting
retention system. The JSON output repeats these limitations and earliest retained observation.

## Release and coverage checks

Before claiming coverage, verify the production webhook endpoint's selected events and API
version read-only. Enabling an event or changing that endpoint/version remains a founder action;
E06 does neither. The development SDK is pinned to Stripe 15.6.1; its default API version does
not establish the deployed webhook version. Unsupported signed shapes fail explicitly.

Gates: `backend/tests/unit/test_billing_revenue.py` covers evidence, money, attribution,
classification, cohort time and account deletion. The existing
`backend/tests/integration/test_subscription_event_transactions.py` covers rollback, provider
shape failures and real PostgreSQL duplicate delivery. The existing migration CI job applies
all SQL, proves ledger skipping, resets the test ledger and safely replays all files.

Account exports (`GET /api/users/export`) include every retained observation attributed to the
requesting account in `billing_payments`, including live and test modes and optional unknown
fields. Other accounts and unattributed allocations are excluded. UTC payment/observation times
are serialized with `Z`; this export does not change the report's revenue exclusions.

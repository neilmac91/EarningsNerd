# Measure observed payment allocations before claiming paid subscribers

Date: 2026-09-06   Area: arch

**Context:** Beta checkout succeeds at $0. Invoice-paid events can also represent off-Stripe
payments. Invoice totals and payment allocations differ, and a retrieved invoice line page can
be incomplete. Neither checkout activation nor a partial price page establishes collected
subscription revenue or billing mix.

**Rule:** Preserve canonical allocation identity, integer minor units and mode; reject conflicting
immutable evidence. Resolve customer ownership without a first-match guess. Count only positive
supported Stripe-collected subscription allocations as observed payers, classify truncated/mixed
price evidence as unknown, and use retained paid time for first-observed cohorts. Read window rows and cohort timestamps
in one SQL statement so concurrent first payments cannot outgrow a stale lookup. Payment/event
rows commit together. Follow existing account deletion semantics; do not quietly create a new
financial-retention policy. Keep coverage/refund/credit limits in the report itself.

**Gate:** `backend/tests/unit/test_billing_revenue.py` checks allocation conflict/dedup,
attribution, zero/type/mode/currency boundaries, complete invoice identity and price pages,
cohort arrival ordering, and ORM deletion. `backend/tests/integration/test_subscription_event_transactions.py`
checks payment/event rollback, provider-shape retries, concurrent PostgreSQL deliveries and a
first-payment insert between report reads.
One bounded mutation of each new invariant produced the intended failure on committed E06 source;
the shared transport/worker invariants also retain E05b/E05c gates.

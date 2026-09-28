# Pro offer — approved September 28, 2026; activation held

The founder approved **$23/month or $190/year** for the focused individual-investor offer,
conditional on quality acceptance and controlled-beta readiness. This supersedes the historical
price-decision hold in [handover §5](../tasks/handover-astra-2026-09-19.md#5-what-remains--reconciled-open-list).
The amount decision is complete; implementation and catalog preparation do not establish launch readiness.

| Cycle | USD charge | Display |
| --- | --- | --- |
| Monthly | $23 each month (2,300 cents) | $23/month |
| Annual | $190 once per year (19,000 cents) | $15.83/month equivalent, billed $190 annually |

Twelve monthly payments total $276. Annual saves **$86**, or **31%** rounded from 31.159%.
The rounded monthly equivalent is not a monthly installment. “Two months free” is retired.

The plain [price module](../frontend/app/pricing/prices.ts) is shared by the pricing page,
homepage section and server Product/Offer JSON-LD. The live `pricing-experiment`/`price_29`
display experiment and its exposure event are retired. Existing analytics history and the
separate landing-headline experiment remain intact. Checkout analytics use the selected full
cycle amount, while the server remains authoritative for the actual charge.

## Retained catalog state

The September 28 Stripe readback confirmed staged **inactive** live-catalog prices at the
approved USD amounts and monthly/yearly cadence. Production checkout bindings still point to
the old $39/month and $390/year offer. The beta promotion's valid 100%-off-forever linkage and
the account's enabled charges/payouts with no currently-due requirements were also read back.
The dated operator receipt retains the exact catalog identifiers; none belong in frontend code.
This is a preparation snapshot, not evidence of a configured or completed new-price checkout.
The default billing portal has subscription updates disabled, so no portal price-switch allowlist
needs changing. Its existing period-end cancellation and payment-method/invoice features remain.

## Activation checklist

Keep this change held as a draft until the quality and controlled-beta acceptance gates are
recorded. The approved price does not waive those gates or authorize customer recruitment.

1. Record quality acceptance and controlled-beta readiness, reconcile the separate trial-routing
   work, and review the final combined source and deployment gates.
2. Re-read the staged prices: correct product, USD, 2,300/month and 19,000/year, recurring cadence
   and intended tax treatment. Preserve existing subscriptions, old prices and the beta promotion.
3. Activate the new catalog prices and update the backend's `STRIPE_PRICE_MONTHLY_ID` and
   `STRIPE_PRICE_YEARLY_ID` through the normal deployment/configuration process. Retain the
   effective serving bindings and verification that new checkouts select the approved amounts.
   **Complete and verify this step before publishing the lower frontend prices.**
4. Publish the reviewed frontend and verify the exact deployment: homepage, pricing page,
   JSON-LD, both cycle selections, annual total/equivalent/savings and checkout agreement.
   The backend-first transition is not atomic: an old page may briefly advertise the higher
   price while checkout offers the lower one. Complete both readbacks before admitting a paid cohort.
5. Retain deployment/configuration receipts and subsequent natural payment evidence separately.
   A local gate, catalog readback or draft PR does not prove a live checkout or payment.

Preserve current paid subscriptions and renewal terms; this is a new-purchase offer, not a
subscription migration. Preserve beta Pro at $0 with its existing no-card promotion. Trial
duration, monthly-only eligibility, account-state guards, repeat-subscriber restrictions and
the `PRO_TRIAL_DAYS` / `NEXT_PUBLIC_ENABLE_PRO_TRIAL` lockstep are separate decisions; this
price change does not flip them. The controlled beta's email response commitment is not a
new paid-plan SLA.

## Rollback

A frontend rollback must retain the lower backend bindings while a lower-price page or cached
tab can still submit checkout. Do not restore higher charge bindings underneath those pages.
If a higher-price restoration is required, first establish and verify an explicit checkout
pause procedure; no such pause switch is introduced or assumed by this change. Existing
subscriptions and beta entitlements remain untouched during rollback.

## Verification

`PricingPage.spec.tsx` exercises the rendered offer across both frontend surfaces and JSON-LD
with a stale `price_29` flag, cycle changes and checkout analytics. `pricing-section.spec.tsx`
retains billing-toggle, access-mode, beta and trial-copy coverage. The server-render guard and
full lint, TypeScript, Vitest and Next build gates remain required. A committed-state mutation
of the JSON-LD amount must fail the cross-surface gate, then pass after exact restoration.
These checks establish frontend consistency; effective Stripe configuration remains an
operator verification at activation.

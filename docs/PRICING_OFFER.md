# Pro offer

Pro is **$25 per month**, or **$240 per year** billed annually, advertised as **$20 per month**.
It has been live since 2026-10-11: the backend bindings were switched and verified before #1009
published the pages, and that PR's merge commit records the readbacks. Any change to the offer is a
production price change, which stays on the founder-held list
([handover §5](../tasks/handover-astra-2026-09-19.md#5-what-remains--reconciled-open-list)).
Implementation and catalog preparation do not establish launch readiness.

| Cycle | USD charge | Display |
| --- | --- | --- |
| Monthly | $25 each month (2,500 cents) | $25/month, billed monthly |
| Annual | $240 once a year (24,000 cents) | $20/month, billed annually at $240 |

Twelve monthly payments total $300, so the $240 annual charge saves **$60** a year, **20%**. The
pricing page and the homepage section both open on annual, which makes **$20/month** the headline
price. It is the annual charge divided by twelve, not a monthly installment: the annual card
states the $240 charge directly beneath it.

The plain [price module](../frontend/app/pricing/prices.ts) is shared by the pricing page,
homepage section and server Product/Offer JSON-LD. Every displayed amount and saving, including
the "save 20%" toggle badges, is computed from it; the percent rounds down, so it never overstates
the saving. The `pricing-experiment`/`price_29` display
experiment and its exposure event are retired; existing analytics history and the separate
landing-headline experiment remain intact. Checkout analytics record the selected cycle's full
charge (25 or 240), while the server remains authoritative for the actual charge.

## Catalog preparation

The Pro product needed live USD Prices of **2,500 cents a month** and **24,000 cents a year**,
created inactive until step 3, while the serving bindings still selected the previous Prices; both
are now active and bound. Leave every other inactive Pro Price inactive. Catalog identifiers and
readbacks belong in the private operator receipt, never in this repository or frontend code.

The pricing introduction and FAQ describe the billing controls the default Customer Portal offers
(period-end cancellation, payment method and invoices) without promising immediate plan changes.
The existing trial-cancellation terms are unchanged.

## Read-only agreement check

After an authorized operator captures the effective serving backend bindings and fresh Stripe
catalog readbacks, compare that supplied snapshot with the shared `PRO_PRICING` module:

```sh
cd frontend
npm run check:pricing -- /path/to/operator-readback.json
```

Use the repository's Node 22 runtime. This local command reads one JSON file and prints a result;
it makes no Stripe, backend or checkout request and changes no catalog, configuration or account.
The JSON envelope is:

```json
{
  "bindings": {
    "STRIPE_PRICE_MONTHLY_ID": "<effective serving monthly Price ID>",
    "STRIPE_PRICE_YEARLY_ID": "<effective serving yearly Price ID>",
    "product_id": "<intended Pro Product ID from the catalog receipt>"
  },
  "product": { "...": "full live Product readback" },
  "prices": {
    "monthly": { "...": "full live monthly Price readback" },
    "yearly": { "...": "full live yearly Price readback" }
  }
}
```

Replace the placeholders with actual readbacks. The binding IDs must come from the effective
serving backend revision, not merely proposed environment values. Supply unexpanded `Price.product`
IDs. Retain the source revision, readback time and serving revision with the operator receipt.
The [Stripe Price schema](https://docs.stripe.com/api/prices/object) defines the checked fields.

The check requires distinct, correctly bound monthly/yearly Prices; an active live Product and
Prices on the intended product; USD fixed per-unit whole-cent amounts matching `PRO_PRICING`;
licensed recurring usage once per month/year; and explicit null custom-amount and quantity-transform
fields. A conflicting decimal amount also fails. Missing or malformed evidence is not agreement.
Exit 0 means the supplied snapshot agrees; exit 1 means a catalog/binding disagreement; exit 2 means
an unreadable file, invalid JSON or incorrect invocation. The command does not authenticate the
snapshot, establish freshness, inspect a real Checkout Session, determine tax/discount/trial totals,
or prove existing customers' renewal terms. Those remain separate activation checks below.

#1009's merge commit records that this check passed on the serving bindings at activation. Passing
it never authorizes a price change by itself. Do not change catalog activity or backend bindings
merely to make it pass. The [machine checks](#machine-checks) below compare the bound amounts with
the page continuously; this readback stays the evidence for what they omit.

## Machine checks

The step order and the rollback rule below protect one invariant: checkout never charges more than
the live page shows, and at rest the two agree. The backend reports what its bindings charge, so
the invariant is checked without Stripe credentials in CI:

- **The serving charge report.** `GET https://api.earningsnerd.io/api/subscriptions/prices`
  returns, per cycle, the bound Price's fixed charge (`amount_cents`, `currency`, `interval`,
  `interval_count`) or the `problem` that leaves it without one: `unconfigured`, `unavailable`,
  `inactive`, `test_mode` or `not_fixed_recurring`. It carries no Price or Product ID. Each backend
  process keeps a report of two charges for ten minutes and reads anything less again after a
  minute. One read runs at a time, and no request waits on another request's read
  (`backend/app/services/billing_serving_prices.py`).
- **Before a page is published.** The `price-agreement` job in `.github/workflows/ci.yml` runs on
  every pull request that changes `frontend/app/pricing/prices.ts`. It fails while production
  checkout charges more than the new page would show: bind the lower Prices (step 3), then re-run
  it. A raise passes, because the page then shows at least the charge. An unreachable production
  API fails the job. On any other pull request it is skipped, which a required check counts as
  passing, so it can be made required. Until it is, a red job holds back an agent, which never
  merges a red pull request, but not a person's merge.
- **Every day.** `prod-smoke.yml` compares the report with the offer the live pricing page
  publishes (its Product/Offer JSON-LD) and fails on a disagreement in either direction, opening or
  updating its failure issue. Reading the live page means it also sees a Vercel rollback, a deploy
  from outside `main` or a failed frontend deploy. It finds a higher Price bound under the lower
  pages, a raise whose bindings were never moved and an archived Price.
- **By hand, after any binding change.** From `frontend/`:
  `curl -fsS https://api.earningsnerd.io/api/subscriptions/prices -o serving.json` and
  `curl -fsSL https://www.earningsnerd.io/pricing -o pricing.html`, then
  `npm run check:pricing -- --serving --page pricing.html serving.json` (exit 0 agree, 1 disagree,
  2 no evidence). Without `--page` it compares with this checkout's `PRO_PRICING`;
  `--serving --publishing` applies the pre-publication rule instead.

Limits. A binding change is an operator action outside CI, so nothing prevents a higher Price
under a lower page, and the same holds for a frontend rollback: the daily run finds either within a
day, the manual check at once. The report proves the bound Prices' amount, currency, cadence and
state only; the operator readback above remains the evidence that the bindings name the intended
Pro Product, and neither proves tax, discount or trial totals, the beta promotion or existing
customers' renewal terms. Making `price-agreement` a required check is a founder setting. Gate:
`backend/tests/unit/test_price_agreement_checks.py`.

## Activation checklist

This checklist was written for #1009, which merged after step 3 was completed and verified; it
remains the order for a future price change. Keep this change a draft until the founder releases
it after quality acceptance and controlled-beta readiness are recorded. The set price does not
waive those gates or authorize customer recruitment.

1. Record quality acceptance and controlled-beta readiness, and review the final combined source
   and deployment gates.
2. Re-read, and record in the private operator receipt: the new Prices (correct product, USD,
   2,500/month and 24,000/year, recurring cadence and intended tax treatment); the beta promotion's
   100%-off-forever linkage; and the default Customer Portal's subscription-update setting. If
   subscription updates are enabled there, add both new Prices to its allowed products and revisit
   the FAQ's billing-cycle answer in the same change. Preserve existing subscriptions, old Prices
   and the beta promotion.
3. Activate the new catalog prices and update the backend's `STRIPE_PRICE_MONTHLY_ID` and
   `STRIPE_PRICE_YEARLY_ID` through the normal deployment/configuration process. Retain the
   effective serving bindings and verification that new checkouts select the set amounts.
   **Complete and verify this step before publishing the lower frontend prices.** The
   `price-agreement` CI job fails the publishing pull request until it is done.
4. Publish the reviewed frontend and verify the exact deployment: the homepage and pricing page
   open on annual at $20/month billed $240 with the $60 saving, monthly shows $25, the JSON-LD
   carries 25 and 240, and checkout agrees. The backend-first transition is not atomic: an old
   page may briefly advertise the higher price while checkout offers the lower one. Complete both
   readbacks before admitting a paid cohort.
5. Retain deployment/configuration receipts and subsequent natural payment evidence separately.
   A local gate, catalog readback or draft PR does not prove a live checkout or payment.

Preserve current paid subscriptions and renewal terms; this is a new-purchase offer, not a
subscription migration. Preserve beta Pro at $0 with its existing no-card promotion. Trial
duration, monthly-only eligibility, account-state guards, repeat-subscriber restrictions and
the `PRO_TRIAL_DAYS` / `NEXT_PUBLIC_ENABLE_PRO_TRIAL` lockstep are separate decisions; this
price change does not flip them.

After step 3, positive renewal payments on the previous Prices count under an `unknown` billing
cycle in the payment report, because classification matches only the configured bindings
([Reading the report](observed-invoice-payments.md#reading-the-report)); amounts, payer counts and
access are unaffected. Read a legacy renewal's cycle from Stripe.

Existing display limitation: the pricing page shows the public offer alongside “Current Plan”
for paid users; it does not read their actual Stripe subscription amount. That pre-existing
behavior is retained. Verify the subscription's billing details separately when checking
customer preservation; the public price is not evidence of that customer's renewal amount.

## Rollback

A frontend rollback must retain the lower backend bindings while a lower-price page or cached
tab can still submit checkout. Do not restore higher charge bindings underneath those pages; the
daily agreement check reports it if that happens, but cannot prevent it.
If a higher-price restoration is required, first establish and verify an explicit checkout
pause procedure; no such pause switch is introduced or assumed by this change. Existing
subscriptions and beta entitlements remain untouched during rollback.

## Verification

`PricingPage.spec.tsx` renders the offer across the pricing page, homepage section and JSON-LD
with a stale `price_29` flag, both cycles and checkout analytics. `pricingFollowsModule.spec.tsx`
renders the same surfaces, the beta strike-through and checkout analytics under other amounts, and
fails on any figure of the real offer (read from the unmocked module) or a typed "months free"
claim. `pricing-section.spec.tsx` keeps billing-toggle, access-mode, beta and trial-copy coverage.
`pricingAgreement.spec.ts` covers the read-only agreement check and the `--serving` comparison in
both modes, and runs `npm run check:pricing` itself for exit codes 0, 1 and 2.
`test_serving_prices.py` pins the serving charge report (fields, problems, no identifiers, caching
and the bounded Stripe read); `test_price_agreement_checks.py` pins both workflows. The
server-render guard and the full lint, TypeScript, Vitest and Next build gates remain required.
Exact gate and mutation-proof tails for each reviewed head belong in the PR body (`AGENTS.md` §4,
§7), not in this document.
These checks establish frontend consistency and, through the serving charge report, agreement with
the bound amounts; the rest of the effective Stripe configuration remains an operator verification.

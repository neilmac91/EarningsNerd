# Never let checkout charge more than the page shows: lower a price on the backend first, raise it on the page first

Date: 2026-10-11   Area: ops

**Context**: The pricing pages show `PRO_PRICING`; checkout charges the Stripe Prices that
`STRIPE_PRICE_MONTHLY_ID` and `STRIPE_PRICE_YEARLY_ID` select, which an operator sets on the Cloud
Run service outside CI. `docs/PRICING_OFFER.md` ordered the 2026-10-11 switch backend first and
forbade restoring higher bindings under the lower pages, but both rules were prose, and agreement
was checked only by hand on an operator's snapshot. No CI job could read the serving bindings
without Stripe credentials in CI, which are the founder's to grant, so the backend now reports
what its bindings charge, without IDs, and the checks read that report.

**Rule**: Checkout never charges more than the live page shows, and at rest the two agree. Lower a
price by binding the lower Prices on the backend first, then publish the page. Raise one by
publishing the page first, and bind the higher Prices only under a verified checkout pause
procedure (`docs/PRICING_OFFER.md`, "Rollback"): a cached tab of the lower page can still submit
checkout. After any binding change or frontend rollback, compare by hand (`docs/PRICING_OFFER.md`,
"Machine checks": `npm run check:pricing -- --serving --page pricing.html serving.json`).

**Evidence**: `GET /api/subscriptions/prices` (`backend/app/services/billing_serving_prices.py`,
`backend/tests/unit/test_serving_prices.py`) reports each bound Price's fixed charge or the
problem that leaves it without one. The `price-agreement` job in `.github/workflows/ci.yml` fails
a pull request that changes `frontend/app/pricing/prices.ts` while production checkout charges
more than the new page shows; `prod-smoke.yml` compares the report with the live page's offer
daily and opens its issue on any disagreement (`backend/tests/unit/test_price_agreement_checks.py`;
verdicts in `frontend/tests/unit/pricingAgreement.spec.ts`). A binding change or a frontend
rollback happens outside CI, so a higher Price under a lower page is found by the next daily run
or the manual check, never prevented; that clause stays session reading.

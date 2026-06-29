# Task: Fake-door $39-vs-$29 price test (roadmap item 2.3)

Measure willingness-to-pay by A/B-testing the displayed Pro price ($39 control vs $29 test). Both
arms route to the **existing** checkout — beta members still pay $0 via the forever promo; the
charge logic is untouched. The signal is `checkout_started{variant}` (and the already-firing
`pricing_experiment_exposed{variant}`), analyzable as an exposed→checkout funnel split by arm.

## Recon findings (the infra already exists)
- `pricing/page.tsx:30` already reads `useFeatureFlagVariantKey('pricing-experiment')`; `:76-82`
  already fires `pricing_experiment_exposed{variant}`. Both currently unused for the price.
- `:121` hardcodes `priceConfig = { monthly: 39, yearly: 390, … }`; `handleUpgrade` (`:100-114`)
  already calls `analytics.checkoutStarted('pro', priceValue, billingCycle)`.
- Backend checkout is variant-agnostic; $0 is server-side via `is_beta` + `STRIPE_BETA_PROMO_CODE_ID`
  with `payment_method_collection:"if_required"`. **Display-only fake-door → no backend change, no
  new Stripe price.**

## Decisions (per approved roadmap "$39 vs $29" + safe-default design)
- **control / undefined / PostHog-down → $39/$390** (current anchor; zero-regression default).
- **`price_29` variant → $29/$290** (annual stays 10×, matching the $39→$390 pattern).
- **Frontend-only.** No charge-path change; the test measures intent (checkout_started), not real
  conversions (those stay gated by the existing beta/$0 logic).
- **Founder owns** the PostHog flag `pricing-experiment` (variants `control` + `price_29`, rollout %).
  Until it's created, everyone sees $39 (safe default) and no exposure fires.

## Plan
- [ ] `analytics.ts`: add optional `variant?: string` to `checkoutStarted`; include it in props when present.
- [ ] `pricing/page.tsx`: replace the static `priceConfig` with a variant-aware pick
      (`price_29` → $29/$290; else control $39/$390); pass the variant (`'control'` when unset) into
      `checkoutStarted`. The strike-through/period text already derive from `priceConfig`, so they
      follow automatically.
- [ ] `PricingPage.test.tsx`: make the `useFeatureFlagVariantKey` / `createCheckoutSession` /
      `checkoutStarted` mocks controllable; add tests — control arm shows $390, `price_29` shows $290,
      and clicking Upgrade fires `checkout_started` with the arm's price + variant.

## Verify
- [ ] `npm run typecheck` (tsconfig.ci.json) · `npm run lint --max-warnings 0` · full `vitest`.
- [ ] Existing PricingPage tests stay green (default mock = undefined → $39 control, unchanged).
- [ ] CI green on the pushed branch; open as a draft PR (per-item convention).

## Notes
- Surgical + reuse-first: leans entirely on the pre-wired flag read + exposure event; ~1 new line of
  real logic + analytics plumbing. No backend, no API-contract, no Stripe price, no eval impact.

## Review
- **Surgical, as scoped.** Two real changes: (1) `priceConfig` is now a variant pick — `price_29` →
  $29/$290, everything else → the $39/$390 control; (2) the variant ('control' when unset) flows into
  `checkout_started`. The existing flag read + exposure event needed no change. No backend, no API,
  no Stripe price, no eval surface.
- **Zero-regression default.** Flag unset / PostHog down → $39 control, identical to today. Existing
  PricingPage tests (mock returns undefined) stayed green untouched.
- **Tests:** made the flag/checkout/analytics mocks controllable; added 3 — control shows $390,
  `price_29` shows $290, and a click fires `checkout_started('pro', 290, 'yearly', 'price_29')` +
  `createCheckoutSession('price_pro_yearly')`.
- **Verified:** `npm run typecheck` clean · `npm run lint --max-warnings 0` clean · vitest 50 files /
  228 tests (was 225; +3).
- **Founder action (not code):** create the `pricing-experiment` PostHog flag (variants `control` +
  `price_29`, e.g. 50/50) to start the test; until then everyone sees $39.

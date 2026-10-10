# Compute every displayed Pro price and saving claim from PRO_PRICING; never type one

Date: 2026-10-10   Area: frontend

**Context**: The founder set the Pro offer three times on PR #1009 before it shipped. Each
time, the per-cycle figures followed `frontend/app/pricing/prices.ts`, but both toggle badges
("(2 months free)" on `/pricing`, "· 2 months free" on the homepage) were typed text. At $25 a
month and $240 a year the annual plan saves 20%, or 2.4 months, so the typed badge would have
published a false saving. The existing cross-surface test asserted the typed badge as a literal,
so it would have kept passing.

**Rule**: Every amount, per-month equivalent and saving (dollars, percent or months free) that a
pricing surface shows comes from `PRO_PRICING`, computed by `proPricing(monthly, yearly)`. No
surface types a price or a saving. A new surface that shows a Pro price joins
`pricingFollowsModule.spec.tsx`.

**Evidence**: `frontend/tests/unit/pricingFollowsModule.spec.tsx` renders the pricing page, the
homepage section, the Product JSON-LD and checkout analytics at $30/$270. It fails on any shipped
figure or "months free" text left on the page. It covers those two surfaces only, so the "new
surface" clause is review-checked. The literal offer stays pinned in `PricingPage.spec.tsx`.

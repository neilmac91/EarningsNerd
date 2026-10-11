# Compute every displayed Pro price and saving claim from PRO_PRICING; never type one

Date: 2026-10-10   Area: frontend

**Context**: The per-cycle figures on the pricing page and the homepage section came from
`frontend/app/pricing/prices.ts`, but both toggle badges ("(2 months free)" on `/pricing`, "· 2
months free" on the homepage) were typed text, true only while the annual price was exactly ten
monthly payments. Setting the offer to $25 a month and $240 a year makes the saving 20%, or 2.4
months, so the typed badge would have published a false saving. The cross-surface test asserted
the typed badge as a literal and would have kept passing.

**Rule**: Every amount, per-month equivalent and saving (dollars, percent or months free) that a
pricing surface shows comes from `PRO_PRICING`, computed by `proPricing(monthly, yearly)`; the
percent rounds down, so the advertised saving never exceeds the real one. No surface types a
price or a saving. A new surface that shows a Pro price joins `pricingFollowsModule.spec.tsx`.

**Evidence**: `frontend/tests/unit/pricingFollowsModule.spec.tsx` renders the pricing page (free
and beta member), the homepage section, the Product JSON-LD and checkout analytics on both cycles
at $30/$270. It fails on any figure of the real offer (read from the unmocked module) or on
"months free" text left on the page. It covers those surfaces only, so the "new surface" clause is
review-checked. The literal offer stays pinned in `PricingPage.spec.tsx`.

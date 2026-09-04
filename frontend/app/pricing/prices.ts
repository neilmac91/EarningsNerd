// Pricing anchor: $39/mo · $390/yr (annual = 2 months free) — the prosumer-band anchor the council
// set (kill $14, which reads as "toy" for an accountability product). Beta members still pay $0 via
// the 100%-off forever promo; this only changes the displayed/anchored price + the analytics value.
//
// Fake-door $39-vs-$29 A/B (roadmap 2.3): the `pricing-experiment` PostHog flag picks the arm.
// Display-only — both arms route to the same checkout, so the charge path is unchanged. Only the
// explicit `price_29` arm lowers the anchor; an unset/missing flag (or PostHog being down) falls
// through to the $39 control, so there's no regression if the experiment isn't configured.
//
// Plain module (no 'use client') so BOTH the client page and the server layout (Product/Offer
// JSON-LD) read one source of truth — a `'use client'` module's exports can't be consumed by a
// Server Component (lessons/frontend-client-exports-need-next-build.md).
export const PRICE_VARIANTS = {
  control: { monthly: 39, yearly: 390, monthlyDisplay: '$39', yearlyDisplay: '$390' },
  price_29: { monthly: 29, yearly: 290, monthlyDisplay: '$29', yearlyDisplay: '$290' },
} as const

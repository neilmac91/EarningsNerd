// Pro offer: $25 per month, or $240 per year billed annually, advertised as $20 per month. Checkout
// must never charge more than the live page shows. Lower a price on the backend first: bind the
// lower Stripe Prices, then change it here. Raise one by publishing the higher page first (this
// change merged and deployed), then bind the higher Prices only under a verified checkout pause:
// a cached tab of the lower page can still submit checkout. docs/PRICING_OFFER.md has the steps
// and existing-customer protections; ci.yml's price-agreement job checks a change to this file
// against production's charge report.
// Keep this a plain module: the client pages and server Product/Offer JSON-LD share it. Every
// displayed amount and saving derives from here (gate: tests/unit/pricingFollowsModule.spec.tsx).
const usd = (amount: number) => (Number.isInteger(amount) ? `$${amount}` : `$${amount.toFixed(2)}`)

export function proPricing(monthly: number, yearly: number) {
  const annualSavings = monthly * 12 - yearly
  return {
    monthly,
    yearly,
    monthlyDisplay: usd(monthly),
    yearlyDisplay: usd(yearly),
    yearlyPerMonthDisplay: usd(yearly / 12),
    annualSavingsDisplay: usd(annualSavings),
    // Rounded down, so the advertised saving can never exceed the real one.
    annualSavingsPercent: Math.floor((annualSavings * 100) / (monthly * 12)),
  } as const
}

export const PRO_PRICING = proPricing(25, 240)

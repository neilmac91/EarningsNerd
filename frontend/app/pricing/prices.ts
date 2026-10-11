// Pro offer: $25 per month, or $240 per year billed annually, advertised as $20 per month. Publish
// only after the backend checkout prices match these amounts; see docs/PRICING_OFFER.md for the
// held activation sequence and existing-customer protections.
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

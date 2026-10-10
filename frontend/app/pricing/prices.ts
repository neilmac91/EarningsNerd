// Approved Pro offer: $19 per month, or $190 per year (two months free). Publish only after the
// backend checkout prices match these amounts; see docs/PRICING_OFFER.md for the held activation
// sequence and existing-customer protections.
// Keep this a plain module: the client pages and server Product/Offer JSON-LD share it.
const monthly = 19
const yearly = 190
const annualSavings = monthly * 12 - yearly

export const PRO_PRICING = {
  monthly,
  yearly,
  monthlyDisplay: `$${monthly}`,
  yearlyDisplay: `$${yearly}`,
  annualSavingsDisplay: `$${annualSavings}`,
  annualSavingsPercent: Math.round((annualSavings / (monthly * 12)) * 100),
} as const

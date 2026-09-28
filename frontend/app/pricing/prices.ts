// Approved Pro offer. Publish only after the backend checkout prices match these amounts;
// see docs/PRICING_OFFER.md for the held activation sequence and existing-customer protections.
// Keep this a plain module: the client pages and server Product/Offer JSON-LD share it.
const monthly = 19
const yearly = 190
const annualSavings = monthly * 12 - yearly

export const PRO_PRICING = {
  monthly,
  yearly,
  monthlyDisplay: `$${monthly}`,
  yearlyDisplay: `$${yearly}`,
  yearlyMonthlyDisplay: `$${(yearly / 12).toFixed(2)}`,
  annualSavingsDisplay: `$${annualSavings}`,
  annualSavingsPercent: Math.round((annualSavings / (monthly * 12)) * 100),
} as const

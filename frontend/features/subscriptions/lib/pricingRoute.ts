export type BillingCycle = 'monthly' | 'yearly'

/** The URL selects presentation only; checkout eligibility remains server-owned. */
export function billingCycleFromQuery(value: string | null): BillingCycle {
  return value === 'monthly' ? 'monthly' : 'yearly'
}

export function pricingHref(billingCycle: BillingCycle): string {
  return `/pricing?billing=${billingCycle}`
}

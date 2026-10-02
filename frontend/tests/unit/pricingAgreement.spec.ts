import { describe, expect, it } from 'vitest'
import { checkPricingAgreement } from '../../scripts/check-pricing-agreement.mjs'
import { PRO_PRICING } from '../../app/pricing/prices'

const snapshot = () => ({
  bindings: {
    STRIPE_PRICE_MONTHLY_ID: 'price_monthly',
    STRIPE_PRICE_YEARLY_ID: 'price_yearly',
    product_id: 'prod_approved',
  },
  product: { object: 'product', id: 'prod_approved', active: true, livemode: true },
  prices: {
    monthly: {
      object: 'price', id: 'price_monthly', product: 'prod_approved', active: true, livemode: true,
      currency: 'usd', type: 'recurring', billing_scheme: 'per_unit', custom_unit_amount: null, transform_quantity: null, unit_amount: PRO_PRICING.monthly * 100,
      recurring: { interval: 'month', interval_count: 1, usage_type: 'licensed' },
    },
    yearly: {
      object: 'price', id: 'price_yearly', product: 'prod_approved', active: true, livemode: true,
      currency: 'usd', type: 'recurring', billing_scheme: 'per_unit', custom_unit_amount: null, transform_quantity: null, unit_amount: PRO_PRICING.yearly * 100,
      recurring: { interval: 'year', interval_count: 1, usage_type: 'licensed' },
    },
  },
})

describe('the held offer agrees with supplied effective checkout prices', () => {
  it('accepts matching active live prices and product, deriving amounts from the public offer', () => {
    expect(checkPricingAgreement(snapshot())).toMatchObject({ ok: true, errors: [] })
  })

  it('rejects a higher amount despite correct IDs, product, currency and cadence', () => {
    const input = snapshot()
    input.prices.monthly.unit_amount += 100
    const result = checkPricingAgreement(input)
    expect(result.ok).toBe(false)
    expect(result.errors).toContain('monthly: Price amount disagrees with PRO_PRICING.')
  })

  it.each([
    ['empty snapshot', {}],
    ['missing yearly Price', { ...snapshot(), prices: { monthly: snapshot().prices.monthly } }],
    ['missing serving binding', { ...snapshot(), bindings: { ...snapshot().bindings, STRIPE_PRICE_MONTHLY_ID: '' } }],
    ['one price bound to both cycles', { ...snapshot(), bindings: { ...snapshot().bindings, STRIPE_PRICE_YEARLY_ID: 'price_monthly' } }],
    ['unbound catalog price', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, id: 'price_other' } } }],
    ['wrong product', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, product: 'prod_other' } } }],
    ['inactive staged price', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, active: false } } }],
    ['test-mode price', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, livemode: false } } }],
    ['inactive product', { ...snapshot(), product: { ...snapshot().product, active: false } }],
    ['test-mode product', { ...snapshot(), product: { ...snapshot().product, livemode: false } }],
    ['wrong product readback', { ...snapshot(), product: { ...snapshot().product, id: 'prod_other' } }],
    ['wrong currency', { ...snapshot(), prices: { ...snapshot().prices, yearly: { ...snapshot().prices.yearly, currency: 'eur' } } }],
    ['two-month cadence', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, recurring: { ...snapshot().prices.monthly.recurring, interval_count: 2 } } } }],
    ['monthly yearly price', { ...snapshot(), prices: { ...snapshot().prices, yearly: { ...snapshot().prices.yearly, recurring: { ...snapshot().prices.yearly.recurring, interval: 'month' } } } }],
    ['metered price', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, recurring: { ...snapshot().prices.monthly.recurring, usage_type: 'metered' } } } }],
    ['tiered price', { ...snapshot(), prices: { ...snapshot().prices, yearly: { ...snapshot().prices.yearly, billing_scheme: 'tiered' } } }],
    ['quantity transformation', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, transform_quantity: { divide_by: 10, round: 'up' } } } }],
    ['custom amount', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, custom_unit_amount: { enabled: true } } } }],
    ['fractional decimal amount', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, unit_amount_decimal: `${PRO_PRICING.monthly * 100}.1` } } }],
    ['string amount', { ...snapshot(), prices: { ...snapshot().prices, monthly: { ...snapshot().prices.monthly, unit_amount: String(PRO_PRICING.monthly * 100) } } }],
  ])('fails closed for %s', (_reason, input) => {
    const result = checkPricingAgreement(input)
    expect(result.ok).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
  })
})

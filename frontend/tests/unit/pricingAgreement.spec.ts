import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { checkPricingAgreement, checkServingCharge } from '../../scripts/check-pricing-agreement.mjs'
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

// The serving backend's public charge report (GET /api/subscriptions/prices): the daily production
// check needs agreement; the check on a pull request that changes the offer needs only that checkout
// charges no more than the new page shows (backend first, docs/PRICING_OFFER.md).
const serving = () => ({
  monthly: { amount_cents: PRO_PRICING.monthly * 100, currency: 'usd', interval: 'month', interval_count: 1 },
  yearly: { amount_cents: PRO_PRICING.yearly * 100, currency: 'usd', interval: 'year', interval_count: 1 },
})
const withMonthly = (overrides: Record<string, unknown>) => ({ ...serving(), monthly: { ...serving().monthly, ...overrides } })

describe('what the serving checkout charges agrees with the page', () => {
  it.each([false, true])('accepts charges equal to the offer (publishing: %s)', (publishing) => {
    expect(checkServingCharge(serving(), { publishing })).toMatchObject({ ok: true, usable: true, errors: [], notes: [] })
  })

  it.each([false, true])('rejects checkout charging more than the page shows (publishing: %s)', (publishing) => {
    const result = checkServingCharge(withMonthly({ amount_cents: PRO_PRICING.monthly * 100 + 1 }), { publishing })
    expect(result).toMatchObject({ ok: false, usable: true })
    expect(result.errors).toEqual([`monthly: checkout charges ${PRO_PRICING.monthly * 100 + 1} cents, more than the ${PRO_PRICING.monthly * 100} the page shows.`])
  })

  it('rejects a lower charge as disagreement, but before publishing only notes it', () => {
    const lower = { ...serving(), yearly: { ...serving().yearly, amount_cents: PRO_PRICING.yearly * 100 - 1 } }
    const message = `yearly: checkout charges ${PRO_PRICING.yearly * 100 - 1} cents, less than the ${PRO_PRICING.yearly * 100} the page shows.`
    expect(checkServingCharge(lower)).toMatchObject({ ok: false, usable: true, errors: [message], notes: [] })
    expect(checkServingCharge(lower, { publishing: true })).toMatchObject({ ok: true, usable: true, errors: [], notes: [message] })
  })

  it.each([
    ['an unset binding', withMonthly({ problem: 'unconfigured' })],
    ['an inactive Price', withMonthly({ problem: 'inactive' })],
    ['a test-mode Price', withMonthly({ problem: 'test_mode' })],
    ['a Price without a fixed charge', withMonthly({ problem: 'not_fixed_recurring' })],
    ['another currency', withMonthly({ currency: 'eur' })],
    ['a quarterly Price', withMonthly({ interval_count: 3 })],
    ['a yearly Price bound as monthly', withMonthly({ interval: 'year' })],
  ])('disagrees, in either mode, for %s', (_reason, report) => {
    for (const publishing of [false, true]) {
      expect(checkServingCharge(report, { publishing })).toMatchObject({ ok: false, usable: true })
    }
  })

  it.each([
    ['Stripe unavailable to the backend', withMonthly({ problem: 'unavailable' })],
    ['an unknown problem', withMonthly({ problem: 'renamed' })],
    ['a missing cycle', { monthly: serving().monthly }],
    ['a string amount', withMonthly({ amount_cents: String(PRO_PRICING.monthly * 100) })],
    ['a fractional amount', withMonthly({ amount_cents: PRO_PRICING.monthly * 100 + 0.5 })],
    ['an array', []],
    ['null', null],
  ])('is no evidence for %s', (_reason, report) => {
    for (const publishing of [false, true]) {
      expect(checkServingCharge(report, { publishing })).toMatchObject({ ok: false, usable: false })
    }
  })
})

// The runbook's command itself: Node's own type stripping (not Vitest) must load prices.ts, and the
// exit code must say agreement (0), disagreement (1) or unusable input (2).
describe('npm run check:pricing', () => {
  const frontend = join(__dirname, '../..')
  const higherYearly = () => {
    const input = snapshot()
    input.prices.yearly.unit_amount += 100
    return JSON.stringify(input)
  }
  const lowerMonthly = () => JSON.stringify(withMonthly({ amount_cents: PRO_PRICING.monthly * 100 - 1 }))
  const higherMonthly = () => JSON.stringify(withMonthly({ amount_cents: PRO_PRICING.monthly * 100 + 1 }))
  it.each([
    ['an agreeing snapshot', [], () => JSON.stringify(snapshot()), 0],
    ['a higher yearly amount', [], higherYearly, 1],
    ['unreadable JSON', [], () => '{', 2],
    ['an agreeing serving report', ['--serving'], () => JSON.stringify(serving()), 0],
    ['a lower serving charge', ['--serving'], lowerMonthly, 1],
    ['a lower serving charge before publishing', ['--serving', '--publishing'], lowerMonthly, 0],
    ['a higher serving charge before publishing', ['--serving', '--publishing'], higherMonthly, 1],
    ['a serving report without evidence', ['--serving'], () => JSON.stringify(withMonthly({ problem: 'unavailable' })), 2],
    ['unreadable serving JSON', ['--serving', '--publishing'], () => '{', 2],
  ] as const)('exits for %s with %i', (_case, flags, contents, status) => {
    const dir = mkdtempSync(join(tmpdir(), 'check-pricing-'))
    try {
      const file = join(dir, 'readback.json')
      writeFileSync(file, contents())
      const run = spawnSync('npm', ['run', '-s', 'check:pricing', '--', ...flags, file], { cwd: frontend, encoding: 'utf8' })
      expect(run.status).toBe(status)
      if (contents() !== '{') expect(JSON.parse(run.stdout)).toMatchObject({ ok: status === 0, expected: { monthly_cents: PRO_PRICING.monthly * 100, yearly_cents: PRO_PRICING.yearly * 100 } })
      expect(run.stderr).not.toMatch(/Warning/)
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it.each([
    ['no arguments', []],
    ['two files', ['a.json', 'b.json']],
    ['an unknown flag', ['--live', 'a.json']],
    ['publishing without serving', ['--publishing', 'a.json']],
    ['flags in the wrong order', ['--publishing', '--serving', 'a.json']],
    ['a flag for a file', ['--serving', '--publishing']],
  ])('refuses %s with the usage and exit 2', (_case, args) => {
    const run = spawnSync('npm', ['run', '-s', 'check:pricing', '--', ...args], { cwd: frontend, encoding: 'utf8' })
    expect(run.status).toBe(2)
    expect(run.stdout).toContain('--serving [--publishing]')
  })
})

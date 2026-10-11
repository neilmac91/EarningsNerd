import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { checkPricingAgreement, checkServingCharge, livePageOffer } from '../../scripts/check-pricing-agreement.mjs'
import { PRO_PRICING } from '../../app/pricing/prices'
import PricingLayout from '../../app/pricing/layout'

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
    ['a negative amount', withMonthly({ amount_cents: -1 })],
    ['an array', []],
    ['null', null],
  ])('is no evidence for %s', (_reason, report) => {
    for (const publishing of [false, true]) {
      expect(checkServingCharge(report, { publishing })).toMatchObject({ ok: false, usable: false })
    }
  })
})

// The daily check reads the offer from the live page, so a frontend rollback or a deploy that skipped
// main is compared too. The page is the server render of app/pricing/layout.tsx's JSON-LD.
const pageHtml = () => renderToStaticMarkup(createElement(PricingLayout, null, createElement('div')))
const ldScript = (data: unknown) => `<script type="application/ld+json">${JSON.stringify(data)}</script>`
const product = (offers: unknown[], id = 'https://www.earningsnerd.io/pricing#product') => ({ '@type': 'Product', '@id': id, offers })
const offer = (name: string, price: unknown, priceCurrency = 'USD') => ({ '@type': 'Offer', name, price, priceCurrency })

describe('the offer a live pricing page publishes', () => {
  it('reads the rendered pricing layout as the module offer, in cents', () => {
    expect(livePageOffer(pageHtml())).toEqual({ monthly: PRO_PRICING.monthly * 100, yearly: PRO_PRICING.yearly * 100 })
  })

  it('reads a cents-bearing price and skips other structured data', () => {
    const html = '<script type="application/ld+json">{not json</script>'
      + ldScript({ '@type': 'Organization', name: 'EarningsNerd' })
      + ldScript(product([offer('Pro (monthly)', 24.99), offer('Pro (annual)', 239)]))
    expect(livePageOffer(html)).toEqual({ monthly: 2499, yearly: 23900 })
  })

  it.each([
    ['a page without structured data', '<html></html>'],
    ['another product only', ldScript(product([offer('Pro (monthly)', 25), offer('Pro (annual)', 240)], 'https://example.com/other'))],
    ['two pricing products', ldScript(product([offer('Pro (monthly)', 25), offer('Pro (annual)', 240)])).repeat(2)],
    ['a missing annual offer', ldScript(product([offer('Pro (monthly)', 25)]))],
    ['a duplicated monthly offer', ldScript(product([offer('Pro (monthly)', 25), offer('Pro (monthly)', 20), offer('Pro (annual)', 240)]))],
    ['another currency', ldScript(product([offer('Pro (monthly)', 25, 'EUR'), offer('Pro (annual)', 240)]))],
    ['a string price', ldScript(product([offer('Pro (monthly)', '25'), offer('Pro (annual)', 240)]))],
    ['a negative price', ldScript(product([offer('Pro (monthly)', -25), offer('Pro (annual)', 240)]))],
    ['no page at all', undefined],
  ])('is no offer for %s', (_case, html) => {
    expect(livePageOffer(html)).toBeNull()
  })

  it('compares the report with the page instead of the module when given one', () => {
    const page = { monthly: PRO_PRICING.monthly * 100 - 500, yearly: PRO_PRICING.yearly * 100 }
    const result = checkServingCharge(serving(), { page })
    expect(result).toMatchObject({ ok: false, usable: true, expected: { source: 'live page', monthly_cents: page.monthly } })
    expect(result.errors).toEqual([`monthly: checkout charges ${PRO_PRICING.monthly * 100} cents, more than the ${page.monthly} the page shows.`])
    expect(checkServingCharge(serving(), { page: { monthly: PRO_PRICING.monthly * 100, yearly: PRO_PRICING.yearly * 100 } })).toMatchObject({ ok: true, expected: { source: 'live page' } })
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
    ['the live page agreeing', ['--serving', '--page', '@page'], () => JSON.stringify(serving()), 0],
    ['the live page showing less than checkout charges', ['--serving', '--page', '@page'], higherMonthly, 1],
  ] as const)('exits for %s with %i', (_case, flags, contents, status) => {
    const dir = mkdtempSync(join(tmpdir(), 'check-pricing-'))
    try {
      const file = join(dir, 'readback.json')
      const page = join(dir, 'pricing.html')
      writeFileSync(file, contents())
      writeFileSync(page, pageHtml())
      const args = flags.map((flag) => (flag === '@page' ? page : flag))
      const run = spawnSync('npm', ['run', '-s', 'check:pricing', '--', ...args, file], { cwd: frontend, encoding: 'utf8' })
      expect(run.status).toBe(status)
      if (contents() !== '{') expect(JSON.parse(run.stdout)).toMatchObject({ ok: status === 0, expected: { monthly_cents: PRO_PRICING.monthly * 100, yearly_cents: PRO_PRICING.yearly * 100 } })
      expect(run.stderr).not.toMatch(/Warning/)
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('exits 2 when the page carries no readable offer', () => {
    const dir = mkdtempSync(join(tmpdir(), 'check-pricing-'))
    try {
      const file = join(dir, 'serving.json')
      const page = join(dir, 'pricing.html')
      writeFileSync(file, JSON.stringify(serving()))
      writeFileSync(page, '<html></html>')
      const run = spawnSync('npm', ['run', '-s', 'check:pricing', '--', '--serving', '--page', page, file], { cwd: frontend, encoding: 'utf8' })
      expect(run.status).toBe(2)
      expect(run.stderr).toContain('no readable Pro offer')
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
    ['a page without its file', ['--serving', '--page', 'a.json']],
    ['a page before publishing', ['--serving', '--page', 'p.html', '--publishing', 'a.json']],
    ['a page for the operator readback', ['--page', 'p.html', 'a.json']],
  ])('refuses %s with the usage and exit 2', (_case, args) => {
    const run = spawnSync('npm', ['run', '-s', 'check:pricing', '--', ...args], { cwd: frontend, encoding: 'utf8' })
    expect(run.status).toBe(2)
    expect(run.stdout).toContain('--serving [--publishing] [--page')
  })
})

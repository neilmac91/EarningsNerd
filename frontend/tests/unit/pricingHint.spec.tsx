import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import PricingLayout from '@/app/pricing/layout'
import { PRICING_HINT_BOOTSTRAP, PRICING_PLAN_KEY, rememberPricingPlan } from '@/features/subscriptions/lib/pricingHint'
import { clearSessionActive, markSessionActive } from '@/lib/api/session'

/**
 * The pricing page's pre-paint mark (E228): a script before the plans marks the document with a returning reader's
 * plan, from the API client's session flag and the plan the page last named, so the held usage card and the billing
 * switch take their places from the first paint. The page's own cases are in PricingPage.spec.tsx, and the plans'
 * place on a cold load in tests/e2e/pricing-usage-hold.spec.ts.
 */

/** The script as the browser runs it, once, against this document and its storage. */
const runBootstrap = () => new Function(PRICING_HINT_BOOTSTRAP)()
const mark = () => document.documentElement.dataset.pricingHint

afterEach(() => {
  vi.restoreAllMocks()
  clearSessionActive()
  localStorage.clear()
  delete document.documentElement.dataset.pricingHint
})

describe('the pricing page’s pre-paint mark', () => {
  it('marks nothing without the session flag a sign-in sets, whatever plan was recorded', () => {
    localStorage.setItem(PRICING_PLAN_KEY, 'pro')
    runBootstrap()
    expect(mark()).toBeUndefined()
  })

  // The flag is the API client's own (markSessionActive), so the script reads the key that client writes.
  it.each([
    ['no recorded plan', null, 'free'],
    ['a recorded Free plan', 'free', 'free'],
    ['a recorded Pro plan', 'pro', 'pro'],
    ['an unknown value', 'enterprise', 'free'],
  ] as const)('marks a signed-in reader with %s as %s', (_, recorded, expected) => {
    markSessionActive()
    if (recorded) localStorage.setItem(PRICING_PLAN_KEY, recorded)
    runBootstrap()
    expect(mark()).toBe(expected)
  })

  it('marks nothing, and throws nothing, where storage cannot be read', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })
    expect(runBootstrap).not.toThrow()
    expect(mark()).toBeUndefined()
  })

  it('records the plan the identity read named, or a guest, and keeps the document’s mark with it', () => {
    rememberPricingPlan({ is_pro: true })
    expect(localStorage.getItem(PRICING_PLAN_KEY)).toBe('pro')
    expect(mark()).toBe('pro')
    rememberPricingPlan({ is_pro: false })
    expect(localStorage.getItem(PRICING_PLAN_KEY)).toBe('free')
    expect(mark()).toBe('free')
    rememberPricingPlan({})
    expect(localStorage.getItem(PRICING_PLAN_KEY)).toBe('free')
    rememberPricingPlan(null)
    expect(localStorage.getItem(PRICING_PLAN_KEY)).toBeNull()
    expect(mark()).toBeUndefined()
  })

  it('keeps the document’s mark where storage cannot be written', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })
    expect(() => rememberPricingPlan({ is_pro: true })).not.toThrow()
    expect(mark()).toBe('pro')
  })

  // The script must run before the plans are parsed, so it sits in the route's layout ahead of the page.
  it('runs in the pricing layout before the page', () => {
    const html = renderToStaticMarkup(<PricingLayout><main id="plans" /></PricingLayout>)
    const script = html.indexOf(PRICING_HINT_BOOTSTRAP)
    expect(script).toBeGreaterThan(-1)
    expect(script).toBeLessThan(html.indexOf('<main id="plans"'))
  })
})

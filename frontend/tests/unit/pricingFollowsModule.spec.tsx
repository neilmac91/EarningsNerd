import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PricingPage from '@/app/pricing/page'
import PricingLayout from '@/app/pricing/layout'
import PricingSection from '@/features/marketing/components/PricingSection'

/**
 * Every Pro amount and saving the pricing surfaces show comes from PRO_PRICING. Rendered under
 * other amounts ($30 a month, $270 a year), the pricing page (guest-free and beta), the homepage
 * section, the Product JSON-LD and checkout analytics on both cycles must all follow, and none may
 * keep a figure of the real offer or a typed "months free" claim
 * (lessons/frontend-price-copy-derives-from-the-module.md).
 */
const MOCK = vi.hoisted(() => ({ monthly: 30, yearly: 270 }))
vi.mock('@/app/pricing/prices', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/pricing/prices')>()
  return { ...actual, PRO_PRICING: actual.proPricing(MOCK.monthly, MOCK.yearly) }
})

const account = vi.hoisted(() => ({ isBeta: false }))
const mockCheckoutStarted = vi.fn()
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => Promise.resolve({ is_pro: false, plan: 'free', status: null, cancel_at_period_end: false }),
  getUsage: () => Promise.resolve({ summaries_used: 0, summaries_limit: 5, is_pro: false, month: '2026-10' }),
  createCheckoutSession: () => Promise.resolve({ url: '' }),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => Promise.resolve({ id: 1, email: 'u@example.com', is_beta: account.isBeta }),
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock('@/lib/analytics', () => ({
  default: {
    pricingViewed: vi.fn(),
    homepageSectionViewed: vi.fn(),
    billingCycleToggled: vi.fn(),
    checkoutStarted: (...args: unknown[]) => mockCheckoutStarted(...args),
  },
}))
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/SecondaryHeader', () => ({ default: () => null }))

// Built from the real module, so it tracks the shipped offer through any later price change.
let SHIPPED: RegExp
beforeAll(async () => {
  const { PRO_PRICING: real } = await vi.importActual<typeof import('@/app/pricing/prices')>('@/app/pricing/prices')
  // Rendering at the shipped amounts would prove nothing.
  expect([real.monthly, real.yearly]).not.toEqual([MOCK.monthly, MOCK.yearly])
  const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const figures = [real.monthlyDisplay, real.yearlyDisplay, real.yearlyPerMonthDisplay, real.annualSavingsDisplay]
  SHIPPED = new RegExp(
    `(${figures.map(escape).join('|')})(?![\\d.])|\\b${real.annualSavingsPercent}\\s*(%|percent)|\\bmonths?\\s+(for\\s+)?free\\b|\\bfree\\s+months?\\b`,
    'i',
  )
})
const expectNoShippedFigure = () => expect(document.body.textContent).not.toMatch(SHIPPED)

const renderPage = () =>
  within(
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <PricingPage />
      </QueryClientProvider>,
    ).container,
  )

describe('pricing surfaces follow PRO_PRICING', () => {
  afterEach(() => {
    account.isBeta = false
    mockCheckoutStarted.mockReset()
  })

  it('render every amount and saving from the module on both cycles', () => {
    const page = renderPage()
    const home = within(render(<PricingSection accessMode="public" showBeta={false} />).container)
    const layout = render(<PricingLayout><div /></PricingLayout>)
    const offers = JSON.parse(layout.container.querySelector('script[type="application/ld+json"]')!.textContent!).offers

    expect(offers.map((offer: { price: number }) => offer.price)).toEqual([30, 270])
    for (const surface of [page, home]) {
      expect(surface.getByText('$22.50')).toBeInTheDocument()
      expect(surface.getByText('Billed annually at $270, saving $90 a year.')).toBeInTheDocument()
    }
    expect(page.getByText('(save 25%)')).toBeInTheDocument()
    expect(home.getByText('· save 25%')).toBeInTheDocument()
    expectNoShippedFigure()

    fireEvent.click(page.getByRole('switch', { name: /billing cycle/i }))
    fireEvent.click(home.getByRole('radio', { name: /monthly/i }))
    expect(page.getByText('$30')).toBeInTheDocument()
    expect(home.getByText('$30')).toBeInTheDocument()
    expect(home.getByText('Billed monthly. Or $22.50 a month, billed annually at $270.')).toBeInTheDocument()
    expectNoShippedFigure()
  })

  it.each([
    ['yearly', 270],
    ['monthly', 30],
  ] as const)('checkout analytics carry the module charge on %s', async (cycle, price) => {
    const page = renderPage()
    if (cycle === 'monthly') fireEvent.click(page.getByRole('switch', { name: /billing cycle/i }))
    await page.findByRole('button', { name: /current plan/i })
    fireEvent.click(page.getByRole('button', { name: /upgrade to pro/i }))
    await waitFor(() => expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', price, cycle))
  })

  it('strikes through the module price for a beta member', async () => {
    account.isBeta = true
    const page = renderPage()
    expect(await page.findByText('$22.50/mo')).toBeInTheDocument()
    fireEvent.click(page.getByRole('switch', { name: /billing cycle/i }))
    expect(screen.getByText('$30/mo')).toBeInTheDocument()
    expectNoShippedFigure()
  })
})

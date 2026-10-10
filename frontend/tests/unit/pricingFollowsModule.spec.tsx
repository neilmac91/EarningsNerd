import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PricingPage from '@/app/pricing/page'
import PricingLayout from '@/app/pricing/layout'
import PricingSection from '@/features/marketing/components/PricingSection'

/**
 * Every Pro amount and saving the pricing surfaces show comes from PRO_PRICING. Rendered under
 * other amounts ($30 a month, $270 a year), the pricing page, the homepage section, the Product
 * JSON-LD and checkout analytics must all follow, and none may keep a shipped figure or a typed
 * saving claim such as "2 months free" (lessons/frontend-price-copy-derives-from-the-module.md).
 */
vi.mock('@/app/pricing/prices', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/pricing/prices')>()
  return { ...actual, PRO_PRICING: actual.proPricing(30, 270) }
})

const mockCheckoutStarted = vi.fn()
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => Promise.resolve({ is_pro: false, plan: 'free', status: null, cancel_at_period_end: false }),
  getUsage: () => Promise.resolve({ summaries_used: 0, summaries_limit: 5, is_pro: false, month: '2026-10' }),
  createCheckoutSession: () => Promise.resolve({ url: '' }),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => Promise.resolve({ id: 1, email: 'u@example.com' }),
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

// A shipped figure ($25, $20, $240, $60, 20%) or a "months free" claim that no amount computes.
const HARD_CODED = /\$(20|25|240|60)\b|\b20%|months? free/i

describe('pricing surfaces follow PRO_PRICING', () => {
  it('render every amount and saving from the module, on both cycles, with no typed figure left', async () => {
    const page = within(
      render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <PricingPage />
        </QueryClientProvider>,
      ).container,
    )
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
    expect(document.body.textContent).not.toMatch(HARD_CODED)

    await page.findByRole('button', { name: /current plan/i })
    fireEvent.click(page.getByRole('button', { name: /upgrade to pro/i }))
    await waitFor(() => expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 270, 'yearly'))

    fireEvent.click(page.getByRole('switch', { name: /billing cycle/i }))
    fireEvent.click(home.getByRole('radio', { name: /monthly/i }))
    expect(page.getByText('$30')).toBeInTheDocument()
    expect(home.getByText('$30')).toBeInTheDocument()
    expect(home.getByText('Billed monthly. Or $22.50 a month, billed annually at $270.')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(HARD_CODED)
  })
})

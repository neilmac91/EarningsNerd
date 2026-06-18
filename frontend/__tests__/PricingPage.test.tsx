import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PricingPage from '@/app/pricing/page'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'

const mockGetSubscriptionStatus = vi.fn<[], Promise<SubscriptionStatus>>()
const mockGetUsage = vi.fn<[], Promise<Usage>>()
const mockGetCurrentUserSafe = vi.fn()

vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => mockGetSubscriptionStatus(),
  getUsage: () => mockGetUsage(),
  createCheckoutSession: vi.fn(),
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => mockGetCurrentUserSafe(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}))

vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => undefined }))
vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@/lib/analytics', () => ({
  default: { pricingViewed: vi.fn(), billingCycleToggled: vi.fn(), checkoutStarted: vi.fn() },
}))

// Trim chrome/icon deps so the test stays focused on pricing logic.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/SecondaryHeader', () => ({ default: () => null }))
vi.mock('@/components/StateCard', () => ({ default: () => null }))

function renderPricing() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <PricingPage />
    </QueryClientProvider>
  )
}

const baseSub: SubscriptionStatus = {
  is_pro: false,
  stripe_customer_id: null,
  stripe_subscription_id: null,
  subscription_status: null,
  plan: 'free',
  status: null,
  trial_end: null,
  current_period_end: null,
  cancel_at_period_end: false,
}

const baseUsage: Usage = { summaries_used: 0, summaries_limit: null, is_pro: true, month: '2026-06' }

describe('PricingPage', () => {
  beforeEach(() => {
    mockGetSubscriptionStatus.mockReset()
    mockGetUsage.mockReset()
    mockGetCurrentUserSafe.mockReset()
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'u@example.com' })
    mockGetUsage.mockResolvedValue(baseUsage)
  })

  it('lets a reverse-trial user convert: enabled "Subscribe to Pro" button + visible billing toggle', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'trialing',
      plan: 'pro',
      trial_end: '2026-06-25T00:00:00Z',
    })

    renderPricing()

    const cta = await screen.findByRole('button', { name: /subscribe to pro/i })
    expect(cta).toBeEnabled()
    // Billing cycle toggle must be available so the user can pick monthly vs yearly.
    expect(screen.getByRole('switch', { name: /billing cycle/i })).toBeInTheDocument()
  })

  it('treats a paid (active, non-trial) subscriber as Current Plan with no toggle', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'active',
      plan: 'pro',
      stripe_customer_id: 'cus_123',
    })

    renderPricing()

    // Toggle removal is the subscription-driven change; wait for it so we don't assert mid-load
    // (the Free card renders its own disabled "Current Plan" before the subscription resolves).
    await waitFor(() =>
      expect(screen.queryByRole('switch', { name: /billing cycle/i })).not.toBeInTheDocument()
    )
    // A paid subscriber has nothing to buy — no enabled upgrade/subscribe CTA anywhere.
    expect(screen.queryByRole('button', { name: /subscribe to pro|upgrade to pro/i })).not.toBeInTheDocument()
    // "Current Plan" appears exactly once (the Pro card) — never on the Free card too.
    const currentPlanButtons = screen.getAllByRole('button', { name: /current plan/i })
    expect(currentPlanButtons).toHaveLength(1)
    expect(currentPlanButtons[0]).toBeDisabled()
    // The Free card is not the user's plan, so it stays the disabled "Get Started Free".
    const freeButton = screen.getByRole('button', { name: /get started free/i })
    expect(freeButton).toBeDisabled()
  })

  it('never leaves the Free card stuck on "Processing…"', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })

    renderPricing()

    // Free card shows the authenticated "Current Plan" label, not a perpetual spinner.
    await screen.findByText(/current plan/i)
    expect(screen.queryByText(/processing/i)).not.toBeInTheDocument()
  })
})

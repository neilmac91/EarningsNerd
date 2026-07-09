import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PricingPage from '@/app/pricing/page'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'

const mockGetSubscriptionStatus = vi.fn<[], Promise<SubscriptionStatus>>()
const mockGetUsage = vi.fn<[], Promise<Usage>>()
const mockGetCurrentUserSafe = vi.fn()
const mockCreateCheckoutSession = vi.fn()
// Controls the pricing A/B arm per test (roadmap 2.3). Default (undefined) = the $39 control.
const mockUseFeatureFlagVariantKey = vi.fn<[], string | boolean | undefined>()
const mockCheckoutStarted = vi.fn()

vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => mockGetSubscriptionStatus(),
  getUsage: () => mockGetUsage(),
  createCheckoutSession: (priceId: string) => mockCreateCheckoutSession(priceId),
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => mockGetCurrentUserSafe(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}))

vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => mockUseFeatureFlagVariantKey() }))
vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@/lib/analytics', () => ({
  default: {
    pricingViewed: vi.fn(),
    billingCycleToggled: vi.fn(),
    checkoutStarted: (...args: unknown[]) => mockCheckoutStarted(...args),
  },
}))

// Trim chrome/icon deps so the test stays focused on pricing logic.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/SecondaryHeader', () => ({ default: () => null }))

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
    mockCreateCheckoutSession.mockReset()
    mockUseFeatureFlagVariantKey.mockReset()
    mockCheckoutStarted.mockReset()
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'u@example.com' })
    mockGetUsage.mockResolvedValue(baseUsage)
    mockCreateCheckoutSession.mockResolvedValue({ url: '' }) // falsy url → no navigation in onSuccess
    mockUseFeatureFlagVariantKey.mockReturnValue(undefined) // default arm = $39 control
  })

  it('treats a trialing user as current-plan: disabled "Current Plan (trial)" + no billing toggle', async () => {
    // INVERTED from the original reverse-trial pin (staff review, PR #619): a card-required
    // Stripe trial IS a live subscription that auto-charges at trial end, so an enabled buy CTA
    // here invited a SECOND checkout — double-billing plus a webhook hazard when the orphaned
    // sub cancels. The server now 409s that path; this pins the client half.
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'trialing',
      plan: 'pro',
      trial_end: '2026-06-25T00:00:00Z',
    })

    renderPricing()

    const cta = await screen.findByRole('button', { name: /current plan \(trial\)/i })
    expect(cta).toBeDisabled()
    // Plan changes for a live trial go through the billing portal, not a second checkout —
    // the cycle toggle would only move a button the user can't press.
    await waitFor(() =>
      expect(screen.queryByRole('switch', { name: /billing cycle/i })).not.toBeInTheDocument()
    )
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

  // --- Fake-door $39-vs-$29 price test (roadmap 2.3) ---

  it('control arm (flag unset) shows the $32.50/mo anchor', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    // Default billing cycle is yearly; the card now shows the effective MONTHLY cost.
    // Control $390/yr → $32.50/mo. The $29 arm's $24.17/mo must not appear.
    expect(await screen.findByText('$32.50')).toBeInTheDocument()
    expect(screen.queryByText('$24.17')).not.toBeInTheDocument()
  })

  it('price_29 arm lowers the displayed anchor to $24.17/mo', async () => {
    mockUseFeatureFlagVariantKey.mockReturnValue('price_29')
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    // $290/yr → $24.17/mo.
    expect(await screen.findByText('$24.17')).toBeInTheDocument()
    expect(screen.queryByText('$32.50')).not.toBeInTheDocument()
  })

  it('checkout_started carries the arm price + variant when Upgrade is clicked', async () => {
    mockUseFeatureFlagVariantKey.mockReturnValue('price_29')
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    // Wait until auth resolves (the Free card flips to "Current Plan") — otherwise the click is
    // treated as a guest and redirects to /register instead of starting checkout.
    await screen.findByRole('button', { name: /current plan/i })
    fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))

    // ('pro', yearly price for the $29 arm = 290, billing cycle, variant key)
    await waitFor(() =>
      expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 290, 'yearly', 'price_29'),
    )
    expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly')
  })
})

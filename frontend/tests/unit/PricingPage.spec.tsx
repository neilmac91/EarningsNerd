import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PricingPage from '@/app/pricing/page'
import PricingLayout from '@/app/pricing/layout'
import PricingSection from '@/features/marketing/components/PricingSection'
import { queryKeys } from '@/lib/queryKeys'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'
import { consumePostAuthRedirect } from '@/lib/postAuthRedirect'

const mockGetSubscriptionStatus = vi.fn<[], Promise<SubscriptionStatus>>()
const mockGetUsage = vi.fn<[], Promise<Usage>>()
const mockGetCurrentUserSafe = vi.fn()
const mockCreateCheckoutSession = vi.fn()
// A stale pricing flag must never change the approved offer.
const mockUseFeatureFlagVariantKey = vi.fn<[], string | boolean | undefined>()
const mockCheckoutStarted = vi.fn()
const mockPricingViewed = vi.fn()
const mockPush = vi.fn()
const mockSearchParams = new URLSearchParams()
const flags = vi.hoisted(() => ({ ENABLE_PRO_TRIAL: false }))
vi.mock('@/lib/featureFlags', () => flags)
// Test-only capture of the real onClick each card Button was rendered with, keyed by
// `${variant}:${label}` (Free = secondary, Pro = primary; both cards share a label while the
// account is unresolved), so each card's actual handler can be exercised independently of
// the DOM's disabled state.
const capturedOnClick = new Map<string, (() => void) | undefined>()
const invokeCard = (card: 'free' | 'pro', label: string) =>
  capturedOnClick.get(`${card === 'pro' ? 'primary' : 'secondary'}:${label}`)?.()

vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => mockGetSubscriptionStatus(),
  getUsage: () => mockGetUsage(),
  createCheckoutSession: (priceId: string) => mockCreateCheckoutSession(priceId),
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => mockGetCurrentUserSafe(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: vi.fn() }),
  useSearchParams: () => mockSearchParams,
}))

vi.mock('@/components/ui/Button', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/ui/Button')>()
  const Button = (props: React.ComponentProps<typeof actual.Button>) => {
    if (props.size === 'lg' && typeof props.children === 'string') capturedOnClick.set(`${props.variant ?? 'primary'}:${props.children}`, props.onClick as (() => void) | undefined)
    return <actual.Button {...props} />
  }
  return { ...actual, Button }
})

vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => mockUseFeatureFlagVariantKey() }))
vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@/lib/analytics', () => ({
  default: {
    pricingViewed: (...args: unknown[]) => mockPricingViewed(...args),
    homepageSectionViewed: vi.fn(),
    billingCycleToggled: vi.fn(),
    checkoutStarted: (...args: unknown[]) => mockCheckoutStarted(...args),
  },
}))

// Trim chrome/icon deps so the test stays focused on pricing logic.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/SecondaryHeader', () => ({ default: () => null }))

function renderPricing(initialSubscription?: SubscriptionStatus) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  if (initialSubscription) queryClient.setQueryData(queryKeys.subscription.byUser(1), initialSubscription)
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
    mockPricingViewed.mockReset()
    mockPush.mockReset()
    Array.from(mockSearchParams.keys()).forEach((key) => mockSearchParams.delete(key))
    flags.ENABLE_PRO_TRIAL = false
    localStorage.clear()
    capturedOnClick.clear()
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'u@example.com' })
    mockGetUsage.mockResolvedValue(baseUsage)
    mockCreateCheckoutSession.mockResolvedValue({ url: '' }) // falsy url → no navigation in onSuccess
    mockUseFeatureFlagVariantKey.mockReturnValue(undefined)
  })

  it('treats a trialing user as current-plan: disabled "Current plan (trial)" + no billing toggle', async () => {
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

  it('lets a server-resolved Free user with an expired trial row upgrade', async () => {
    const expiredTrial = { ...baseSub, status: 'trialing', trial_end: '2026-01-01T00:00:00Z' }
    mockGetSubscriptionStatus.mockResolvedValue(expiredTrial)
    mockGetUsage.mockResolvedValue({ ...baseUsage, is_pro: false, summaries_limit: 5 })

    // Seed the resolved response so the transient Free loading label cannot hide a regression.
    renderPricing(expiredTrial)
    await screen.findByRole('button', { name: /^current plan$/i })
    const upgrade = screen.getByRole('button', { name: /upgrade to pro/i })
    expect(upgrade).toBeEnabled()
    expect(screen.queryByRole('button', { name: /current plan \(trial\)/i })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /current plan/i })).toHaveLength(1)
    expect(screen.getByRole('switch', { name: /billing cycle/i })).toBeInTheDocument()
    fireEvent.click(upgrade)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 190, 'yearly')
  })

  it('treats a paid (active, non-trial) subscriber as Current plan with no toggle', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'active',
      plan: 'pro',
      stripe_customer_id: 'cus_123',
    })

    renderPricing()

    // Toggle removal is the subscription-driven change; wait for it so we don't assert mid-load
    // (the Free card renders its own disabled "Current plan" before the subscription resolves).
    await waitFor(() =>
      expect(screen.queryByRole('switch', { name: /billing cycle/i })).not.toBeInTheDocument()
    )
    // A paid subscriber has nothing to buy — no enabled upgrade/subscribe CTA anywhere.
    expect(screen.queryByRole('button', { name: /subscribe to pro|upgrade to pro/i })).not.toBeInTheDocument()
    // "Current plan" appears exactly once (the Pro card) — never on the Free card too.
    const currentPlanButtons = screen.getAllByRole('button', { name: /current plan/i })
    expect(currentPlanButtons).toHaveLength(1)
    expect(currentPlanButtons[0]).toBeDisabled()
    // The Free card is not the user's plan, so it stays the disabled "Create free account".
    const freeButton = screen.getByRole('button', { name: /create free account/i })
    expect(freeButton).toBeDisabled()
  })

  it('never leaves the Free card stuck on "Processing…"', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })

    renderPricing()

    // Free card shows the authenticated "Current plan" label, not a perpetual spinner.
    await screen.findByText(/current plan/i)
    expect(screen.queryByText(/processing/i)).not.toBeInTheDocument()
  })

  it('keeps the approved offer aligned across pricing, homepage and JSON-LD despite a stale price flag', async () => {
    mockUseFeatureFlagVariantKey.mockReturnValue('price_29')
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    const pricing = renderPricing()
    const page = within(pricing.container)
    const landing = render(<PricingSection accessMode="public" showBeta={false} />)
    const home = within(landing.container)
    const layout = render(<PricingLayout><div /></PricingLayout>)
    const structuredData = JSON.parse(layout.container.querySelector('script[type="application/ld+json"]')!.textContent!)

    // Annual is charged once at $190; $15.83 is the rounded monthly equivalent, not a charge.
    expect(page.getByText('$15.83')).toBeInTheDocument()
    expect(page.getByText('Billed annually at $190. Two months free, saving $38 a year (17%).')).toBeInTheDocument()
    expect(page.getByText('(2 months free)')).toBeInTheDocument()
    expect(home.getByText('$19')).toBeInTheDocument()
    expect(home.getByText('Billed monthly. Or $190 a year, with two months free.')).toBeInTheDocument()
    expect(structuredData.offers).toEqual([
      expect.objectContaining({ name: 'Pro (monthly)', price: 19, priceCurrency: 'USD' }),
      expect.objectContaining({ name: 'Pro (annual)', price: 190, priceCurrency: 'USD' }),
    ])

    fireEvent.click(home.getByRole('radio', { name: /annual/i }))
    expect(home.getByText('$15.83')).toBeInTheDocument()
    expect(home.getByText('Billed annually at $190. Two months free, saving $38 a year (17%).')).toBeInTheDocument()
    fireEvent.click(page.getByRole('switch', { name: /billing cycle/i }))
    expect(page.getByText('$19')).toBeInTheDocument()
    expect(page.getByText('Billed monthly')).toBeInTheDocument()
    expect(mockUseFeatureFlagVariantKey).not.toHaveBeenCalled()

    // Wait until auth resolves (the Free card flips to "Current plan") before checkout.
    await page.findByRole('button', { name: /current plan/i })
    fireEvent.click(page.getByRole('button', { name: /upgrade to pro/i }))
    await waitFor(() => expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 19, 'monthly'))
    expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_monthly')
  })

  // --- Honest account states (billing-state-honesty): absent account data is not a decision ---

  const noCheckoutSideEffects = () => {
    expect(mockCheckoutStarted).not.toHaveBeenCalled()
    expect(mockCreateCheckoutSession).not.toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  }

  it('unresolved identity claims no plan, arms no checkout and is not routed as a guest', async () => {
    mockGetCurrentUserSafe.mockReturnValue(new Promise(() => {}))
    renderPricing()

    const checking = await screen.findAllByRole('button', { name: /checking your plan/i })
    expect(checking).toHaveLength(2)
    checking.forEach((button) => expect(button).toBeDisabled())
    expect(screen.queryByRole('button', { name: /current plan/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /upgrade to pro|start 7-day|claim pro/i })).not.toBeInTheDocument()
    expect(mockGetSubscriptionStatus).not.toHaveBeenCalled()

    // The real handlers of BOTH cards, invoked past the disabled DOM: nothing is recorded,
    // sent or redirected (an unresolved identity is not a guest for the Free card either).
    invokeCard('free', 'Checking your plan…')
    invokeCard('pro', 'Checking your plan…')
    await Promise.resolve()
    noCheckoutSideEffects()
  })

  it('a failed identity check shows an account error with retry, never a guest or Free view', async () => {
    mockGetCurrentUserSafe.mockRejectedValueOnce(new Error('network down'))
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    expect(await screen.findByText(/couldn't check your account/i)).toBeInTheDocument()
    expect(screen.getByText('network down')).toBeInTheDocument()
    const unavailable = screen.getAllByRole('button', { name: /plan unavailable/i })
    expect(unavailable).toHaveLength(2)
    unavailable.forEach((button) => expect(button).toBeDisabled())
    expect(screen.queryByRole('button', { name: /current plan|create free account/i })).not.toBeInTheDocument()
    invokeCard('free', 'Plan unavailable')
    invokeCard('pro', 'Plan unavailable')
    await Promise.resolve()
    noCheckoutSideEffects()

    // Retry resolves the identity and the ordinary Free view follows.
    fireEvent.click(screen.getByRole('button', { name: /retry account check/i }))
    await screen.findByRole('button', { name: /^current plan$/i })
    expect(screen.queryByText(/couldn't check your account/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upgrade to pro/i })).toBeEnabled()
  })

  it('a known user with no subscription snapshot gets no current plan or checkout until it resolves', async () => {
    let resolveSubscription!: (value: SubscriptionStatus) => void
    mockGetSubscriptionStatus.mockReturnValue(new Promise<SubscriptionStatus>((resolve) => { resolveSubscription = resolve }))
    renderPricing()

    await waitFor(() => expect(mockGetSubscriptionStatus).toHaveBeenCalledTimes(1))
    expect(screen.getAllByRole('button', { name: /checking your plan/i })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /current plan/i })).not.toBeInTheDocument()
    invokeCard('free', 'Checking your plan…')
    invokeCard('pro', 'Checking your plan…')
    await Promise.resolve()
    noCheckoutSideEffects()

    resolveSubscription({ ...baseSub })
    await screen.findByRole('button', { name: /^current plan$/i })
    // Positive control through the same captured handler: resolved Free may check out.
    invokeCard('pro', 'Upgrade to Pro')
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 190, 'yearly')
  })

  it('a failed initial subscription read offers retry and keeps checkout unavailable; usage failure alone blocks nothing', async () => {
    mockGetSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    mockGetUsage.mockRejectedValue(new Error('usage unavailable'))
    renderPricing()

    expect(await screen.findByText(/couldn't load all pricing details/i)).toBeInTheDocument()
    const unavailable = screen.getAllByRole('button', { name: /plan unavailable/i })
    expect(unavailable).toHaveLength(2)
    expect(screen.queryByRole('button', { name: /current plan/i })).not.toBeInTheDocument()
    invokeCard('free', 'Plan unavailable')
    invokeCard('pro', 'Plan unavailable')
    await Promise.resolve()
    noCheckoutSideEffects()

    fireEvent.click(screen.getByRole('button', { name: /retry subscription/i }))
    await screen.findByRole('button', { name: /^current plan$/i })
    // Usage is still failing; the plan decision does not depend on it.
    expect(screen.getByText(/couldn't load all pricing details/i)).toBeInTheDocument()
    const upgrade = screen.getByRole('button', { name: /upgrade to pro/i })
    expect(upgrade).toBeEnabled()
    fireEvent.click(upgrade)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
  })

  it.each([false, true])('retains same-account subscription data (is_pro=%s) across a failed refresh with a refresh notice', async (isPro) => {
    const cached = { ...baseSub, is_pro: isPro, status: isPro ? 'active' : null, plan: isPro ? 'pro' : 'free', stripe_customer_id: isPro ? 'cus_1' : null }
    mockGetSubscriptionStatus.mockRejectedValueOnce(new Error('refresh failed'))
    mockGetSubscriptionStatus.mockResolvedValue({ ...cached })
    renderPricing(cached)

    expect(await screen.findByText(/couldn't refresh your plan details/i)).toBeInTheDocument()
    expect(screen.getByText(/showing your last loaded plan/i)).toBeInTheDocument()
    const current = screen.getAllByRole('button', { name: /current plan/i })
    expect(current).toHaveLength(1)
    if (isPro) {
      expect(screen.queryByRole('button', { name: /upgrade to pro/i })).not.toBeInTheDocument()
      invokeCard('pro', 'Current plan')
      await Promise.resolve()
      noCheckoutSideEffects()
    } else {
      // Cached Free keeps its existing checkout action; the server re-checks entitlement.
      fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))
      await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    }

    fireEvent.click(screen.getByRole('button', { name: /retry subscription/i }))
    await waitFor(() => expect(screen.queryByText(/couldn't refresh your plan details/i)).not.toBeInTheDocument())
    expect(screen.getAllByRole('button', { name: /current plan/i })).toHaveLength(1)
  })

  it('a confirmed guest keeps registration routing on both cards', async () => {
    mockGetCurrentUserSafe.mockResolvedValue(null)
    renderPricing()

    const free = await screen.findByRole('button', { name: /create free account/i })
    expect(free).toBeEnabled()
    fireEvent.click(free)
    expect(mockPush).toHaveBeenCalledWith('/register')
    fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))
    expect(mockPush).toHaveBeenCalledWith('/register?redirect=%2Fpricing%3Fbilling%3Dyearly')
    expect(mockGetSubscriptionStatus).not.toHaveBeenCalled()
    expect(mockCheckoutStarted).not.toHaveBeenCalled()
  })

  it.each([
    ['monthly', 'monthly', 19],
    ['yearly', 'yearly', 190],
    ['annual', 'yearly', 190],
    ['https://example.com', 'yearly', 190],
    [null, 'yearly', 190],
  ] as const)('incoming billing=%s records the resolved cycle and checks out %s', async (requested, cycle, price) => {
    if (requested !== null) mockSearchParams.set('billing', requested)
    flags.ENABLE_PRO_TRIAL = true
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    const label = cycle === 'monthly' ? 'Start 7-day free trial' : 'Upgrade to Pro'
    const checkout = await screen.findByRole('button', { name: label })
    expect(screen.getByRole('switch', { name: /billing cycle/i })).toHaveAttribute('aria-checked', String(cycle === 'yearly'))
    expect(mockPricingViewed.mock.calls).toEqual([[cycle]])
    if (cycle === 'yearly') expect(screen.queryByRole('button', { name: /start 7-day/i })).not.toBeInTheDocument()
    fireEvent.click(checkout)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith(`price_pro_${cycle}`))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', price, cycle)
  })

  it('keeps a later manual cycle choice instead of reapplying the incoming trial link', async () => {
    mockSearchParams.set('billing', 'monthly')
    flags.ENABLE_PRO_TRIAL = true
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    await screen.findByRole('button', { name: 'Start 7-day free trial' })
    fireEvent.click(screen.getByRole('switch', { name: /billing cycle/i }))
    const checkout = await screen.findByRole('button', { name: 'Upgrade to Pro' })
    expect(screen.getByText('$15.83')).toBeInTheDocument()
    fireEvent.click(checkout)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 190, 'yearly')
    expect(mockPricingViewed.mock.calls).toEqual([['monthly']])
  })

  it.each(['monthly', 'yearly'] as const)('preserves the guest %s choice in the registration query and email-login stash', async (cycle) => {
    mockSearchParams.set('billing', cycle)
    flags.ENABLE_PRO_TRIAL = true
    mockGetCurrentUserSafe.mockResolvedValue(null)
    renderPricing()

    fireEvent.click(await screen.findByRole('button', { name: cycle === 'monthly' ? 'Start 7-day free trial' : 'Upgrade to Pro' }))
    const registration = new URL(mockPush.mock.calls[0][0], 'https://www.earningsnerd.io')
    expect(registration.pathname).toBe('/register')
    expect(registration.searchParams.get('redirect')).toBe(`/pricing?billing=${cycle}`)
    expect(consumePostAuthRedirect()).toBe(`/pricing?billing=${cycle}`)
    expect(consumePostAuthRedirect()).toBeNull()
    expect(mockCreateCheckoutSession).not.toHaveBeenCalled()
    expect(mockCheckoutStarted).not.toHaveBeenCalled()
  })

  it('a monthly trial link keeps beta checkout separate from trial eligibility', async () => {
    mockSearchParams.set('billing', 'monthly')
    flags.ENABLE_PRO_TRIAL = true
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'beta@example.com', is_beta: true })
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    fireEvent.click(await screen.findByRole('button', { name: 'Claim Pro' }))
    expect(screen.queryByRole('button', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_monthly'))
  })

  it.each([true, false])('the actual homepage link preserves its offer at guest pricing (beta=%s)', async (showBeta) => {
    flags.ENABLE_PRO_TRIAL = true
    mockGetCurrentUserSafe.mockResolvedValue(null)
    const landing = render(<PricingSection accessMode={showBeta ? 'invite' : 'public'} showBeta={showBeta} />)
    const label = showBeta ? 'Upgrade to Pro' : 'Start 7-day free trial'
    const href = screen.getByRole('link', { name: label }).getAttribute('href')!
    landing.unmount()

    // Follow the rendered link instead of inventing a destination independent of the homepage.
    const destination = new URL(href, 'https://www.earningsnerd.io')
    expect(destination.pathname).toBe('/pricing')
    destination.searchParams.forEach((value, key) => mockSearchParams.set(key, value))
    renderPricing()
    expect(await screen.findByRole('button', { name: label })).toBeEnabled()
    expect(screen.getByRole('switch', { name: /billing cycle/i })).toHaveAttribute('aria-checked', String(showBeta))
    const trialNote = 'First 7 days free · cancel anytime, no charge'
    if (showBeta) {
      expect(screen.queryByRole('button', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
      expect(screen.queryByText(trialNote)).not.toBeInTheDocument()
    } else {
      expect(screen.getByText(trialNote)).toBeInTheDocument()
    }
    expect(mockPricingViewed.mock.calls).toEqual([[showBeta ? 'yearly' : 'monthly']])
  })
})

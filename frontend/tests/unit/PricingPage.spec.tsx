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
const mockGetRegistrationConfig = vi.fn()
const mockCreateCheckoutSession = vi.fn()
// A stale pricing flag must never change the approved offer.
const mockUseFeatureFlagVariantKey = vi.fn<[], string | boolean | undefined>()
const mockCheckoutStarted = vi.fn()
const mockPricingViewed = vi.fn()
const mockPush = vi.fn()
const mockSearchParams = new URLSearchParams()
// router.replace moves the address as the real router does, so the next render reads what is left.
const mockReplace = vi.fn((href: string) => {
  Array.from(mockSearchParams.keys()).forEach((key) => mockSearchParams.delete(key))
  new URLSearchParams(href.split('?')[1] ?? '').forEach((value, key) => mockSearchParams.set(key, value))
})
// The flags ship off: the plan lists leave out the lines they decide (lib/planLimits.ts shipped).
const flags = vi.hoisted(() => ({ ENABLE_PRO_TRIAL: false, ENABLE_ANALYSIS: false, ENABLE_FPI_FILINGS: false }))
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

vi.mock('@/features/marketing/api/access-api', () => ({
  getRegistrationConfig: () => mockGetRegistrationConfig(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: vi.fn(), replace: mockReplace }),
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

// The billing switch is named by the cycle it turns on, its visible "Yearly" label (the literal
// offer is pinned in this file).
const BILLING_SWITCH = { name: 'Yearly (save 20%)' }

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
    mockReplace.mockClear()
    mockGetRegistrationConfig.mockReset()
    mockGetRegistrationConfig.mockResolvedValue({ mode: 'public', beta_promo_enabled: false })
    Array.from(mockSearchParams.keys()).forEach((key) => mockSearchParams.delete(key))
    flags.ENABLE_PRO_TRIAL = false
    flags.ENABLE_ANALYSIS = false
    flags.ENABLE_FPI_FILINGS = false
    localStorage.clear()
    capturedOnClick.clear()
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'u@example.com' })
    mockGetUsage.mockResolvedValue(baseUsage)
    mockCreateCheckoutSession.mockResolvedValue({ url: '' }) // falsy url → no navigation in onSuccess
    mockUseFeatureFlagVariantKey.mockReturnValue(undefined)
  })

  // Stripe's cancel_url carries only ?canceled=true: no session id and no charge outcome. The notice says
  // the visitor came back from checkout and what the subscription query says, nothing about payment.
  describe('returning from a cancelled checkout (?canceled=true)', () => {
    const RETURNED = 'You returned from checkout'

    it('a Free account is invited to choose a plan, and the flag is dropped from the address', async () => {
      mockSearchParams.set('canceled', 'true')
      mockSearchParams.set('billing', 'monthly')
      mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
      const { unmount } = renderPricing()

      expect(await screen.findByText('You can choose a plan below.')).toBeInTheDocument()
      expect(screen.getByText(RETURNED)).toBeInTheDocument()
      expect(screen.queryByText(/charged/i)).not.toBeInTheDocument()
      expect(screen.queryByText('Your plan is Pro.')).not.toBeInTheDocument()
      // Other params are kept; only the return flag goes.
      expect(mockReplace).toHaveBeenCalledWith('/pricing?billing=monthly', { scroll: false })
      expect(mockSearchParams.toString()).toBe('billing=monthly')

      // A second visit to the address left behind (a reload, a history entry) says nothing. A later visit
      // comes in a later task than the unmount, never in the same commit.
      unmount()
      await new Promise((resolve) => setTimeout(resolve, 0))
      renderPricing()
      await screen.findByRole('button', { name: /^current plan$/i })
      expect(screen.queryByText(RETURNED)).not.toBeInTheDocument()
    })

    // Any parent that swaps its element type (here a Fragment for a component) remounts the page in that commit;
    // the flag already left the address, and the notice stays.
    it('keeps the notice when a parent swaps its element type and the page remounts in that commit', async () => {
      mockSearchParams.set('canceled', 'true')
      mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const Provider = ({ children }: { children: React.ReactNode }) => <>{children}</>
      const tree = (consented: boolean) => (
        <QueryClientProvider client={queryClient}>
          {consented ? <Provider><PricingPage /></Provider> : <><PricingPage /></>}
        </QueryClientProvider>
      )
      const { rerender } = render(tree(false))
      const before = await screen.findByText('You can choose a plan below.')
      expect(mockSearchParams.has('canceled')).toBe(false)

      rerender(tree(true))
      const after = await screen.findByText('You can choose a plan below.')
      // A new node: the page remounted, and the notice came with it.
      expect(after).not.toBe(before)
      expect(screen.getByText(RETURNED)).toBeInTheDocument()
    })

    it('an account already on Pro is told its plan is Pro, with no invitation to choose', async () => {
      mockSearchParams.set('canceled', 'true')
      mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub, is_pro: true, status: 'active', plan: 'pro', stripe_customer_id: 'cus_123' })
      renderPricing()

      expect(await screen.findByText('Your plan is Pro.')).toBeInTheDocument()
      expect(screen.getByText(RETURNED)).toBeInTheDocument()
      expect(screen.queryByText('You can choose a plan below.')).not.toBeInTheDocument()
      expect(screen.queryByText(/charged/i)).not.toBeInTheDocument()
      expect(mockReplace).toHaveBeenCalledWith('/pricing', { scroll: false })
    })

    it('says nothing about the plan while the subscription query is pending', async () => {
      mockSearchParams.set('canceled', 'true')
      let resolveSubscription!: (value: SubscriptionStatus) => void
      mockGetSubscriptionStatus.mockReturnValue(new Promise<SubscriptionStatus>((resolve) => { resolveSubscription = resolve }))
      renderPricing()

      await waitFor(() => expect(mockGetSubscriptionStatus).toHaveBeenCalledTimes(1))
      // The title alone: no description names a plan the query has not answered yet.
      expect((await screen.findByText(RETURNED)).closest('[role="status"]')).toHaveTextContent(/^You returned from checkout$/)
      expect(screen.queryByText('You can choose a plan below.')).not.toBeInTheDocument()
      expect(screen.queryByText('Your plan is Pro.')).not.toBeInTheDocument()

      // Once it answers, the plan joins the notice.
      resolveSubscription({ ...baseSub })
      expect(await screen.findByText('You can choose a plan below.')).toBeInTheDocument()
    })

    it('says nothing about a checkout without the flag', async () => {
      mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
      renderPricing()
      await screen.findByRole('button', { name: /^current plan$/i })
      expect(screen.queryByText(RETURNED)).not.toBeInTheDocument()
      expect(mockReplace).not.toHaveBeenCalled()
    })
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
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
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
    expect(screen.getByRole('switch', BILLING_SWITCH)).toBeInTheDocument()
    fireEvent.click(upgrade)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 240, 'yearly')
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
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    )
    // A paid subscriber has nothing to buy — no enabled upgrade/subscribe CTA anywhere.
    expect(screen.queryByRole('button', { name: /subscribe to pro|upgrade to pro/i })).not.toBeInTheDocument()
    // "Current plan" appears exactly once (the Pro card) — never on the Free card too.
    const currentPlanButtons = screen.getAllByRole('button', { name: /current plan/i })
    expect(currentPlanButtons).toHaveLength(1)
    expect(currentPlanButtons[0]).toBeDisabled()
    // The Free card is not the user's plan, and a Pro account is offered no call to action for it: its
    // disabled button names the plan, never the guest's "Create a free account" or "Request an invite".
    const freeButton = screen.getByRole('button', { name: /^free plan$/i })
    expect(freeButton).toBeDisabled()
    expect(screen.queryByRole('button', { name: /create a free account|request an invite/i })).not.toBeInTheDocument()
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

    // Both surfaces open on annual: the $20 per month headline, charged $240 once a year.
    expect(page.getByText('$20')).toBeInTheDocument()
    expect(page.getByText('/month')).toBeInTheDocument()
    expect(page.getByText('Billed annually at $240, saving $60 a year.')).toBeInTheDocument()
    expect(page.getByText('(save 20%)')).toBeInTheDocument()
    expect(home.getByText('$20')).toBeInTheDocument()
    expect(home.getByText('per month')).toBeInTheDocument()
    expect(home.getByText('Billed annually at $240, saving $60 a year.')).toBeInTheDocument()
    expect(home.getByText('· save 20%')).toBeInTheDocument()
    expect(structuredData.offers).toEqual([
      expect.objectContaining({ name: 'Pro (monthly)', price: 25, priceCurrency: 'USD' }),
      expect.objectContaining({ name: 'Pro (annual)', price: 240, priceCurrency: 'USD' }),
    ])

    // Monthly is $25 on both.
    fireEvent.click(home.getByRole('radio', { name: /monthly/i }))
    expect(home.getByText('$25')).toBeInTheDocument()
    expect(home.getByText('Billed monthly. Or $20 a month, billed annually at $240.')).toBeInTheDocument()
    fireEvent.click(page.getByRole('switch', BILLING_SWITCH))
    expect(page.getByText('$25')).toBeInTheDocument()
    expect(page.getByText('Billed monthly')).toBeInTheDocument()
    expect(mockUseFeatureFlagVariantKey).not.toHaveBeenCalled()

    // Wait until auth resolves (the Free card flips to "Current plan") before checkout.
    await page.findByRole('button', { name: /current plan/i })
    fireEvent.click(page.getByRole('button', { name: /upgrade to pro/i }))
    await waitFor(() => expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 25, 'monthly'))
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
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
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
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 240, 'yearly')
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

    // One Retry serves both reads (each Retry reads "Try again", D-032): its press retries every read that failed.
    expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(1)
    expect(mockGetUsage).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await screen.findByRole('button', { name: /^current plan$/i })
    expect(mockGetUsage).toHaveBeenCalledTimes(2)
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

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.queryByText(/couldn't refresh your plan details/i)).not.toBeInTheDocument())
    expect(screen.getAllByRole('button', { name: /current plan/i })).toHaveLength(1)
  })

  it('a guest under the invite gate is offered an invite, never a signup /register would reject', async () => {
    mockGetCurrentUserSafe.mockResolvedValue(null)
    mockGetRegistrationConfig.mockResolvedValue({ mode: 'invite_only', beta_promo_enabled: true })
    renderPricing()

    const free = await screen.findByRole('button', { name: /request an invite/i })
    expect(free).toBeEnabled()
    expect(screen.queryByRole('button', { name: /create a free account/i })).not.toBeInTheDocument()
    fireEvent.click(free)
    expect(mockPush).toHaveBeenCalledWith('/waitlist')
  })

  it('a confirmed guest keeps registration routing on both cards', async () => {
    mockGetCurrentUserSafe.mockResolvedValue(null)
    renderPricing()

    const free = await screen.findByRole('button', { name: /create a free account/i })
    expect(free).toBeEnabled()
    fireEvent.click(free)
    expect(mockPush).toHaveBeenCalledWith('/register')
    fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))
    expect(mockPush).toHaveBeenCalledWith('/register?redirect=%2Fpricing%3Fbilling%3Dyearly')
    expect(mockGetSubscriptionStatus).not.toHaveBeenCalled()
    expect(mockCheckoutStarted).not.toHaveBeenCalled()
  })

  it.each([
    ['monthly', 'monthly', 25],
    ['yearly', 'yearly', 240],
    ['annual', 'yearly', 240],
    ['https://example.com', 'yearly', 240],
    [null, 'yearly', 240],
  ] as const)('incoming billing=%s records the resolved cycle and checks out %s', async (requested, cycle, price) => {
    if (requested !== null) mockSearchParams.set('billing', requested)
    flags.ENABLE_PRO_TRIAL = true
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    const label = cycle === 'monthly' ? 'Start 7-day free trial' : 'Upgrade to Pro'
    const checkout = await screen.findByRole('button', { name: label })
    expect(screen.getByRole('switch', BILLING_SWITCH)).toHaveAttribute('aria-checked', String(cycle === 'yearly'))
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
    fireEvent.click(screen.getByRole('switch', BILLING_SWITCH))
    const checkout = await screen.findByRole('button', { name: 'Upgrade to Pro' })
    expect(screen.getByText('$20')).toBeInTheDocument()
    fireEvent.click(checkout)
    await waitFor(() => expect(mockCreateCheckoutSession).toHaveBeenCalledWith('price_pro_yearly'))
    expect(mockCheckoutStarted).toHaveBeenCalledWith('pro', 240, 'yearly')
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

  it("labels a beta member's struck-through regular price for screen readers", async () => {
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1, email: 'beta@example.com', is_beta: true })
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    renderPricing()

    // The strike is visual only: the struck price carries a hidden label, read before it.
    const regular = await screen.findByText('$20/mo')
    expect(regular).toHaveClass('line-through')
    expect(within(regular).getByText('Regular price')).toHaveClass('sr-only')
    expect(regular).toHaveTextContent(/^Regular price \$20\/mo$/)
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

  it.each([
    ['a beta member', true, false],
    ['a guest on the default annual plan', false, false],
    ['a guest choosing the monthly trial', false, true],
  ] as const)('the actual homepage link preserves its offer at guest pricing for %s', async (_case, showBeta, pickMonthly) => {
    flags.ENABLE_PRO_TRIAL = true
    mockGetCurrentUserSafe.mockResolvedValue(null)
    const landing = render(<PricingSection accessMode={showBeta ? 'invite' : 'public'} showBeta={showBeta} />)
    // The landing opens on annual; the trial is the monthly plan's offer.
    if (pickMonthly) fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    const label = pickMonthly ? 'Start 7-day free trial' : 'Upgrade to Pro'
    const href = screen.getByRole('link', { name: label }).getAttribute('href')!
    landing.unmount()

    // Follow the rendered link instead of inventing a destination independent of the homepage.
    const destination = new URL(href, 'https://www.earningsnerd.io')
    expect(destination.pathname).toBe('/pricing')
    destination.searchParams.forEach((value, key) => mockSearchParams.set(key, value))
    renderPricing()
    expect(await screen.findByRole('button', { name: label })).toBeEnabled()
    expect(screen.getByRole('switch', BILLING_SWITCH)).toHaveAttribute('aria-checked', String(!pickMonthly))
    const trialNote = 'First 7 days free · cancel anytime, no charge'
    if (pickMonthly) {
      expect(screen.getByText(trialNote)).toBeInTheDocument()
    } else {
      expect(screen.queryByRole('button', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
      expect(screen.queryByText(trialNote)).not.toBeInTheDocument()
    }
    expect(mockPricingViewed.mock.calls).toEqual([[pickMonthly ? 'monthly' : 'yearly']])
  })

  // Multi-Period Analysis ships behind ENABLE_ANALYSIS (its route 404s while the flag is off), and the
  // Excel export is its workbook, so the Pro plan lists both only while it ships (audit pub/F06; the
  // landing half is in analysis-route-hidden.spec.tsx).
  it.each([false, true])('lists Multi-Period Analysis and Excel on the Pro plan only while the flag ships them (flag %s)', async (on) => {
    flags.ENABLE_ANALYSIS = on
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    const { container } = renderPricing()
    await screen.findByRole('button', { name: /current plan/i })
    expect(screen.getByText('Ask this Filing, with cited passages you can check')).toBeInTheDocument()
    if (on) {
      expect(container).toHaveTextContent('Unlimited Multi-Period Analysis')
      expect(screen.getByText('PDF, CSV and Excel exports')).toBeInTheDocument()
    } else {
      expect(container).not.toHaveTextContent(/multi-period|excel/i)
      expect(screen.getByText('PDF and CSV exports')).toBeInTheDocument()
    }
  })

  // The Product JSON-LD (app/pricing/layout.tsx) sells what the Pro lists sell, so its description
  // names multi-period analysis only while the flag ships the route.
  it.each([false, true])('names multi-period analysis in the Product JSON-LD only while the flag ships it (flag %s)', (on) => {
    flags.ENABLE_ANALYSIS = on
    const layout = render(<PricingLayout><div /></PricingLayout>)
    const { description } = JSON.parse(layout.container.querySelector('script[type="application/ld+json"]')!.textContent!)
    // The rest of the description reads either way, so neither case passes on an empty one. Filing Q&A has a
    // sentence of its own, outside the list "Unlimited" heads (planLimitsLockstep.spec.ts).
    expect(description).toContain('alerts, and exports. Pro also includes filing Q&A.')
    if (on) expect(description).toContain('multi-period analysis')
    else expect(description).not.toMatch(/multi-period/i)
  })

  // The Free plan names 20-F only while NEXT_PUBLIC_ENABLE_FPI_FILINGS mirrors the API's ENABLE_FPI_FILINGS
  // (the deploy sets the API's flag on, its code default is off; tasks/todo.md F39), and never the
  // "Supported" hedge.
  it.each([true, false])('names the filing forms on the Free plan without a hedge, 20-F only while the FPI flag ships it (flag %s)', async (on) => {
    flags.ENABLE_FPI_FILINGS = on
    mockGetSubscriptionStatus.mockResolvedValue({ ...baseSub })
    const { container } = renderPricing()
    await screen.findByRole('button', { name: /current plan/i })
    expect(screen.getByText(on ? '10-K, 10-Q and 20-F filings from SEC EDGAR' : '10-K and 10-Q filings from SEC EDGAR')).toBeInTheDocument()
    if (!on) expect(container).not.toHaveTextContent('20-F')
    expect(container).not.toHaveTextContent(/Supported/i)
  })
})

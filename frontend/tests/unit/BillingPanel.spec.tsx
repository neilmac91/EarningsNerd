import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { queryKeys } from '@/lib/queryKeys'
import BillingPanel from '@/features/settings/components/BillingPanel'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'

const mockGetCurrentUserSafe = vi.fn()
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => mockGetCurrentUserSafe() }))

// next/link → plain anchor so we can assert href.
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const mockGetSubscriptionStatus = vi.fn<[], Promise<SubscriptionStatus>>()
const mockGetUsage = vi.fn<[], Promise<Usage>>()
const mockCreatePortalSession = vi.fn()

vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => mockGetSubscriptionStatus(),
  getUsage: () => mockGetUsage(),
  createPortalSession: () => mockCreatePortalSession(),
}))

function renderPanel(identity: { id: number } | null = { id: 1 }, pendingIdentity = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  if (!pendingIdentity) queryClient.setQueryData(queryKeys.currentUser(), identity)
  return render(
    <QueryClientProvider client={queryClient}>
      <BillingPanel />
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

describe('BillingPanel', () => {
  beforeEach(() => {
    mockGetCurrentUserSafe.mockReset()
    mockGetCurrentUserSafe.mockResolvedValue({ id: 1 })
    mockGetSubscriptionStatus.mockReset()
    mockGetUsage.mockReset()
    mockCreatePortalSession.mockReset()
    mockGetUsage.mockResolvedValue(baseUsage)
  })

  it('sends a no-card trial user to /pricing to subscribe instead of the failing billing portal', async () => {
    // Reverse-trial user: is_pro but NO stripe_customer_id — the portal would 400 for them.
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'trialing',
      plan: 'pro',
      trial_end: '2026-06-25T00:00:00Z',
    })

    renderPanel()

    const subscribeLink = await screen.findByRole('link', { name: /subscribe to pro/i })
    expect(subscribeLink).toHaveAttribute('href', '/pricing')
    expect(screen.queryByRole('button', { name: /manage billing/i })).not.toBeInTheDocument()
  })

  it.each([null, 'cus_expired'])('labels an expired trial Free and preserves portal routing (%s)', async (customerId) => {
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      status: 'trialing',
      trial_end: '2026-01-01T00:00:00Z',
      stripe_customer_id: customerId,
    })
    mockGetUsage.mockResolvedValue({ ...baseUsage, is_pro: false, summaries_limit: 5 })

    renderPanel()
    expect(await screen.findByText('Free', { exact: true })).toBeInTheDocument()
    expect(screen.queryByText('Pro (trial)', { exact: true })).not.toBeInTheDocument()
    expect(screen.queryByText(/in your Pro trial/)).not.toBeInTheDocument()
    if (customerId) {
      expect(screen.getByRole('button', { name: /manage billing/i })).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /upgrade to pro/i })).not.toBeInTheDocument()
    } else {
      expect(screen.getByRole('link', { name: /upgrade to pro/i })).toHaveAttribute('href', '/pricing')
      expect(screen.queryByRole('button', { name: /manage billing/i })).not.toBeInTheDocument()
    }
  })

  it('shows Manage billing only when the user has a real Stripe customer', async () => {
    mockGetSubscriptionStatus.mockResolvedValue({
      ...baseSub,
      is_pro: true,
      status: 'active',
      plan: 'pro',
      stripe_customer_id: 'cus_123',
      current_period_end: '2027-06-18T00:00:00Z',
    })

    renderPanel()

    expect(await screen.findByRole('button', { name: /manage billing/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /subscribe|upgrade/i })).not.toBeInTheDocument()
  })
})


it('keeps account details absent while identity is unresolved or logged out', async () => {
  mockGetCurrentUserSafe.mockReturnValue(new Promise(() => {}))
  mockGetSubscriptionStatus.mockReset()
  mockGetUsage.mockReset()
  const pending = renderPanel({ id: 1 }, true)
  expect(screen.queryByText('Free')).not.toBeInTheDocument()
  expect(screen.queryByText('Plan')).not.toBeInTheDocument()
  expect(mockGetSubscriptionStatus).not.toHaveBeenCalled()
  expect(mockGetUsage).not.toHaveBeenCalled()
  pending.unmount()
  mockGetCurrentUserSafe.mockResolvedValue(null)
  renderPanel(null)
  expect(screen.queryByText('Plan')).not.toBeInTheDocument()
  expect(mockGetSubscriptionStatus).not.toHaveBeenCalled()
  expect(mockGetUsage).not.toHaveBeenCalled()
})

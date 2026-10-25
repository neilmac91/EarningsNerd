import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LegalReadiness } from '@/features/legal/api/legal-api'
import { legalReady } from './fixtures/legalReady'
import { PublicAccessProvider } from '@/features/marketing/components/PublicAccessProvider'
import PublicAccessLine from '@/features/marketing/components/PublicAccessLine'
import ClosingLine from '@/features/marketing/components/ClosingLine'
import PricingSection from '@/features/marketing/components/PricingSection'
import { WaitlistAccessStatus, WaitlistEntryLink } from '@/features/waitlist/components/WaitlistAccess'
import Header from '@/components/Header'
import type { AccessMode } from '@/features/marketing/lib/access'

const mocks = vi.hoisted(() => ({ read: vi.fn(), pathname: '/', stats: vi.fn() }))
vi.mock('@/features/legal/api/legal-api', () => ({ getLegalReadiness: mocks.read }))
vi.mock('next/navigation', () => ({ usePathname: () => mocks.pathname, useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => null, logout: vi.fn() }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ getWaitlistStats: mocks.stats }))
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/lib/analytics', () => ({ default: { homepageSectionViewed: vi.fn(), billingCycleToggled: vi.fn(), exampleCtaClicked: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (original) => ({ ...(await original<typeof import('@/lib/featureFlags')>()), ENABLE_PRO_TRIAL: true }))

const closed = { ...legalReady, collection_available: false, checkout_available: false, operator: null }
function deferred() {
  let resolve!: (value: LegalReadiness) => void
  const promise = new Promise<LegalReadiness>((done) => { resolve = done })
  return { promise, resolve }
}
function Surface({ mode = 'invite' }: { mode?: AccessMode }) {
  return <PublicAccessProvider>
    <Header accessMode={mode} />
    <PublicAccessLine accessMode={mode} />
    <ClosingLine accessMode={mode} />
    <PricingSection accessMode={mode} showBeta />
    <WaitlistAccessStatus />
    <WaitlistEntryLink className="" />
  </PublicAccessProvider>
}
function open(mode: AccessMode = 'invite') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><Surface mode={mode} /></QueryClientProvider>)
}
const noIntakePromise = () => {
  expect(screen.queryByRole('link', { name: /Request.*invite|Create a free account|Sign up|Join the waitlist/i })).not.toBeInTheDocument()
  expect(screen.queryByText('Free for beta members')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Upgrade to Pro|Start .*free trial/ })).not.toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: /live example/i }).length).toBeGreaterThan(2)
}

beforeEach(() => {
  mocks.read.mockReset().mockResolvedValue(closed)
  mocks.stats.mockReset().mockResolvedValue({ total_signups: 0 })
  mocks.pathname = '/'
})

describe('public access promises follow fresh readiness', () => {
  it.each(['invite', 'public'] as const)('keeps examples and login available while %s intake is checking or closed', async (mode) => {
    const pending = deferred()
    mocks.read.mockReturnValueOnce(pending.promise)
    open(mode)
    noIntakePromise()
    await screen.findByRole('link', { name: 'Log in' })
    await act(async () => pending.resolve(closed))
    expect(screen.getAllByText(/New registrations are currently closed/)).toHaveLength(2)
    noIntakePromise()
    expect(mocks.stats).not.toHaveBeenCalled()
    expect(mocks.read).toHaveBeenCalledTimes(1)
  })

  it.each(['invite', 'public'] as const)('shows the %s intake destination only after collection opens, independently of checkout', async (mode) => {
    mocks.read.mockResolvedValue({ ...legalReady, checkout_available: false })
    open(mode)
    const label = mode === 'invite' ? 'Request an invite' : 'Create a free account'
    const links = await screen.findAllByRole('link', { name: label })
    expect(links.length).toBeGreaterThan(1)
    for (const link of links) expect(link).toHaveAttribute('href', mode === 'invite' ? '/waitlist' : '/register')
    expect(screen.getByRole('link', { name: 'Join the waitlist' })).toHaveAttribute('href', '#waitlist')
    fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    expect(screen.queryByText('Free for beta members')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /free trial/i })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View plans' })).toHaveAttribute('href', '/pricing?billing=monthly')
  })

  it('closes earlier intake on navigation and refuses a late open response after a newer failed recheck', async () => {
    mocks.read.mockResolvedValueOnce(legalReady)
    const view = open()
    await screen.findAllByRole('link', { name: 'Request an invite' })
    const old = deferred()
    mocks.read.mockReturnValueOnce(old.promise)
    mocks.pathname = '/waitlist'
    view.rerender(<QueryClientProvider client={new QueryClient()}><Surface /></QueryClientProvider>)
    noIntakePromise()
    await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(2))
    mocks.read.mockRejectedValueOnce(new Error('offline'))
    fireEvent(window, new Event('focus'))
    await screen.findAllByText(/Registration availability could not be confirmed/)
    noIntakePromise()
    await act(async () => old.resolve(legalReady))
    noIntakePromise()
    expect(mocks.read).toHaveBeenCalledTimes(3)
  })
})

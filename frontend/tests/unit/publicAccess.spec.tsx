import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
import { ACCESS_COPY, accountLabels, accountShortLabels, heldAccessLines, publicAccessCopy, type AccessMode } from '@/features/marketing/lib/access'

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
/** What a reader is shown: the hero line's held lines are in the document, invisible and aria-hidden (E220). */
const shown = { ignore: 'script, style, [aria-hidden="true"]' }
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
  expect(screen.getAllByRole('link', { name: /live example/i }).length).toBeGreaterThan(1)
  const close = screen.getByText(/Start with a real filing:/).closest('p')!
  expect(within(close).getAllByRole('link')).toHaveLength(1)
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

  it('retains confirmed intake during navigation and focus checks, then switches only to the latest completed answer', async () => {
    mocks.read.mockResolvedValueOnce(legalReady)
    const view = open()
    await screen.findAllByRole('link', { name: 'Request an invite' })
    const close = screen.getByText(/Start with a real filing:/).closest('p')!
    const accountAction = within(close).getByRole('link', { name: 'Request an invite' })
    const example = within(close).getByRole('link', { name: /read the Apple/ })
    accountAction.focus()
    const old = deferred()
    mocks.read.mockReturnValueOnce(old.promise)
    mocks.pathname = '/waitlist'
    view.rerender(<QueryClientProvider client={new QueryClient()}><Surface /></QueryClientProvider>)
    await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(2))
    expect(accountAction).toHaveFocus()
    expect(screen.queryByText(/Checking registration availability/, shown)).not.toBeInTheDocument()
    const latest = deferred()
    mocks.read.mockReturnValueOnce(latest.promise)
    fireEvent(window, new Event('focus'))
    await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(3))
    expect(accountAction).toHaveFocus()
    expect(screen.getByText('Private beta · request an invite', shown)).toBeInTheDocument()
    await act(async () => latest.resolve(closed))
    expect(screen.getAllByText(/New registrations are currently closed/)).toHaveLength(2)
    noIntakePromise()
    await waitFor(() => expect(example).toHaveFocus())
    await act(async () => old.resolve(legalReady))
    noIntakePromise()
    expect(screen.getAllByText(/New registrations are currently closed/)).toHaveLength(2)
    mocks.read.mockRejectedValueOnce(new Error('offline'))
    fireEvent(window, new Event('focus'))
    await screen.findAllByText(/Registration availability could not be confirmed/)
    noIntakePromise()
    expect(mocks.read).toHaveBeenCalledTimes(4)
  })
})

describe('the header and the hero keep their place as readiness lands (E220)', () => {
  const MODES = ['invite', 'public'] as const
  const checking = [null, true] as const
  const opened = [legalReady, false] as const
  const closedAnswer = [closed, false] as const
  const unconfirmed = [null, false] as const

  it.each(MODES)("holds every account label the %s bar can print in the header's copy", (mode) => {
    for (const [readiness, loading] of [checking, opened, closedAnswer, unconfirmed]) {
      expect(accountLabels(mode), `${readiness?.collection_available} ${loading}`).toContain(publicAccessCopy(mode, readiness, loading).cta)
    }
  })

  it.each(MODES)('holds every short label the %s compact bar can print in its account link (E223)', (mode) => {
    for (const [readiness, loading] of [checking, opened, closedAnswer, unconfirmed]) {
      expect(accountShortLabels(mode), `${readiness?.collection_available} ${loading}`).toContain(publicAccessCopy(mode, readiness, loading).ctaShort)
    }
    // The mode's own and the live example's: the other mode's label would hold room for a promise this mode does not make.
    expect(accountShortLabels(mode)).toEqual([publicAccessCopy(mode, ...opened).ctaShort, publicAccessCopy(mode, ...checking).ctaShort])
  })

  it.each(MODES)("holds the %s hero line's checking and open lines and no other", (mode) => {
    // Chief design on #1686: the closed line would add a row at some widths and a closed notice to every visit's HTML,
    // and the other mode's line would put a promise this mode does not make there.
    expect(heldAccessLines(mode)).toEqual([publicAccessCopy(mode, ...checking).line, publicAccessCopy(mode, ...opened).line])
    for (const answer of [closedAnswer, unconfirmed]) expect(heldAccessLines(mode)).not.toContain(publicAccessCopy(mode, ...answer).line)
  })

  it.each(MODES)('keeps the %s hero line in one cell with the lines it holds, the shown one alone read', async (mode) => {
    const pending = deferred()
    mocks.read.mockReturnValueOnce(pending.promise)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={client}>
        <PublicAccessProvider>
          <PublicAccessLine accessMode={mode} />
        </PublicAccessProvider>
      </QueryClientProvider>,
    )
    const cells = () => [...container.querySelector('p')!.children] as HTMLElement[]
    const read = () => cells().filter((cell) => !cell.hasAttribute('aria-hidden')).map((cell) => cell.textContent)
    const held = () => {
      for (const cell of cells()) expect(cell).toHaveClass('col-start-1', 'row-start-1')
      for (const cell of cells()) expect(cell.classList.contains('invisible')).toBe(cell.hasAttribute('aria-hidden'))
      // The server HTML's text keeps the lines apart, for a reader of the page without its styles.
      expect(container.querySelector('p')!.textContent).toBe(cells().map((cell) => cell.textContent).join(' '))
      return cells().map((cell) => cell.textContent)
    }
    expect(container.querySelector('p')).toHaveClass('grid')
    expect(held()).toEqual(heldAccessLines(mode))
    expect(read()).toEqual([publicAccessCopy(mode, ...checking).line])
    await act(async () => pending.resolve(legalReady))
    expect(held()).toEqual(heldAccessLines(mode))
    expect(read()).toEqual([ACCESS_COPY[mode].line])
    mocks.read.mockResolvedValueOnce(closed)
    fireEvent(window, new Event('focus'))
    await waitFor(() => expect(read()).toEqual([publicAccessCopy(mode, ...closedAnswer).line]))
    expect(held()).toEqual([...heldAccessLines(mode), publicAccessCopy(mode, ...closedAnswer).line])
    mocks.read.mockRejectedValueOnce(new Error('offline'))
    fireEvent(window, new Event('focus'))
    await waitFor(() => expect(read()).toEqual([publicAccessCopy(mode, ...unconfirmed).line]))
    expect(held()).toEqual([...heldAccessLines(mode), publicAccessCopy(mode, ...unconfirmed).line])
  })
})

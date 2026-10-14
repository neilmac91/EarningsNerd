import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Filing } from '@/features/filings/api/filings-api'
import { GenerateSignupGate } from '@/features/summaries/components/GenerateSignupGate'
import { FREE_SUMMARY_LIMIT, TRIAL_DAYS } from '@/lib/planLimits'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The signup gate a guest gets on a filing with no summary follows the one access decision
 * (features/marketing/lib/access.ts), as the header and pricing page do (filing/F01): in invite-only mode
 * /register rejects a signup without an invite, so the gate asks for an invite instead of offering a free
 * account, and it fails closed to that copy until the registration payload answers, or when it cannot.
 * The trial sentence renders only while the trial ships (ENABLE_PRO_TRIAL), its length from TRIAL_DAYS.
 *
 * The gate shows the invite copy while the query is still loading, so a case that asserts on the first
 * render proves nothing about the answer. Each case waits until the registration query has settled
 * (success or error) and the gate has re-rendered with it, then reads the card.
 */

const state = vi.hoisted(() => ({ registration: vi.fn(), ENABLE_PRO_TRIAL: false }))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: state.registration }))
vi.mock('@/lib/analytics', () => ({ default: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  get ENABLE_PRO_TRIAL() {
    return state.ENABLE_PRO_TRIAL
  },
}))

const filing = { id: 42, filing_type: '10-K', company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } } as Filing

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <GenerateSignupGate filing={filing} entryPoint="test" />
    </QueryClientProvider>,
  )
  return client
}

/** Resolves once the registration query has answered or failed and the gate has rendered that state. */
async function settled(client: QueryClient, status: 'success' | 'error') {
  await waitFor(() => expect(state.registration).toHaveBeenCalled())
  await waitFor(() => expect(client.getQueryState(queryKeys.registrationConfig())?.status).toBe(status))
  // React Query hands the settled result to its observers on a setTimeout(0) queued at the cache
  // write, which is already behind us; one more macrotask inside act() lets that notify and the
  // re-render it causes land before the case reads the card.
  await act(() => new Promise((resolve) => setTimeout(resolve, 0)))
}

beforeEach(() => {
  state.ENABLE_PRO_TRIAL = false
})
afterEach(() => {
  cleanup()
  state.registration.mockReset()
})

describe('GenerateSignupGate', () => {
  it('asks for an invite in invite-only mode, and keeps Log in', async () => {
    state.registration.mockResolvedValue({ mode: 'invite_only', beta_promo_enabled: false })
    await settled(mount(), 'success')
    expect(await screen.findByRole('heading', { level: 2, name: 'Summaries need an account' })).toBeInTheDocument()
    expect(screen.getByText('EarningsNerd is in private beta. Request an invite, or log in if you have one.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
    expect(screen.getByRole('link', { name: 'Log in' }).getAttribute('href')).toMatch(/^\/login\?redirect=/)
    expect(screen.queryByRole('link', { name: 'Create free account' })).toBeNull()
  })

  it('fails closed to the invite copy when the registration payload cannot be read', async () => {
    state.registration.mockRejectedValue(new Error('offline'))
    await settled(mount(), 'error')
    expect(await screen.findByRole('heading', { name: 'Summaries need an account' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
    expect(screen.queryByText(/Free accounts get/)).toBeNull()
    expect(screen.queryByRole('link', { name: 'Create free account' })).toBeNull()
  })

  it('offers the free account in public mode, the trial only while it ships', async () => {
    state.registration.mockResolvedValue({ mode: 'public', beta_promo_enabled: false })
    await settled(mount(), 'success')
    expect(await screen.findByRole('heading', { name: 'Create a free account to summarize this filing' })).toBeInTheDocument()
    expect(screen.getByText(new RegExp(`Free accounts get ${FREE_SUMMARY_LIMIT} AI summaries a month`))).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create free account' }).getAttribute('href')).toMatch(/^\/register\?redirect=/)
    expect(screen.queryByText(/days free/)).toBeNull()
    cleanup()

    state.ENABLE_PRO_TRIAL = true
    mount()
    expect(await screen.findByText(new RegExp(`get ${TRIAL_DAYS} days free, cancel anytime`))).toBeInTheDocument()
  })
})

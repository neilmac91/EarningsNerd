import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import api from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'
import FilingPageClient from '@/app/filing/[id]/page-client'
import analytics from '@/lib/analytics'

const state = vi.hoisted(() => ({ user: { id: 7 } as { id: number } | null, summary: { id: 91, filing_id: 42 } as { id: number; filing_id: number } | null, saved: false, authPending: false }))
vi.mock('next/navigation', () => ({ useParams: () => ({ id: '42' }), useRouter: () => ({ back: vi.fn(), push: vi.fn() }) }))
vi.mock('@/lib/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() }, getApiUrl: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => state.authPending ? new Promise(() => {}) : Promise.resolve(state.user) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getSubscriptionStatus: () => Promise.resolve({ is_pro: false }) }))
vi.mock('@/features/filings/api/filings-api', () => ({ getFiling: () => Promise.resolve({ id: 42, filing_type: '10-K', filing_date: '2026-09-01' }) }))
vi.mock('@/features/summaries/hooks/useSummaryGeneration', () => ({ useSummaryGeneration: () => ({ summary: state.summary, hasSummaryContent: !!state.summary, summaryLoading: false }) }))
vi.mock('@/lib/analytics', () => ({ default: { filingViewed: vi.fn(), summaryGenerated: vi.fn(), summaryViewed: vi.fn(), summarySaved: vi.fn() } }))
vi.mock('@/features/filings/components/copilot/FilingWorkspace', () => ({ default: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock('@/features/filings/components/copilot/FilingViewerContext', () => ({ FilingViewerProvider: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock('@/features/filings/components/copilot/AskAboutSelection', () => ({ default: () => null }))
vi.mock('@/features/filings/components/copilot/AskCopilotRail', () => ({ default: () => null }))
vi.mock('@/features/filings/components/copilot/FilingViewer', () => ({ default: () => null }))
vi.mock('@/features/summaries/components/SummaryDisplay', () => ({ SummaryDisplay: ({ isSaved, isAuthenticated, summary, saveMutation }: { isSaved: boolean; isAuthenticated: boolean; summary: { id: number }; saveMutation: { mutate: (id: number) => void } }) => (
  <button disabled={isSaved || !isAuthenticated} onClick={() => saveMutation.mutate(summary.id)}>{isSaved ? 'Saved' : 'Save'}</button>
) }))

function mount(identity?: { id: number } | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } })
  if (identity !== undefined) client.setQueryData(queryKeys.currentUser(), identity)
  render(<QueryClientProvider client={client}><FilingPageClient /></QueryClientProvider>)
  return client
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  state.user = { id: 7 }
  state.summary = { id: 91, filing_id: 42 }
  state.saved = false
  state.authPending = false
  vi.mocked(api.get).mockImplementation(async (url) => {
    if (url === '/api/saved-summaries/status/91') return { data: { is_saved: state.saved } }
    throw new Error(`Filing page fetched unexpected library endpoint: ${url}`)
  })
  vi.mocked(api.post).mockImplementation(async () => {
    state.saved = true
    return { data: { id: 1, summary_id: 91 } }
  })
})

describe('filing saved status consumer', () => {
  it('reads only this summary and refreshes Saved plus the library after saving', async () => {
    const client = mount()
    client.setQueryData(queryKeys.savedSummaries(), [])
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/saved-summaries/status/91'))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled())
    expect(api.post).toHaveBeenCalledWith('/api/saved-summaries/', { summary_id: 91, notes: undefined })
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(client.getQueryState(queryKeys.savedSummaries())?.isInvalidated).toBe(true)
    client.clear()
  })

  it('shows an existing saved status without downloading library content', async () => {
    state.saved = true
    const client = mount()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled())
    expect(api.get).toHaveBeenCalledTimes(1)
    client.clear()
  })

  it.each(['signed out', 'no summary'])('does not request private status when %s', async (condition) => {
    if (condition === 'signed out') state.user = null
    else state.summary = null
    const client = mount()
    await waitFor(() => expect(client.getQueryState(queryKeys.currentUser())?.status).toBe('success'))
    expect(api.get).not.toHaveBeenCalled()
    client.clear()
  })

  it('does not reuse one account’s saved state after the current user changes', async () => {
    state.saved = true
    const client = mount()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled())
    state.saved = false
    client.setQueryData(queryKeys.currentUser(), { id: 8 })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled())
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
    client.clear()
  })
})

// A later person merge or account transition cannot rewrite the identity of a past view.
describe('summary view event-time identity', () => {
  it.each([{ id: 7 }, null, undefined])('records the current route identity and summary for %j', async (identity) => {
    state.authPending = identity === undefined
    const client = mount(identity)
    await waitFor(() => expect(analytics.summaryViewed).toHaveBeenCalledTimes(1))
    expect(analytics.summaryViewed).toHaveBeenCalledWith(expect.objectContaining({
      identity: identity ? { state: 'authenticated', accountId: '7' } : { state: identity === undefined ? 'unknown' : 'anonymous', accountId: null },
      summaryId: 91, filingId: 42,
    }))
    client.setQueryData(queryKeys.currentUser(), { id: 8 })
    await waitFor(() => expect(client.getQueryData(queryKeys.currentUser())).toEqual({ id: 8 }))
    expect(analytics.summaryViewed).toHaveBeenCalledTimes(1)
    client.clear()
  })
})

/**
 * Rule-#12 gate for signup-before-generation (frontend half; the backend half is
 * backend/tests/unit/test_generation_requires_account.py):
 *
 *   1. A GUEST on a filing with no cached summary must NOT auto-fire generateSummaryStream —
 *      the page shows the signup gate instead (the backend would 401 the call anyway).
 *   2. While the /me query is UNRESOLVED, nobody auto-fires — before it settles,
 *      isAuthenticated is false for everyone, so firing early would 401 a logged-in user's
 *      request mid-race (the bug class that let the old flag-off POC mode ship guest generation).
 *   3. A signed-in user with no cached summary DOES auto-generate (the happy path survived).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { useSummaryGeneration } from '@/features/summaries/hooks/useSummaryGeneration'
import type { Filing } from '@/features/filings/api/filings-api'

vi.mock('@/features/summaries/api/summaries-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/summaries/api/summaries-api')>()
  return {
    ...actual,
    getSummary: vi.fn().mockResolvedValue(null), // no cached summary
    getSummaryProgress: vi.fn().mockResolvedValue({}),
    generateSummaryStream: vi.fn().mockResolvedValue(undefined),
  }
})

import { generateSummaryStream } from '@/features/summaries/api/summaries-api'

const filing = {
  id: 42,
  filing_type: '10-K',
  company: { id: 1, ticker: 'ACME', name: 'Acme Corp' },
} as unknown as Filing

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

function renderGeneration(args: { isAuthenticated: boolean; isAuthResolved: boolean }) {
  return renderHook(
    () =>
      useSummaryGeneration({
        filingId: filing.id,
        filing,
        isAuthenticated: args.isAuthenticated,
        isAuthResolved: args.isAuthResolved,
        entryPoint: 'test',
      }),
    { wrapper },
  )
}

const flush = () => new Promise((r) => setTimeout(r, 50))

describe('signup-before-generation gate (useSummaryGeneration auto-generate)', () => {
  beforeEach(() => {
    vi.mocked(generateSummaryStream).mockClear()
  })

  it('guest + no cached summary: never auto-fires generation', async () => {
    renderGeneration({ isAuthenticated: false, isAuthResolved: true })
    await flush()
    expect(generateSummaryStream).not.toHaveBeenCalled()
  })

  it('auth unresolved: nobody auto-fires (no premature guest-shaped request)', async () => {
    renderGeneration({ isAuthenticated: false, isAuthResolved: false })
    await flush()
    expect(generateSummaryStream).not.toHaveBeenCalled()
  })

  it('signed-in + no cached summary: auto-generates (happy path intact)', async () => {
    renderGeneration({ isAuthenticated: true, isAuthResolved: true })
    await waitFor(() => expect(generateSummaryStream).toHaveBeenCalledTimes(1))
  })

  it('guest calling handleGenerateSummary directly is refused with a sign-in error', async () => {
    const { result } = renderGeneration({ isAuthenticated: false, isAuthResolved: true })
    await act(async () => {
      await result.current.handleGenerateSummary()
    })
    expect(generateSummaryStream).not.toHaveBeenCalled()
    await waitFor(() => expect(result.current.generationError).toMatch(/sign in/i))
  })
})

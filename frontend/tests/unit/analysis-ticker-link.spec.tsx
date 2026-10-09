/**
 * CLEAN-R1: /analysis?ticker=AAPL — the homepage's "Try it on Apple" link — preselects that company,
 * and nothing more: no dataset request and no narrative stream (a run costs AI; only the user's
 * "Run analysis" starts one). The ticker is resolved through the company API before the page trusts
 * it; a malformed one is never sent and an unknown one leaves today's empty picker. A pick the user
 * makes while the link resolves wins. The page owns its <main> landmark (the root layout's #main is a
 * non-landmark skip-link target).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createElement } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import api from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'

vi.mock('@/features/companies/components/CompanySearch', () => ({
  default: ({ onSelect }: { onSelect: (ticker: string) => void }) =>
    createElement('button', { onClick: () => onSelect('MSFT') }, 'Select Microsoft'),
}))
vi.mock('@/lib/analytics', () => ({ default: { analysisRun: vi.fn() } }))

const COMPANIES: Record<string, { id: number; cik: string; ticker: string; name: string }> = {
  AAPL: { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' },
  MSFT: { id: 2, cik: '789019', ticker: 'MSFT', name: 'Microsoft Corp' },
}

const companyCalls = () =>
  (api.get as unknown as { mock: { calls: unknown[][] } }).mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.startsWith('/api/companies/'))

function mount(search: string) {
  window.history.replaceState(null, '', `/analysis${search}`)
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
  client.setQueryData(queryKeys.currentUser(), { id: 7 })
  client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
  for (const ticker of Object.keys(COMPANIES)) {
    client.setQueryData(queryKeys.analysisCoverage(ticker), {
      ticker, company_name: COMPANIES[ticker].name, supported: true, syncing: false,
      annual: [2021, 2022, 2023].map((year) => ({ key: `FY${year}`, fiscal_year: year, period_end: `${year}-12-31`, has_core: true })),
      quarterly: [],
      limits: { annual: 10, quarterly: 12 },
    })
  }
  return render(createElement(QueryClientProvider, { client }, createElement(AnalysisPageClient)))
}

describe('/analysis?ticker= preselects a resolved company and never runs', () => {
  const originalFetch = global.fetch
  let post: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      const ticker = url.replace('/api/companies/', '')
      if (COMPANIES[ticker]) return { data: COMPANIES[ticker] }
      throw Object.assign(new Error('Not found'), { status: 404 })
    })
    post = vi.spyOn(api, 'post')
    global.fetch = vi.fn() as unknown as typeof fetch
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    global.fetch = originalFetch
    window.history.replaceState(null, '', '/')
  })

  it('preselects the linked company and leaves the run to the user', async () => {
    mount('?ticker=AAPL')
    expect(await screen.findByText('Apple Inc.')).toBeTruthy()
    expect(screen.getByText('AAPL')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Run analysis' })).toBeTruthy()
    expect(companyCalls()).toEqual(['/api/companies/AAPL'])
    // Neither the dataset (POST) nor the narrative stream (fetch) is requested by the link.
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('normalises the ticker before resolving it', async () => {
    mount('?ticker=%20aapl%20')
    expect(await screen.findByText('Apple Inc.')).toBeTruthy()
    expect(companyCalls()).toEqual(['/api/companies/AAPL'])
  })

  it('leaves the empty picker for a ticker the API does not know', async () => {
    mount('?ticker=ZZZZ')
    await waitFor(() => expect(companyCalls()).toEqual(['/api/companies/ZZZZ']))
    await act(async () => {})
    expect(screen.queryByText('ZZZZ')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Run analysis' })).toBeNull()
  })

  it.each(['?ticker=../../auth/me', '?ticker=AAPL%3BMSFT', '?ticker=TOOLONGX', '?ticker=', '?company=AAPL', ''])(
    'never sends a malformed or missing ticker (%s)',
    async (search) => {
      mount(search)
      await act(async () => {})
      expect(companyCalls()).toEqual([])
      expect(screen.queryByRole('button', { name: 'Run analysis' })).toBeNull()
    },
  )

  it("keeps the user's own pick when it lands before the link resolves", async () => {
    let resolveApple!: (value: { data: (typeof COMPANIES)['AAPL'] }) => void
    vi.mocked(api.get).mockImplementationOnce(() => new Promise((resolve) => { resolveApple = resolve }) as never)
    mount('?ticker=AAPL')
    await waitFor(() => expect(companyCalls()).toEqual(['/api/companies/AAPL']))
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    expect(await screen.findByText('Microsoft Corp')).toBeTruthy()
    await act(async () => resolveApple({ data: COMPANIES.AAPL }))
    expect(screen.getByText('Microsoft Corp')).toBeTruthy()
    expect(screen.queryByText('Apple Inc.')).toBeNull()
  })

  it('renders inside one <main> landmark', () => {
    mount('')
    const main = screen.getByRole('main')
    expect(within(main).getByRole('heading', { level: 1, name: 'Multi-Period Analysis' })).toBeTruthy()
  })
})

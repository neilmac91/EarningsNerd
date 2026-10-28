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
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, useQuery, onlineManager } from '@tanstack/react-query'
import api from '@/lib/api/client'
import { getCompany } from '@/features/companies/api/companies-api'
import { queryKeys } from '@/lib/queryKeys'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'
import type { AnalysisCoverage } from '@/features/analysis/api/analysis-api'

vi.mock('@/features/companies/components/CompanySearch', () => ({
  default: ({ onSelect }: { onSelect: (ticker: string) => void }) =>
    createElement('button', { onClick: () => onSelect('MSFT') }, 'Select Microsoft'),
}))
vi.mock('@/lib/analytics', () => ({ default: { analysisRun: vi.fn() } }))
// The App Router's search params, read from the jsdom URL on each render (a navigation that keeps the
// page mounted is a URL change plus a re-render).
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }))

const COMPANIES: Record<string, { id: number; cik: string; ticker: string; name: string }> = {
  AAPL: { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' },
  MSFT: { id: 2, cik: '789019', ticker: 'MSFT', name: 'Microsoft Corp' },
}

const companyCalls = () =>
  (api.get as unknown as { mock: { calls: unknown[][] } }).mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.startsWith('/api/companies/'))

/**
 * A second observer of the link's lookup. React Query hands a query's result to all its observers in
 * one batch, on a timer after the fetch settles, so once this reads the resolved ticker the page has
 * re-rendered with the link too: a positive signal for asserting what the page did with it.
 */
function LinkProbe({ ticker }: { ticker: string }) {
  const { data } = useQuery({ queryKey: queryKeys.analysisCompany(ticker), queryFn: () => getCompany(ticker), enabled: false })
  return data ? createElement('output', null, `link resolved: ${data.ticker}`) : null
}

const coverageFor = (ticker: string): AnalysisCoverage => ({
  ticker, company_name: COMPANIES[ticker].name, supported: true, syncing: false,
  annual: [2021, 2022, 2023].map((year) => ({ key: `FY${year}`, fiscal_year: year, period_end: `${year}-12-31`, has_core: true })),
  quarterly: [], limits: { annual: 10, quarterly: 12 },
})
const clients: QueryClient[] = []

function mount(search: string, probeTicker?: string, seedCoverage = true) {
  window.history.replaceState(null, '', `/analysis${search}`)
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
  clients.push(client)
  client.setQueryData(queryKeys.currentUser(), { id: 7 })
  client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
  for (const ticker of seedCoverage ? Object.keys(COMPANIES) : []) {
    client.setQueryData(queryKeys.analysisCoverage(ticker), coverageFor(ticker))
  }
  const tree = () =>
    createElement(
      QueryClientProvider,
      { client },
      createElement(AnalysisPageClient),
      probeTicker ? createElement(LinkProbe, { ticker: probeTicker }) : null,
    )
  const view = render(tree())
  /** A search-param-only navigation: the URL changes and the page re-renders without remounting. */
  const navigate = (next: string) =>
    act(async () => {
      window.history.pushState(null, '', `/analysis${next}`)
      view.rerender(tree())
    })
  return { ...view, navigate, client }
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
    clients.splice(0).forEach((client) => client.clear())
    onlineManager.setOnline(true)
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
    mount('?ticker=AAPL', 'AAPL')
    await waitFor(() => expect(companyCalls()).toEqual(['/api/companies/AAPL']))
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    expect(await screen.findByText('Microsoft Corp')).toBeTruthy()
    await act(async () => resolveApple({ data: COMPANIES.AAPL }))
    // Wait until the resolved link has reached the page (asserting straight after the resolve would
    // run before React Query delivers it, and pass whichever ticker wins).
    expect(await screen.findByText('link resolved: AAPL')).toBeTruthy()
    expect(screen.getByText('Microsoft Corp')).toBeTruthy()
    expect(screen.queryByText('Apple Inc.')).toBeNull()
  })

  it('follows a navigation that keeps the page mounted: a link without a ticker starts the page over', async () => {
    const { navigate } = mount('?ticker=AAPL')
    expect(await screen.findByText('Apple Inc.')).toBeTruthy()
    // The Header's and Footer's /analysis links keep this page mounted.
    await navigate('')
    await waitFor(() => expect(screen.queryByText('Apple Inc.')).toBeNull())
    expect(screen.queryByRole('button', { name: 'Run analysis' })).toBeNull()
    // A link to another ticker preselects it, and a user's earlier pick gives way to it.
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    expect(await screen.findByText('Microsoft Corp')).toBeTruthy()
    await navigate('?ticker=AAPL')
    expect(await screen.findByText('Apple Inc.')).toBeTruthy()
    expect(screen.queryByText('Microsoft Corp')).toBeNull()
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('renders inside one <main> landmark', () => {
    mount('')
    const main = screen.getByRole('main')
    expect(within(main).getByRole('heading', { level: 1, name: 'Multi-Period Analysis' })).toBeTruthy()
  })

  it('keeps an initial offline coverage read unresolved', async () => {
    onlineManager.setOnline(false)
    mount('', undefined, false)
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    expect(await screen.findByRole('status', { name: 'Loading available periods' })).toBeInTheDocument()
    expect(screen.queryByText(/No analyzable reporting history/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run analysis' })).not.toBeInTheDocument()
  })

  it('shows a first-touch history fetch as activity, the words in the ink beside one sage pulse dot, until the periods land', async () => {
    let synced = false
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === '/api/companies/AAPL') return { data: COMPANIES.AAPL }
      if (url === '/api/analysis/AAPL/coverage') {
        return { data: synced ? coverageFor('AAPL') : { ...coverageFor('AAPL'), syncing: true, annual: [], quarterly: [] } }
      }
      throw Object.assign(new Error('Not found'), { status: 404 })
    })
    const { client } = mount('?ticker=AAPL', undefined, false)
    const words = await screen.findByText("Fetching AAPL's full SEC reporting history. The first load takes a few seconds.")
    // A status line in the secondary ink (the census in statusTintResidue.spec.ts keeps it from being an info
    // Notice), with the Ask answer's one pulse dot, sage in both themes and hidden from assistive tech.
    const line = words.closest('[role="status"]') as HTMLElement
    expect(line).toHaveClass('text-text-secondary-light', 'dark:text-text-secondary-dark')
    const dots = line.querySelectorAll('.animate-pulse')
    expect(dots).toHaveLength(1)
    expect(dots[0]).toHaveClass('bg-brand-strong', 'dark:bg-brand-strong-dark')
    expect(dots[0].closest('[aria-hidden="true"]')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Run analysis' })).not.toBeInTheDocument()
    // The poll's next read lands the periods: the line gives way to the picker.
    synced = true
    await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.analysisCoverage('AAPL') }) })
    expect(await screen.findByRole('button', { name: 'Run analysis' })).toBeInTheDocument()
    expect(screen.queryByText(/full SEC reporting history/)).not.toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('recovers coverage in place without losing retry focus or starting a paid run', async () => {
    const user = userEvent.setup()
    mount('?ticker=AAPL', undefined, false)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load available periods.')
    expect(screen.queryByText(/No analyzable reporting history/)).not.toBeInTheDocument()
    let finish!: (value: { data: AnalysisCoverage }) => void
    vi.mocked(api.get).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }) as never)
    const retry = screen.getByRole('button', { name: 'Try again' })
    retry.focus()
    await user.keyboard('{Enter}{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load available periods.')
    expect(retry).toHaveFocus()
    expect(vi.mocked(api.get).mock.calls.filter(([url]) => String(url).endsWith('/coverage'))).toHaveLength(2)
    await act(async () => finish({ data: coverageFor('AAPL') }))
    expect(await screen.findByRole('button', { name: 'Run analysis' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('AAPL').parentElement).toHaveFocus())
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('keeps cached periods and the chosen range through a failed refresh and a changed successful read', async () => {
    const { client } = mount('?ticker=AAPL')
    const user = userEvent.setup()
    const from = await screen.findByRole('combobox', { name: 'From' })
    await user.selectOptions(from, 'FY2022')
    await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.analysisCoverage('AAPL') }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last loaded periods.')
    expect(screen.getByRole('combobox', { name: 'From' })).toHaveValue('FY2022')
    const fresh = coverageFor('AAPL')
    fresh.annual.push({ key: 'FY2024', fiscal_year: 2024, period_end: '2024-12-31', has_core: true })
    vi.mocked(api.get).mockResolvedValueOnce({ data: fresh })
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(screen.getByRole('combobox', { name: 'From' })).toHaveValue('FY2022')
    expect(screen.getByRole('combobox', { name: 'To' })).toHaveValue('FY2023')
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('does not carry a failed company’s coverage or its late recovery into a different selection', async () => {
    const { client } = mount('?ticker=AAPL', undefined, false)
    await screen.findByRole('alert')
    let finish!: (value: { data: AnalysisCoverage }) => void
    vi.mocked(api.get).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }) as never)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(finish).toBeTypeOf('function'))
    act(() => { client.setQueryData(queryKeys.analysisCoverage('MSFT'), coverageFor('MSFT')) })
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    expect(await screen.findByText('Microsoft Corp')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => finish({ data: coverageFor('AAPL') }))
    expect(screen.getByText('Microsoft Corp')).toBeInTheDocument()
    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

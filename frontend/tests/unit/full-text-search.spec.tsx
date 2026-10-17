import React from 'react'
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'

vi.mock('@/features/search/api/search-api', () => ({ searchFullText: vi.fn() }))

import FullTextSearch, { FullTextSearchResults } from '@/features/search/components/FullTextSearch'
import { searchFullText, type FullTextSearchHit } from '@/features/search/api/search-api'
import api, { ApiError } from '@/lib/api/client'

/** An ApiError as lib/api/client builds it when the response body carried a string `detail`. */
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}
const fromBackend = (status: number, detail: string) => Object.assign(new ApiError(status, detail), { backendDetail: detail })

/**
 * The search request as lib/api/client fails it when the response has the given status and body: the
 * real response interceptor runs, so `detail` is the client's own fallback (a bodiless 503's "Service
 * temporarily unavailable" sentence) or axios's text (a bodiless 413), never typed out here.
 */
async function failThroughClient(status: number, data: unknown): Promise<never> {
  const original = api.defaults.adapter
  const adapter: AxiosAdapter = (config: InternalAxiosRequestConfig) => {
    const response = { status, statusText: '', data, headers: new AxiosHeaders(), config }
    return Promise.reject(new AxiosError(`Request failed with status code ${status}`, AxiosError.ERR_BAD_RESPONSE, config, null, response))
  }
  api.defaults.adapter = adapter
  try {
    await api.get('/api/search/full-text')
  } finally {
    api.defaults.adapter = original
  }
  throw new Error('the stub adapter did not fail the request')
}

const hit: FullTextSearchHit = {
  accession_no: '0000320193-24-000123',
  form: '10-K',
  filed_date: '2024-11-01',
  period_ending: '2024-09-28',
  cik: '320193',
  company: 'Apple Inc.',
  ticker: 'AAPL',
  document: 'aapl.htm',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl.htm',
}

describe('FullTextSearchResults', () => {
  it('renders a hit with company, ticker, form, dates and an external document link', () => {
    const { container } = render(<FullTextSearchResults hits={[hit]} />)
    expect(container.textContent).toContain('AAPL')
    expect(container.textContent).toContain('Apple Inc.')
    expect(container.textContent).toContain('10-K')
    expect(container.textContent).toContain('Filed 2024-11-01')
    expect(container.textContent).toContain('Period 2024-09-28')

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(hit.document_url)
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noreferrer')
  })

  it('falls back to sec_url when document_url is missing and labels an unknown filer', () => {
    const partial: FullTextSearchHit = { ...hit, company: null, ticker: null, document_url: null }
    const { container } = render(<FullTextSearchResults hits={[partial]} />)
    expect(container.textContent).toContain('Unknown filer')
    expect(screen.getByRole('link').getAttribute('href')).toBe(partial.sec_url)
  })

  it('renders a non-link row when no URL is available (no empty anchor)', () => {
    const noUrl: FullTextSearchHit = { ...hit, document_url: null, sec_url: null }
    const { container } = render(<FullTextSearchResults hits={[noUrl]} />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(container.textContent).toContain('Apple Inc.')
  })

  it('sets the form code as data-face text, never a chip, and rings and tints the row link inside the clipped list', () => {
    render(<FullTextSearchResults hits={[hit]} />)
    const form = screen.getByText('10-K')
    expect(form).toHaveClass('font-data')
    expect(form.className).not.toMatch(/\b(rounded|border|uppercase|tracking-eyebrow)\b/)
    // The list is overflow-hidden, so an outer ring would be clipped: the inset token instead.
    expect(screen.getByRole('link')).toHaveClass(
      'focus-visible:outline-none',
      'focus-visible:shadow-ring-brand-inset',
      'dark:focus-visible:shadow-ring-brand-inset-dark',
    )
    // Hover brightens to the product's row tint (DESIGN_SYSTEM.md section 6), never darkens.
    expect(screen.getByRole('link')).toHaveClass('hover:bg-brand-weak', 'dark:hover:bg-white/5')
    expect(screen.getByRole('link').className).not.toMatch(/hover:bg-black/)
  })

  it('renders one row per hit', () => {
    render(<FullTextSearchResults hits={[hit, { ...hit, accession_no: '0000320193-23-000077', document: 'aapl2.htm' }]} />)
    expect(screen.getAllByRole('link')).toHaveLength(2)
  })
})

describe('FullTextSearch date filters', () => {
  beforeEach(() => vi.mocked(searchFullText).mockReset())

  it('passes the selected date range to the search request', async () => {
    vi.mocked(searchFullText).mockResolvedValue({ query: '', total: 0, count: 0, hits: [] })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <FullTextSearch />
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByLabelText('Filed on or after'), { target: { value: '2023-01-01' } })
    fireEvent.change(screen.getByLabelText('Filed on or before'), { target: { value: '2023-12-31' } })
    fireEvent.change(screen.getByLabelText(/Search the full text/i), {
      target: { value: 'going concern' },
    })

    await waitFor(() =>
      expect(vi.mocked(searchFullText)).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'going concern', startdt: '2023-01-01', enddt: '2023-12-31' }),
      ),
    )
  })

  it('does not fire a request when the date range is inverted', async () => {
    vi.mocked(searchFullText).mockResolvedValue({ query: '', total: 0, count: 0, hits: [] })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <FullTextSearch />
      </QueryClientProvider>,
    )

    fireEvent.change(screen.getByLabelText('Filed on or after'), { target: { value: '2024-12-31' } })
    fireEvent.change(screen.getByLabelText('Filed on or before'), { target: { value: '2024-01-01' } })
    fireEvent.change(screen.getByLabelText(/Search the full text/i), {
      target: { value: 'going concern' },
    })

    expect(await screen.findByText(/start date must be on or before end date/i)).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 400)) // past the 350ms debounce
    expect(vi.mocked(searchFullText)).not.toHaveBeenCalled()
  })
})

describe('FullTextSearch form filters', () => {
  beforeEach(() => vi.mocked(searchFullText).mockReset())

  it('filters on a chip’s form code, not its label ("Form 4" sends 4, the code EFTS matches)', async () => {
    vi.mocked(searchFullText).mockResolvedValue({ query: '', total: 0, count: 0, hits: [] })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <FullTextSearch />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: '10-K' }))
    fireEvent.click(screen.getByRole('button', { name: 'Form 4' }))
    fireEvent.change(screen.getByLabelText(/Search the full text/i), { target: { value: 'insider' } })

    expect(screen.getByRole('button', { name: 'Form 4' })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() =>
      expect(vi.mocked(searchFullText)).toHaveBeenCalledWith(expect.objectContaining({ q: 'insider', forms: '10-K,4' })),
    )
  })
})

describe('FullTextSearch controls and errors', () => {
  beforeEach(() => vi.mocked(searchFullText).mockReset())

  const renderSearch = () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <FullTextSearch />
      </QueryClientProvider>,
    )
  }
  const search = (q: string) => fireEvent.change(screen.getByLabelText(/Search the full text/i), { target: { value: q } })

  it('rings the form toggles and Clear dates', () => {
    renderSearch()
    fireEvent.change(screen.getByLabelText('Filed on or after'), { target: { value: '2023-01-01' } })
    for (const control of [screen.getByRole('button', { name: '10-K' }), screen.getByRole('button', { name: 'Clear dates' })]) {
      expect(control).toHaveClass('focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark')
    }
  })

  it('an unselected form toggle brightens like a result row; a selected one keeps its tint', () => {
    renderSearch()
    const toggle = screen.getByRole('button', { name: '10-K' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    // In dark it rests on white/5, so its hover steps to white/10 (the product's chip toggles).
    expect(toggle).toHaveClass('hover:bg-brand-weak', 'dark:hover:bg-white/10')
    expect(toggle.className).not.toMatch(/hover:bg-black/)
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(toggle).toHaveClass('bg-brand-weak', 'dark:bg-brand-dark/15')
  })

  it('shows a backend detail (the 429) verbatim, and its Retry runs the search again', async () => {
    vi.mocked(searchFullText)
      .mockRejectedValueOnce(fromBackend(429, 'SEC full-text search is rate-limited right now. Please retry shortly.'))
      .mockResolvedValueOnce({ query: 'going concern', total: 0, count: 0, hits: [] })
    renderSearch()
    search('going concern')
    expect(await screen.findByRole('alert')).toHaveTextContent('SEC full-text search is rate-limited right now. Please retry shortly.')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText(/No filings match/)).toBeInTheDocument()
    expect(vi.mocked(searchFullText)).toHaveBeenCalledTimes(2)
  })

  // At 200% text on a phone the Retry beside the message ran past the alert and the screen (Codex on #1380: 472px at
  // 390px, 848px with a long token). The fix is the Notice's layout; its browser case waits on E39, since CI's e2e
  // build leaves /search off, so this pins the layout (tests/e2e/reflow-200.spec.ts holds the homepage alert's twin).
  it("stacks the Retry under the message, in the message's column, and breaks a long token in the message", async () => {
    vi.mocked(searchFullText).mockRejectedValueOnce(fromBackend(502, 'SEC full-text search failed: EFTS_UPSTREAM_TIMEOUT_EXCEEDED'))
    renderSearch()
    search('going concern')
    const alert = await screen.findByRole('alert')
    const message = within(alert).getByText(/EFTS_UPSTREAM_TIMEOUT_EXCEEDED/)
    const row = within(alert).getByRole('button', { name: 'Try again' }).parentElement as HTMLElement
    expect(alert).toHaveClass('flex', 'items-start')
    expect(alert.className).not.toMatch(/\b(justify-between|items-center)\b/)
    expect(message).toHaveClass('break-words')
    // The message's column holds the message, then the Retry's own row.
    const column = message.parentElement as HTMLElement
    expect(column).toHaveClass('min-w-0', 'flex-1')
    expect([...column.children]).toEqual([message, row])
    expect(row.className).toBe('mt-2.5 flex')
    expect(row.children).toHaveLength(1)
  })

  it.each([
    ['a lost connection (no response)', new ApiError(0, 'Could not reach the server. Try again in a moment.')],
    // FastAPI's 422 carries a list, which reached the UI as "[object Object]" before lib/api/client read it.
    ['a validation list in place of a detail', new ApiError(422, [{ loc: ['query', 'q'], msg: 'too long' }] as unknown as string)],
    ['an error that is not an ApiError', new Error('boom')],
  ])('shows its own sentence for %s', async (_name, error) => {
    vi.mocked(searchFullText).mockRejectedValueOnce(error)
    renderSearch()
    search('going concern')
    expect(await screen.findByRole('alert')).toHaveTextContent('Search did not load. Try again in a minute.')
  })

  // lib/api/client's own fallbacks and axios's text fill `detail` when the body carried none: they are
  // not the backend's words. These run the real interceptor, beside the 429 above.
  it.each([
    ["a bodiless 503 (the client's sentence)", 503, ''],
    ["a bodiless 413 (axios's message)", 413, ''],
    ['a 502 HTML gateway page (the client fallback)', 502, '<html>Bad Gateway</html>'],
  ])('shows its own sentence for %s, never the client text in detail', async (_name, status, data) => {
    const thrown = await failThroughClient(status, data).catch((err: unknown) => err)
    expect(thrown).toBeInstanceOf(ApiError)
    const clientText = (thrown as ApiError).detail
    expect(clientText).toBeTruthy()
    vi.mocked(searchFullText).mockImplementationOnce(() => failThroughClient(status, data))
    renderSearch()
    search('going concern')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Search did not load. Try again in a minute.')
    expect(alert).not.toHaveTextContent(clientText)
  })

  it("shows the backend's own detail word for word (the 502)", async () => {
    vi.mocked(searchFullText).mockRejectedValueOnce(fromBackend(502, 'SEC full-text search is temporarily unavailable.'))
    renderSearch()
    search('going concern')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('SEC full-text search is temporarily unavailable.')
    expect(alert).not.toHaveTextContent('Search did not load')
  })

  it("after a search with results, a failed one's Retry stays up, busy and focused, with no old hits, until it lands", async () => {
    const retry = deferred<{ query: string; total: number; count: number; hits: FullTextSearchHit[] }>()
    vi.mocked(searchFullText)
      .mockResolvedValueOnce({ query: 'apple', total: 1, count: 1, hits: [hit] })
      .mockRejectedValueOnce(fromBackend(502, 'SEC full-text search is temporarily unavailable.'))
      .mockReturnValueOnce(retry.promise)
    renderSearch()
    search('apple')
    expect(await screen.findByText('Apple Inc.')).toBeInTheDocument()
    search('going concern')
    expect(await screen.findByRole('alert')).toHaveTextContent('SEC full-text search is temporarily unavailable.')
    const button = screen.getByRole('button', { name: 'Try again' })
    button.focus()
    fireEvent.click(button)
    await waitFor(() => expect(vi.mocked(searchFullText)).toHaveBeenCalledTimes(3))
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
    // keepPreviousData hands the retry apple's results as a placeholder: none of it may show here.
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(button).toBeInTheDocument()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(document.activeElement).toBe(button)
    expect(screen.queryByText('Apple Inc.')).toBeNull()
    await act(async () => retry.resolve({ query: 'going concern', total: 0, count: 0, hits: [] }))
    expect(await screen.findByText(/No filings match/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(document.activeElement).toBe(screen.getByLabelText(/Search the full text/i))
  })
})

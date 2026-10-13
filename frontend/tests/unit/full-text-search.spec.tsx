import React from 'react'
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/features/search/api/search-api', () => ({ searchFullText: vi.fn() }))

import FullTextSearch, { FullTextSearchResults } from '@/features/search/components/FullTextSearch'
import { searchFullText, type FullTextSearchHit } from '@/features/search/api/search-api'
import { ApiError } from '@/lib/api/client'

/** An ApiError as lib/api/client builds it when the response body carried a string `detail`. */
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}
const fromBackend = (status: number, detail: string) => Object.assign(new ApiError(status, detail), { backendDetail: detail })

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

  it('sets the form code as data-face text, never a chip, and rings the row link inside the clipped list', () => {
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

  it('caps the query at the 400 characters the backend accepts, so its 422 cannot occur', () => {
    renderSearch()
    expect(screen.getByLabelText(/Search the full text/i)).toHaveAttribute('maxLength', '400')
  })

  it('rings the form toggles and Clear dates', () => {
    renderSearch()
    fireEvent.change(screen.getByLabelText('Filed on or after'), { target: { value: '2023-01-01' } })
    for (const control of [screen.getByRole('button', { name: '10-K' }), screen.getByRole('button', { name: 'Clear dates' })]) {
      expect(control).toHaveClass('focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark')
    }
  })

  it('shows a backend detail (the 429) verbatim, and its Retry runs the search again', async () => {
    vi.mocked(searchFullText)
      .mockRejectedValueOnce(fromBackend(429, 'SEC full-text search is rate-limited right now. Please retry shortly.'))
      .mockResolvedValueOnce({ query: 'going concern', total: 0, count: 0, hits: [] })
    renderSearch()
    search('going concern')
    expect(await screen.findByRole('alert')).toHaveTextContent('SEC full-text search is rate-limited right now. Please retry shortly.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText(/No filings match/)).toBeInTheDocument()
    expect(vi.mocked(searchFullText)).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['a lost connection (no response)', new ApiError(0, 'Could not reach the server. Try again in a moment.')],
    // FastAPI's 422 carries a list, which reached the UI as "[object Object]" before lib/api/client read it.
    ['a validation list in place of a detail', new ApiError(422, [{ loc: ['query', 'q'], msg: 'too long' }] as unknown as string)],
    ['an error that is not an ApiError', new Error('boom')],
    // lib/api/client's own fallbacks and axios's text fill `detail` when the body carried none (an HTML
    // gateway page, a 4xx without a detail): they are not the backend's words.
    ['a 502 whose detail is the client fallback', new ApiError(502, 'A server error occurred. Please try again later.')],
    ["a 413 carrying axios's message", new ApiError(413, 'Request failed with status code 413')],
  ])('shows its own sentence for %s', async (_name, error) => {
    vi.mocked(searchFullText).mockRejectedValueOnce(error)
    renderSearch()
    search('going concern')
    expect(await screen.findByRole('alert')).toHaveTextContent('Search did not load. Try again in a minute.')
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
    const button = screen.getByRole('button', { name: 'Retry' })
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

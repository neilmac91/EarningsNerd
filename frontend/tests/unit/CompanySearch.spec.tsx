import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'

// Router is invoked on result click; capture push.
const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

// The network search endpoint — the ONLY source of dropdown rows now that the
// instant local-matches block has been removed.
vi.mock('@/features/companies/api/companies-api', () => ({ searchCompanies: vi.fn() }))

// Analytics is a default-export object used for search tracking.
vi.mock('@/lib/analytics', () => ({
  default: { companySearched: vi.fn(), companySearchResultClicked: vi.fn() },
}))

import CompanySearch from '@/features/companies/components/CompanySearch'
import { searchCompanies, type Company } from '@/features/companies/api/companies-api'

const company = (over: Partial<Company>): Company => ({
  id: 1,
  cik: '0000000000',
  ticker: 'TICK',
  name: 'A Company',
  ...over,
})

const APPLE = company({
  id: 1,
  cik: '0000320193',
  ticker: 'AAPL',
  name: 'Apple Inc.',
  stock_quote: { price: 150.25, change: 2.13, change_percent: 1.42 },
})
const TESLA = company({
  id: 2,
  cik: '0001318605',
  ticker: 'TSLA',
  name: 'Tesla, Inc.',
  stock_quote: { price: 240.1, change: -12.34, change_percent: -4.88 },
})
const NOPRICE = company({
  id: 3,
  cik: '0000789019',
  ticker: 'MSFT',
  name: 'Microsoft Corporation',
  // no stock_quote yet — price still loading
})

const renderSearch = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CompanySearch />
    </QueryClientProvider>,
  )
}

const type = (value: string) =>
  fireEvent.change(screen.getByRole('combobox'), { target: { value } })

describe('CompanySearch dropdown', () => {
  beforeEach(() => {
    push.mockReset()
    vi.mocked(searchCompanies).mockReset()
  })

  it('renders a single unified, theme-aware row with name, ticker, price and signed daily change', async () => {
    vi.mocked(searchCompanies).mockResolvedValue([APPLE, TESLA])
    renderSearch()
    type('a')

    // Names + tickers
    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument(), { timeout: 3000 })
    expect(screen.getByText('Tesla, Inc.')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()

    // Prices
    expect(screen.getByText('$150.25')).toBeInTheDocument()
    expect(screen.getByText('$240.10')).toBeInTheDocument()

    // Delta TEXT uses the 700-level gain.text/loss.text tokens (the 600-level values
    // are graphic/chip-only — they fail AA as text on cream); dark stays the 400-level.
    const gain = screen.getByText(/\(\+1\.42%\)/)
    expect(gain.className).toContain('text-gain-text')
    expect(gain.className).toContain('dark:text-gain-dark')

    const loss = screen.getByText(/\(-4\.88%\)/)
    expect(loss.className).toContain('text-loss-text')
    expect(loss.className).toContain('dark:text-loss-dark')

    // Name + price use theme-aware primary text (never a hardcoded black/white).
    expect(screen.getByText('Apple Inc.').className).toContain('text-text-primary-light')
    expect(screen.getByText('Apple Inc.').className).toContain('dark:text-text-primary-dark')
  })

  it("shows a 'Loading price…' placeholder when a result has no quote yet (same row layout)", async () => {
    vi.mocked(searchCompanies).mockResolvedValue([NOPRICE])
    renderSearch()
    type('msft')

    await waitFor(
      () => expect(screen.getByText('Microsoft Corporation')).toBeInTheDocument(),
      { timeout: 3000 },
    )
    expect(screen.getByText('Loading price...')).toBeInTheDocument()
  })

  it('does NOT render the removed instant-matches block (no second style)', async () => {
    vi.mocked(searchCompanies).mockResolvedValue([APPLE])
    renderSearch()
    // 'AAPL' previously triggered the instant local-match block immediately.
    type('AAPL')

    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument(), { timeout: 3000 })
    // The instant block rendered an "instant" badge — it must be gone.
    expect(screen.queryByText('instant')).not.toBeInTheDocument()
    // Exactly one listbox, one option per network result.
    expect(screen.getAllByRole('listbox')).toHaveLength(1)
    expect(screen.getAllByRole('option')).toHaveLength(1)
  })

  it('navigates to the company page when a result is clicked', async () => {
    vi.mocked(searchCompanies).mockResolvedValue([APPLE])
    renderSearch()
    type('apple')

    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument(), { timeout: 3000 })
    fireEvent.click(screen.getByRole('option'))
    expect(push).toHaveBeenCalledWith('/company/AAPL')
  })
})

describe('CompanySearch accessible name', () => {
  it('lets a visible <label htmlFor="company-search"> name the field when ariaLabel is null (landing hero)', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <label htmlFor="company-search">Or start with a company</label>
        <CompanySearch ariaLabel={null} shortcuts />
      </QueryClientProvider>,
    )
    // Label in Name (WCAG 2.5.3): no aria-label overrides the visible label.
    expect(screen.getByRole('combobox', { name: 'Or start with a company' })).not.toHaveAttribute('aria-label')
    // The secondary action never takes initial focus.
    expect(screen.getByRole('combobox')).not.toHaveFocus()
  })

  it('keeps its own aria-label by default (every other call site)', () => {
    renderSearch()
    expect(screen.getByRole('combobox', { name: 'Search for a company' })).toBeInTheDocument()
  })
})

// "Try Again" stays mounted while the retry it started runs: an errored search has no data, so its
// refetch goes back to pending and the alert, with the focused button in it, used to vanish
// (lessons/frontend-busy-controls-stay-focusable.md, rules (f) and (g)). The component retries a
// failed search once after 1 s before it reports the error, hence the longer waits below.
describe('CompanySearch "Try Again" keeps keyboard focus', () => {
  beforeEach(() => {
    push.mockReset()
    vi.mocked(searchCompanies).mockReset()
  })

  const deferred = <T,>() => {
    let resolve!: (value: T) => void
    let reject!: (reason: unknown) => void
    const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
    return { promise, resolve, reject }
  }
  const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
  /** The search fails, and fails its one automatic retry, so the alert shows. */
  const failSearch = () =>
    vi.mocked(searchCompanies)
      .mockRejectedValueOnce(new Error('Search is down'))
      .mockRejectedValueOnce(new Error('Search is down'))
  let user: ReturnType<typeof userEvent.setup>
  beforeEach(() => { user = userEvent.setup() })
  async function failedTryAgain() {
    renderSearch()
    type('apple')
    const alert = await screen.findByRole('alert', {}, { timeout: 4000 })
    return within(alert).getByRole('button', { name: 'Try again' })
  }

  it('stays mounted, busy and focused while its retry runs, refuses a second press, then hands focus to the field', async () => {
    failSearch()
    const retried = deferred<Company[]>()
    vi.mocked(searchCompanies).mockReturnValueOnce(retried.promise)
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(searchCompanies).toHaveBeenCalledTimes(3))
    await settle()
    expect(tryAgain.isConnected).toBe(true)
    expect(tryAgain).toHaveAttribute('aria-busy', 'true')
    expect(tryAgain).toHaveAttribute('aria-disabled', 'true')
    expect(tryAgain).toHaveAccessibleName('Retrying…')
    expect(document.activeElement).toBe(tryAgain)
    expect(screen.getByText('Search is down')).toBeInTheDocument()
    await user.keyboard('{Enter}')
    // A pointer press while busy is inert too: it neither refetches nor drops the keyboard hand-off.
    fireEvent.click(tryAgain, { detail: 1 })
    await settle()
    expect(searchCompanies).toHaveBeenCalledTimes(3)

    await act(async () => retried.resolve([APPLE]))
    await waitFor(() => expect(tryAgain.isConnected).toBe(false))
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('combobox')))
  }, 10_000)

  it('a retry that fails again leaves the alert and the keyboard user on Try Again, live again', async () => {
    failSearch()
    vi.mocked(searchCompanies)
      .mockRejectedValueOnce(new Error('Still down'))
      .mockRejectedValueOnce(new Error('Still down'))
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))
    await waitFor(() => expect(tryAgain).not.toHaveAttribute('aria-busy'), { timeout: 4000 })
    expect(tryAgain.isConnected).toBe(true)
    expect(tryAgain).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(tryAgain)
    expect(screen.getByText('Still down')).toBeInTheDocument()
  }, 12_000)

  it('a pointer press does not pull focus into the field when the retry succeeds (no touch keyboard)', async () => {
    failSearch()
    vi.mocked(searchCompanies).mockResolvedValueOnce([APPLE])
    const tryAgain = await failedTryAgain()
    await user.click(tryAgain)
    await waitFor(() => expect(tryAgain.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).not.toBe(screen.getByRole('combobox'))
  }, 10_000)

  it('typing a new term drops the failure the retry was holding, before the new search answers', async () => {
    failSearch()
    const retried = deferred<Company[]>()
    const newSearch = deferred<Company[]>()
    vi.mocked(searchCompanies).mockReturnValueOnce(retried.promise).mockReturnValueOnce(newSearch.promise)
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))

    screen.getByRole('combobox').focus()
    type('tesla')
    await waitFor(() => expect(searchCompanies).toHaveBeenLastCalledWith('tesla'))
    await settle()
    // The new search is still loading, and the old term's error is gone.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => newSearch.resolve([TESLA]))
    expect(await screen.findByText('Tesla, Inc.')).toBeInTheDocument()
  }, 10_000)

  it('a retry that failed again leaves no hand-off armed: a later recovery nobody pressed moves no focus', async () => {
    failSearch()
    vi.mocked(searchCompanies)
      .mockRejectedValueOnce(new Error('Still down'))
      .mockRejectedValueOnce(new Error('Still down'))
      .mockResolvedValueOnce([APPLE])
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><CompanySearch /></QueryClientProvider>)
    type('apple')
    const tryAgain = within(await screen.findByRole('alert', {}, { timeout: 4000 })).getByRole('button', { name: 'Try again' })
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))
    await waitFor(() => expect(tryAgain).not.toHaveAttribute('aria-busy'), { timeout: 4000 })
    tryAgain.blur()

    await act(async () => { await qc.refetchQueries({ queryKey: ['companies'] }) })
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    await settle()
    expect(document.activeElement).toBe(document.body)
  }, 15_000)
  it('a retry that fails again with the same message re-inserts it, so the alert is announced again', async () => {
    failSearch()
    vi.mocked(searchCompanies)
      .mockRejectedValueOnce(new Error('Search is down'))
      .mockRejectedValueOnce(new Error('Search is down'))
    const tryAgain = await failedTryAgain()
    const message = screen.getByText('Search is down')
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))
    await waitFor(() => expect(tryAgain).not.toHaveAttribute('aria-busy'), { timeout: 4000 })
    expect(message.isConnected).toBe(false)
    expect(screen.getByText('Search is down')).toBeInTheDocument()
    expect(document.activeElement).toBe(tryAgain)
  }, 12_000)

  it('Escape out of the field while the retry runs moves no focus back into it', async () => {
    failSearch()
    const retried = deferred<Company[]>()
    vi.mocked(searchCompanies).mockReturnValueOnce(retried.promise)
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))

    screen.getByRole('combobox').focus()
    await user.keyboard('{Escape}')
    expect(document.activeElement).toBe(document.body)
    // The debounce drops the term, and with it the failure; the press's retry then lands too late.
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 400)) })
    await act(async () => retried.resolve([APPLE]))
    await settle()
    expect(document.activeElement).toBe(document.body)
  }, 10_000)

  it('switching to a term already cached is not the retry\'s success: it moves no focus', async () => {
    vi.mocked(searchCompanies).mockResolvedValueOnce([TESLA])
    failSearch()
    const retried = deferred<Company[]>()
    vi.mocked(searchCompanies).mockReturnValueOnce(retried.promise)
    renderSearch()
    type('tesla')
    await screen.findByText('Tesla, Inc.')
    type('apple')
    const tryAgain = within(await screen.findByRole('alert', {}, { timeout: 4000 })).getByRole('button', { name: 'Try again' })
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))

    // Back to the cached term, then away from the field before the debounce lands: its results show
    // at once, but they are not what the press asked for.
    const field = screen.getByRole('combobox')
    field.focus()
    type('tesla')
    field.blur()
    await screen.findByText('Tesla, Inc.')
    await settle()
    expect(document.activeElement).toBe(document.body)
  }, 10_000)

  it('a keyboard user who moved on keeps their focus when the retry succeeds', async () => {
    failSearch()
    const retried = deferred<Company[]>()
    vi.mocked(searchCompanies).mockReturnValueOnce(retried.promise)
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(tryAgain).toHaveAttribute('aria-busy', 'true'))
    const elsewhere = document.createElement('button')
    document.body.appendChild(elsewhere)
    try {
      elsewhere.focus()
      await act(async () => retried.resolve([APPLE]))
      await waitFor(() => expect(tryAgain.isConnected).toBe(false))
      await settle()
      expect(document.activeElement).toBe(elsewhere)
    } finally {
      elsewhere.remove()
    }
  }, 10_000)

  it('a retry paused offline stays busy, keeps its alert and focus, and resumes when back online', async () => {
    failSearch()
    // The press's attempt fails, and the component's own retry (1 s later) finds the browser offline.
    vi.mocked(searchCompanies)
      .mockRejectedValueOnce(new Error('Search is down'))
      .mockResolvedValueOnce([APPLE])
    const tryAgain = await failedTryAgain()
    tryAgain.focus()
    try {
      await user.keyboard('{Enter}')
      await waitFor(() => expect(searchCompanies).toHaveBeenCalledTimes(3))
      act(() => onlineManager.setOnline(false))
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1300)) })
      expect(searchCompanies).toHaveBeenCalledTimes(3)
      expect(tryAgain.isConnected).toBe(true)
      expect(tryAgain).toHaveAttribute('aria-busy', 'true')
      expect(document.activeElement).toBe(tryAgain)

      act(() => onlineManager.setOnline(true))
      await waitFor(() => expect(tryAgain.isConnected).toBe(false))
      await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('combobox')))
    } finally {
      onlineManager.setOnline(true)
    }
  }, 12_000)
})

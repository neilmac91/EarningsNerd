import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

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

import CompanySearch from '@/components/CompanySearch'
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

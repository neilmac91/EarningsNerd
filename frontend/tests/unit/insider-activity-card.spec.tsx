import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { InsiderActivityResponse } from '@/features/insiders/api/insiders-api'
import { ApiError } from '@/lib/api/client'

/**
 * The company page's Insider activity card (ADR 0009): the last 90 days in three lines and a link to the company's
 * insider page. The component wraps what the page lays out and hands it the card, or null until there is something
 * to show (tests/unit/company-insiders-placement.spec.tsx holds that on the page itself); the harness below renders
 * what it is handed, so a case that expects no card proves it was handed null.
 */

const getInsiderActivity = vi.fn()
vi.mock('@/features/insiders/api/insiders-api', () => ({
  getInsiderActivity: (...args: unknown[]) => getInsiderActivity(...args),
}))
const getCurrentUserSafe = vi.fn()
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: (...args: unknown[]) => getCurrentUserSafe(...args),
}))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

import { InsiderActivityCard, insidersHref } from '@/features/insiders/components/InsiderActivityCard'

const BETA = { id: 1, email: 'reader@example.test', full_name: null, is_pro: false, is_beta: true, is_admin: false, email_verified: true }

const SCAN = { status: 'complete', filings_listed: 60, filings_read: 60, oldest_filed_date: '2026-03-02', refreshed_at: '2026-11-14T10:00:00Z', retry_after_seconds: null } as InsiderActivityResponse['scan']
const SELLING: InsiderActivityResponse = {
  ticker: 'NVDA', company_name: 'NVIDIA Corp', cik: '1045810', window_days: 90,
  summary: {
    window_days: 90, buy_count: 0, sell_count: 41, buy_shares: 0, sell_shares: 1284000, buy_value: null, sell_value: 297900000,
    net_shares: -1284000, net_value: -297900000, discretionary_net_shares: -1054000, plan_10b5_1_sell_shares: 230000,
    last_transaction_date: '2026-10-01',
  },
  transactions: [], total_transactions: 41, scan: SCAN,
}
const BUYING: InsiderActivityResponse = {
  ...SELLING,
  summary: { ...SELLING.summary, buy_count: 1, sell_count: 2, buy_shares: 12000, sell_shares: 9500, buy_value: 1803000, sell_value: 1461500, net_shares: 2500, net_value: 341500 },
  total_transactions: 3,
}
const NONE: InsiderActivityResponse = {
  ...SELLING,
  summary: { ...SELLING.summary, buy_count: 0, sell_count: 0, sell_shares: 0, sell_value: null, net_shares: 0, net_value: null },
  total_transactions: 0,
}
const scanning = (over: Partial<InsiderActivityResponse['scan']> = {}): InsiderActivityResponse['scan'] => ({ ...SCAN, status: 'scanning', filings_read: 16, retry_after_seconds: 8, ...over })

/** The company page's mount, with nothing around the card. */
function Mount({ ticker }: { ticker: string }) {
  return (
    <InsiderActivityCard key={ticker} ticker={ticker} isFpi={false}>
      {(card) => card}
    </InsiderActivityCard>
  )
}
function renderCard(ticker = 'NVDA', queries: Record<string, unknown> = { retry: false }) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries } })}>
      <Mount ticker={ticker} />
    </QueryClientProvider>,
  )
}
const card = () => screen.getByRole('complementary', { name: 'Insider activity' })
const noCard = () => expect(screen.queryByRole('complementary', { name: 'Insider activity' })).toBeNull()
/** Let the reader's read and anything it enables settle. */
const settle = () => act(async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0)) })
const rows = () => within(card()).getAllByRole('listitem').map((li) => li.textContent?.replace(/\s+/g, ' ').trim())
/** The card's status region: the one live region with no name of its own (the bones' is named). */
const statusRegion = () => within(card()).getAllByRole('status').find((el) => !el.getAttribute('aria-label'))!

beforeEach(() => {
  getInsiderActivity.mockReset()
  getCurrentUserSafe.mockReset()
  getCurrentUserSafe.mockResolvedValue(BETA)
})

describe('InsiderActivityCard', () => {
  it('reads the last 90 days once the reader is known to be a beta account', async () => {
    getInsiderActivity.mockResolvedValue(SELLING)
    renderCard()
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalledWith('NVDA', 90))
    expect(await screen.findByText('Form 4 · last 90 days')).toBeInTheDocument()
  })

  it.each([
    ['a guest', null],
    ['an account that is not a beta tester', { ...BETA, is_beta: false }],
  ])('%s: nothing is asked and there is nothing to show', async (_, reader) => {
    getCurrentUserSafe.mockResolvedValue(reader)
    getInsiderActivity.mockResolvedValue(SELLING)
    renderCard()
    await waitFor(() => expect(getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(getInsiderActivity).not.toHaveBeenCalled()
    noCard()
  })

  it('says net selling in words, a glyph and the loss ink, then each side with its trades', async () => {
    getInsiderActivity.mockResolvedValue(SELLING)
    renderCard()
    await screen.findByText('Net selling')
    expect(rows()).toEqual(['Net selling▼ $297.9M', 'BuysNone', 'Sells$297.9M41 trades'])
    const figure = within(within(card()).getAllByRole('listitem')[0]).getByText('$297.9M', { exact: false })
    expect(figure.className).toMatch(/text-loss-text/)
    expect(figure.className).toMatch(/dark:text-loss-dark/)
    expect(within(figure).getByText('▼', { exact: false })).toHaveAttribute('aria-hidden', 'true')
  })

  it('says net buying with an up glyph in the gain ink, and counts one trade in the singular', async () => {
    getInsiderActivity.mockResolvedValue(BUYING)
    renderCard()
    await screen.findByText('Net buying')
    expect(rows()).toEqual(['Net buying▲ $341.5K', 'Buys$1.8M1 trade', 'Sells$1.5M2 trades'])
    expect(within(within(card()).getAllByRole('listitem')[0]).getByText('$341.5K', { exact: false }).className).toMatch(/text-gain-text/)
  })

  it('falls back to shares where a side has no dollar value, and to a share count for the net', async () => {
    getInsiderActivity.mockResolvedValue({ ...SELLING, summary: { ...SELLING.summary, sell_value: null, net_value: null } })
    renderCard()
    await screen.findByText('Net selling')
    expect(rows()).toEqual(['Net selling▼ 1.3M shares', 'BuysNone', 'Sells1.3M sh41 trades'])
  })

  it('links to the company’s insider page, in a label with no figure', async () => {
    getInsiderActivity.mockResolvedValue(SELLING)
    renderCard('BRK-B')
    const link = await screen.findByRole('link', { name: 'Open insider activity' })
    expect(link).toHaveAttribute('href', '/company/BRK-B/insiders')
    expect(insidersHref('BRK-B')).toBe('/company/BRK-B/insiders')
  })

  it('has nothing to show until the endpoint first answers, so a reader it refuses never sees a card appear and go', async () => {
    getInsiderActivity.mockReturnValue(new Promise(() => {}))
    renderCard()
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalledTimes(1))
    noCard()
  })

  it('says a complete scan found no trades, and still links to the other windows', async () => {
    getInsiderActivity.mockResolvedValue(NONE)
    renderCard()
    expect(await screen.findByText('No open-market insider trades in the last 90 days.')).toBeInTheDocument()
    expect(within(card()).queryByRole('listitem')).not.toBeInTheDocument()
    expect(within(card()).getByRole('link', { name: 'Open insider activity' })).toBeInTheDocument()
  })

  it('a first visit says the filings are being read, in the status region, and claims no empty window', async () => {
    getInsiderActivity.mockResolvedValue({ ...NONE, scan: scanning({ filings_listed: 0, filings_read: 0, oldest_filed_date: null }) })
    renderCard()
    await screen.findByText('Reading recent Form 4 filings.')
    expect(statusRegion()).toHaveTextContent('Reading recent Form 4 filings.')
    expect(within(card()).queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
    expect(within(card()).queryByRole('progressbar')).not.toBeInTheDocument()   // the count is the insider page's
  })

  it('a scan part-way through shows what is stored so far under the words', async () => {
    getInsiderActivity.mockResolvedValue({ ...BUYING, scan: scanning() })
    renderCard()
    await screen.findByText('Net buying')
    // The words alone: no count and no date, so nothing that moves with each answer is read out.
    expect(statusRegion()).toHaveTextContent(/^Reading recent Form 4 filings\.$/)
  })

  it('a paused scan says it resumes on its own', async () => {
    getInsiderActivity.mockResolvedValue({ ...NONE, scan: scanning({ status: 'paused', retry_after_seconds: 300 }) })
    renderCard()
    expect(await screen.findByText('Reading Form 4 filings is paused and resumes on its own.')).toBeInTheDocument()
    expect(within(card()).queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
  })

  it('a failed scan says insider activity is unavailable, and claims no empty window', async () => {
    getInsiderActivity.mockResolvedValue({ ...NONE, scan: { ...SCAN, status: 'failed' } })
    renderCard()
    expect(await screen.findByText('Insider activity is unavailable for this company right now.')).toBeInTheDocument()
    expect(within(card()).queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
  })

  it.each([
    ['a server error', new ApiError(500, 'Internal Server Error')],
    ['a dropped connection', new ApiError(0, 'Network Error')],
  ])('%s: a Notice whose Try again asks again, and no retry of its own', async (_, error) => {
    getInsiderActivity.mockRejectedValueOnce(error).mockResolvedValue(SELLING)
    renderCard('NVDA', { retry: 3, retryDelay: 0 })
    const alert = await screen.findByRole('alert')
    expect(within(card()).getByRole('alert')).toBe(alert)
    expect(alert).toHaveTextContent('Couldn’t load insider activity')
    expect(getInsiderActivity).toHaveBeenCalledTimes(1)

    await userEvent.setup().click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Net selling')).toBeInTheDocument()
    expect(getInsiderActivity).toHaveBeenCalledTimes(2)
  })

  it.each([401, 403, 404])('a %i (a refusal: the endpoint switched off, or a company it does not know) shows no card and asks once', async (status) => {
    getInsiderActivity.mockRejectedValue(new ApiError(status, 'Refused'))
    renderCard('NVDA', { retry: 3, retryDelay: 0 })
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalled())
    await settle()
    noCard()
    expect(getInsiderActivity).toHaveBeenCalledTimes(1)
  })
})

describe('InsiderActivityCard: while a scan is under way', () => {
  /** Under fake timers: let the reader's read, then the insider read it enables, land. */
  const land = async () => { for (let i = 0; i < 4; i++) await act(async () => { await vi.advanceTimersByTimeAsync(5) }) }

  it('a poll that fails keeps the answer it already has, under the Notice', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false })
    try {
      getInsiderActivity.mockResolvedValueOnce({ ...BUYING, scan: scanning() }).mockRejectedValue(new ApiError(500, 'Internal Server Error'))
      renderCard()
      await land()
      expect(within(card()).getByText('Net buying')).toBeInTheDocument()
      await act(async () => { await vi.advanceTimersByTimeAsync(8_001) })
      expect(within(card()).getByRole('alert')).toHaveTextContent('Couldn’t load insider activity')
      expect(within(card()).getByText('Net buying')).toBeInTheDocument()
      expect(within(card()).getByRole('link', { name: 'Open insider activity' })).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it.each([401, 404])('a later read the endpoint refuses (%i: a session ended, its switch turned off) takes the card away, answer and all', async (status) => {
    vi.useFakeTimers({ shouldAdvanceTime: false })
    try {
      getInsiderActivity.mockResolvedValueOnce({ ...BUYING, scan: scanning() }).mockRejectedValue(new ApiError(status, 'Refused'))
      renderCard()
      await land()
      expect(within(card()).getByText('Net buying')).toBeInTheDocument()
      await act(async () => { await vi.advanceTimersByTimeAsync(8_001) })
      noCard()
      expect(screen.queryByText('Net buying')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('another company starts its own three minutes: the read is keyed by ticker', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false })
    try {
      getInsiderActivity.mockResolvedValue({ ...BUYING, scan: scanning() })
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const view = render(<QueryClientProvider client={client}><Mount ticker="NVDA" /></QueryClientProvider>)
      await land()
      await act(async () => { await vi.advanceTimersByTimeAsync(3 * 60_000 + 10) })
      expect(statusRegion()).toHaveTextContent('Reading continues in the background. Reload the page to see more.')

      view.rerender(<QueryClientProvider client={client}><Mount ticker="TSLA" /></QueryClientProvider>)
      await land()
      expect(statusRegion()).toHaveTextContent(/^Reading recent Form 4 filings\.$/)
      const asked = getInsiderActivity.mock.calls.filter(([t]) => t === 'TSLA').length
      await act(async () => { await vi.advanceTimersByTimeAsync(8_001) })
      expect(getInsiderActivity.mock.calls.filter(([t]) => t === 'TSLA').length).toBe(asked + 1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('asks again at the interval the answer gives, then stops and says how to see more', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false })
    try {
      getInsiderActivity.mockResolvedValue({ ...BUYING, scan: scanning() })
      renderCard()
      await act(async () => { await vi.advanceTimersByTimeAsync(10) })
      expect(getInsiderActivity).toHaveBeenCalledTimes(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(8_001) })
      expect(getInsiderActivity).toHaveBeenCalledTimes(2)

      await act(async () => { await vi.advanceTimersByTimeAsync(3 * 60_000) })
      const asked = getInsiderActivity.mock.calls.length
      expect(statusRegion()).toHaveTextContent('Reading continues in the background. Reload the page to see more.')
      await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
      expect(getInsiderActivity).toHaveBeenCalledTimes(asked)
    } finally {
      vi.useRealTimers()
    }
  })
})

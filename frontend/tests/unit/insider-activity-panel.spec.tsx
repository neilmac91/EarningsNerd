import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const getInsiderActivity = vi.fn()
vi.mock('@/features/insiders/api/insiders-api', () => ({
  getInsiderActivity: (...args: unknown[]) => getInsiderActivity(...args),
}))

import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'

// isFpi defaults to false ("known domestic") so the live read is enabled — the panel only queries
// once the parent knows the company is not a foreign private issuer (isFpi === false).
function renderPanel(ticker = 'AAPL', isFpi: boolean | undefined = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <InsiderActivityPanel ticker={ticker} isFpi={isFpi} />
    </QueryClientProvider>,
  )
}

const txn = (over: Record<string, unknown> = {}) => ({
  insider_name: 'Jane Doe',
  insider_title: 'CEO',
  is_director: false,
  is_officer: true,
  is_ten_pct_owner: false,
  ticker: 'AAPL',
  transaction_date: '2024-05-01',
  transaction_code: 'P',
  transaction_label: 'Purchase',
  shares: 10000,
  price: 180,
  value: 1800000,
  acquired_disposed: 'A',
  is_10b5_1: false,
  accession: '0000000000-24-000001',
  filed_date: '2024-05-02',
  ...over,
})

const RESP = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  cik: '0000320193',
  window_days: 90,
  summary: {
    window_days: 90,
    buy_count: 2,
    sell_count: 1,
    buy_shares: 15000,
    sell_shares: 5000,
    buy_value: 2700000,
    sell_value: 900000,
    net_shares: 10000,
    net_value: 1800000,
    discretionary_net_shares: 10000,
    plan_10b5_1_sell_shares: 0,
    last_transaction_date: '2024-05-01',
  },
  transactions: [txn(), txn({ insider_name: 'John Roe', is_10b5_1: true, acquired_disposed: 'D', transaction_label: 'Sale' })],
  total_transactions: 3,
}

describe('InsiderActivityPanel', () => {
  beforeEach(() => getInsiderActivity.mockReset())

  it('renders the net-buying signal and a transactions row', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()

    expect(await screen.findByText('Insider activity')).toBeInTheDocument()
    expect(screen.getByText(/Net insider buying/)).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    // The 10b5-1 sale row carries the badge.
    expect(screen.getByText('10b5-1')).toBeInTheDocument()
  })

  it('surfaces the 10b5-1 exclusion note when there are pre-scheduled sells', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      summary: { ...RESP.summary, plan_10b5_1_sell_shares: 50000, discretionary_net_shares: 12000 },
    })
    renderPanel()

    expect(await screen.findByText(/pre-scheduled 10b5-1 plans/)).toBeInTheDocument()
  })

  it('signs the discretionary net, so a net sale never reads as a purchase (CO-21)', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      summary: { ...RESP.summary, plan_10b5_1_sell_shares: 50000, discretionary_net_shares: -1_200_000 },
    })
    renderPanel()
    expect(await screen.findByText(/pre-scheduled 10b5-1 plans/)).toHaveTextContent('discretionary net \u22121.2M shares')
  })

  // E76: the summary reads share counts the API always sends, so a missing dollar value falls back to them and no
  // line joins the missing-value token with a unit, a sign or a middot. A trade's missing share count, value or date
  // is the token alone in its cell, which assistive tech reads as "unavailable".
  it('never joins the missing-value dash with copy: missing dollar values fall back to shares, a missing cell reads as unavailable', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      summary: { ...RESP.summary, buy_value: null, sell_value: null, net_value: null, plan_10b5_1_sell_shares: 50000, discretionary_net_shares: -1_200_000 },
      transactions: [txn({ shares: null, value: null, transaction_date: null })],
    })
    renderPanel()

    expect(await screen.findByText(/Net insider buying/)).toHaveTextContent(/^Net insider buying · 10\.0K shares$/)
    expect(screen.getByText(/pre-scheduled 10b5-1 plans/)).toHaveTextContent(
      /^Excludes 50\.0K shares sold under pre-scheduled 10b5-1 plans · discretionary net −1\.2M shares$/,
    )
    expect(screen.getByText('15.0K sh')).toBeInTheDocument()
    expect(screen.getByText('5.0K sh')).toBeInTheDocument()
    expect(screen.getByText('+10.0K shares')).toBeInTheDocument()

    const [, , sharesCell, valueCell, dateCell] = within(screen.getByRole('row', { name: /Jane Doe/ })).getAllByRole('cell')
    for (const cell of [sharesCell, valueCell, dateCell]) {
      expect(cell).toHaveAccessibleName('unavailable')
      expect(within(cell).getByText('—')).toHaveAttribute('aria-hidden', 'true')
      expect(cell).toHaveTextContent(/^—unavailable$/)
    }
  })

  // E88: a missing name or role is MissingValue with words of its own, never the bare token and never "unavailable"
  // alone, which would read as the insider being unavailable: "name unavailable", and "no role listed" where the
  // filing gives no title and flags none of the three roles.
  it('reads a missing name and role in words of their own', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      transactions: [txn({ insider_name: null, insider_title: null, is_officer: false, is_director: false, is_ten_pct_owner: false })],
    })
    renderPanel()

    const [insider] = within(await screen.findByRole('row', { name: /name unavailable/ })).getAllByRole('cell')
    expect(insider).toHaveTextContent(/^—name unavailable—no role listed$/)
    for (const words of ['name unavailable', 'no role listed']) expect(within(insider).getByText(words)).toHaveClass('sr-only')
    const dashes = within(insider).getAllByText('—')
    expect(dashes).toHaveLength(2)
    for (const dash of dashes) expect(dash).toHaveAttribute('aria-hidden', 'true')
  })

  // Three fixed tracks left each tile about 13px for its figure at 200% text on a 390px phone, and content-sized tiles
  // made the tinted row change shape with the data. The tiles take equal tracks of at least 5.5rem, as many as fit, so
  // they stay one width and stack when enlarged text leaves no room; the figures are in the data face (DESIGN_SYSTEM.md §3).
  it('lays the buy, sell and net tiles in equal tracks with a rem minimum, figures in the data face', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()
    const row = (await screen.findByText(/^Buys \(2\)$/)).parentElement!.parentElement!
    expect(row).toHaveClass('grid', 'grid-cols-[repeat(auto-fit,minmax(min(5.5rem,100%),1fr))]')
    expect(row.className).not.toMatch(/\bflex\b|flex-wrap|grid-cols-3/)
    expect(row.children).toHaveLength(3)
    for (const tile of Array.from(row.children)) {
      expect(tile).toHaveClass('min-w-0')
      expect(tile.className).not.toMatch(/flex-auto|flex-1/)
      expect(tile.lastElementChild).toHaveClass('break-words', 'font-data', 'tabular-nums')
    }
  })

  it('marks each trade type with a hidden ▲/▼ beside its label, and names the 10b5-1 badge plainly', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()
    const buy = await screen.findByText('Purchase', { exact: false })
    expect(buy.closest('td')).toHaveTextContent('▲ Purchase')
    expect(screen.getByText('Sale', { exact: false }).closest('td')).toHaveTextContent('▼ Sale')
    for (const glyph of screen.getAllByText(/^[▲▼]\s*$/)) expect(glyph).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText(/10b5-1 marks a trade scheduled in advance under a trading plan\./)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Time window' })).toBeInTheDocument()
  })

  // The company page reaches phones and 200% text, so both segment heights are rem and grow with the root:
  // below sm h-9 (2.25rem) with text-sm, the touch size; from sm up 1.625rem (26px at the default root) with
  // text-xs, whose line box (32px at a 32px root) a fixed 26px could not hold. size="sm" would hold the phone
  // at the desktop size. FilingIndex's filter does the same.
  it('sizes the time window with the text: adaptive segments, 2.25rem below sm and 1.625rem from sm up', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()
    const group = await screen.findByRole('group', { name: 'Time window' })
    const segments = within(group).getAllByRole('button')
    expect(segments.map((segment) => segment.textContent)).toEqual(['90D', '180D', '1Y'])
    for (const segment of segments) {
      const classes = segment.className.split(/\s+/)
      expect(classes).toEqual(expect.arrayContaining(['h-9', 'text-sm', 'sm:h-[1.625rem]', 'sm:text-xs']))
      expect(classes).not.toContain('h-[26px]')
      expect(classes).not.toContain('text-xs')
    }
  })

  it('refetches with a new window when the window is changed', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    const user = userEvent.setup()
    renderPanel('AAPL')

    await screen.findByText('Insider activity')
    await user.click(screen.getByRole('button', { name: '1Y' }))
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalledWith('AAPL', 365))
  })

  it('renders nothing when there are no trades', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      transactions: [],
      total_transactions: 0,
    })
    renderPanel()

    await waitFor(() => expect(screen.queryByText('Insider activity')).not.toBeInTheDocument())
  })

  it('shows the FPI note and skips the live SEC read for foreign private issuers', async () => {
    renderPanel('BABA', true)

    expect(
      await screen.findByText(/not generally required for foreign private issuers/),
    ).toBeInTheDocument()
    expect(getInsiderActivity).not.toHaveBeenCalled()
  })

  it('does not query until FPI status is known (isFpi undefined while filings load)', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    // Render WITHOUT the isFpi prop so it is genuinely undefined — passing `undefined` to
    // renderPanel would trigger its default of false. enabled is gated on isFpi === false, so the
    // live read must not fire while FPI status is still unknown.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <InsiderActivityPanel ticker="AAPL" />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(getInsiderActivity).not.toHaveBeenCalled())
    expect(screen.queryByText('Insider activity')).not.toBeInTheDocument()
  })
})

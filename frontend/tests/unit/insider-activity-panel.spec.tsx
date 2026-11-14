import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import { ApiError } from '@/lib/api/client'

const getInsiderActivity = vi.fn()
vi.mock('@/features/insiders/api/insiders-api', () => ({
  getInsiderActivity: (...args: unknown[]) => getInsiderActivity(...args),
}))
// The reader, as the company page reads it (/me through getCurrentUserSafe, null when signed out).
const getCurrentUserSafe = vi.fn()
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: (...args: unknown[]) => getCurrentUserSafe(...args),
}))

import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'

const user = (over: Partial<CurrentUser> = {}): CurrentUser => ({
  id: 1, email: 'reader@example.test', full_name: null, is_pro: false, is_beta: true, is_admin: false, email_verified: true, ...over,
})
const BETA = user()

function newClient(queries: Record<string, unknown> = { retry: false }) {
  return new QueryClient({ defaultOptions: { queries } })
}

// isFpi defaults to false ("known domestic") so the read is enabled — the panel only queries
// once the parent knows the company is not a foreign private issuer (isFpi === false).
function renderPanel(ticker = 'AAPL', isFpi: boolean | undefined = false, qc = newClient()) {
  return render(
    <QueryClientProvider client={qc}>
      <InsiderActivityPanel ticker={ticker} isFpi={isFpi} />
    </QueryClientProvider>,
  )
}

/** Let the reader's read and anything it enables settle (several turns of the event loop). */
const settle = () => act(async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0)) })

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

const COMPLETE = {
  status: 'complete' as 'complete' | 'scanning' | 'paused' | 'failed',
  filings_listed: 60,
  filings_read: 60,
  oldest_filed_date: '2024-03-02' as string | null,
  refreshed_at: '2024-05-03T10:00:00Z' as string | null,
  retry_after_seconds: null as number | null,
}

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
  scan: COMPLETE,
}

const NO_TRADES = { transactions: [], total_transactions: 0 }
/** A response whose scan says `scan` over COMPLETE's fields, with RESP's trades unless `trades` is false. */
const answer = (scan: Partial<typeof COMPLETE>, trades = true) => ({ ...RESP, ...(trades ? {} : NO_TRADES), scan: { ...COMPLETE, ...scan } })

describe('InsiderActivityPanel', () => {
  beforeEach(() => {
    getInsiderActivity.mockReset()
    getCurrentUserSafe.mockReset()
    getCurrentUserSafe.mockResolvedValue(BETA)
  })

  it('renders the net-buying signal and a transactions row', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()

    expect(await screen.findByText(/Net insider buying/)).toBeInTheDocument()
    expect(screen.getByText('Insider activity')).toBeInTheDocument()
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
  // E89: a figure never breaks inside itself ("$900.0" over "K" at 320px under 200% text); a stacked tile holds it.
  it('lays the buy, sell and net tiles in equal tracks with a rem minimum, figures in the data face, whole', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()
    const row = (await screen.findByText(/^Buys \(2\)$/)).parentElement!.parentElement!
    expect(row).toHaveClass('grid', 'grid-cols-[repeat(auto-fit,minmax(min(5.5rem,100%),1fr))]')
    expect(row.className).not.toMatch(/\bflex\b|flex-wrap|grid-cols-3/)
    expect(row.children).toHaveLength(3)
    for (const tile of Array.from(row.children)) {
      expect(tile).toHaveClass('min-w-0')
      expect(tile.className).not.toMatch(/flex-auto|flex-1/)
      expect(tile.lastElementChild).toHaveClass('font-data', 'tabular-nums')
      expect(tile.lastElementChild!.className).not.toMatch(/break-(?:words|all)|overflow-wrap|word-break/)
    }
  })

  // E89 (chief design's approach, #1381's thread): at 320 to 390px under 200% text the panel broke four ways, so the
  // card takes E120's capped inset, the window control spans the card below 40rem and wraps whole segments rather than
  // running past it, the signal row wraps as a Notice's does, and each separator dot is held to the word before it.
  it('takes the capped inset and spans the time window across the card below 40rem', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    renderPanel()
    expect((await screen.findByText('Insider activity')).closest('section')).toHaveClass('p-cap-6')
    const group = screen.getByRole('group', { name: 'Time window' })
    expect(group).toHaveClass('w-full', 'flex-wrap', '[@media(min-width:40rem)]:w-auto')
    for (const segment of within(group).getAllByRole('button')) expect(segment).toHaveClass('flex-1')
  })

  it('wraps the signal row as a Notice does, its text column under the glyph when it cannot keep 9rem beside it', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      summary: { ...RESP.summary, plan_10b5_1_sell_shares: 50000, discretionary_net_shares: 12000 },
    })
    renderPanel()
    const headline = await screen.findByText(/Net insider buying/)
    const column = headline.parentElement!
    expect(column).toHaveClass('min-w-0', 'flex-[1_1_9rem]')
    expect(column.parentElement).toHaveClass('flex', 'flex-wrap')
    expect(column.parentElement!.firstElementChild).toHaveClass('shrink-0')
  })

  it('holds each separator dot to the word before it with a no-break space, so no line starts with a dot', async () => {
    getInsiderActivity.mockResolvedValue({
      ...RESP,
      summary: { ...RESP.summary, plan_10b5_1_sell_shares: 50000, discretionary_net_shares: 12000 },
    })
    renderPanel()
    const dots = [await screen.findByText(/Net insider buying/), screen.getByText(/pre-scheduled 10b5-1 plans/)]
    expect(dots[0].textContent).toBe('Net insider buying\u00a0· $1.8M')
    expect(dots[1].textContent).toBe('Excludes 50.0K shares sold under pre-scheduled 10b5-1 plans\u00a0· discretionary net +12.0K shares')
    for (const line of dots) expect(line.textContent).not.toMatch(/ ·/)
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

  it('says a complete scan found no trades in the window, and keeps the window control', async () => {
    getInsiderActivity.mockResolvedValue({ ...RESP, ...NO_TRADES })
    renderPanel()

    expect(await screen.findByText('No open-market insider trades in the last 90 days.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Time window' })).toBeInTheDocument()
  })

  it('shows the FPI note to a beta account and asks nothing for foreign private issuers', async () => {
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
    // read must not fire while FPI status is still unknown.
    render(
      <QueryClientProvider client={newClient()}>
        <InsiderActivityPanel ticker="AAPL" />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(getInsiderActivity).not.toHaveBeenCalled()
    // On its own page the card stands meanwhile, with its bones: the page is never blank under its lead.
    expect(screen.getByRole('heading', { name: 'Insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading insider activity' })).toBeInTheDocument()
  })

  it('shows every trade the answer carries, and says how many the window holds when it holds more', async () => {
    const many = Array.from({ length: 12 }, (_, i) => txn({ insider_name: `Insider ${i + 1}`, accession: `0000000000-24-0000${i + 10}` }))
    getInsiderActivity.mockResolvedValue({ ...RESP, transactions: many, total_transactions: 41 })
    renderPanel()

    expect(await screen.findByText('Insider 12')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(13)   // the header and all twelve, none held back
    expect(screen.getByText(/^The 12 most recent of 41 trades in this window\./)).toBeInTheDocument()
  })

  it('says nothing of a count when the answer carries every trade in the window', async () => {
    getInsiderActivity.mockResolvedValue({ ...RESP, total_transactions: RESP.transactions.length })
    renderPanel()

    await screen.findByText('Jane Doe')
    expect(screen.queryByText(/most recent of/)).not.toBeInTheDocument()
  })
})

// ADR 0009, decision 7: the endpoint answers only a beta account (401 signed out, 403 any other account), so the panel
// asks only once the page's read of /me says the reader is one, and otherwise renders nothing.
describe('InsiderActivityPanel: only a beta account asks', () => {
  beforeEach(() => {
    getInsiderActivity.mockReset()
    getCurrentUserSafe.mockReset()
    getInsiderActivity.mockResolvedValue(RESP)
  })

  it.each([
    ['signed out', null],
    ['signed in to an account that is not a beta account', user({ is_beta: false })],
  ])('%s: asks nothing and renders nothing', async (_, reader) => {
    getCurrentUserSafe.mockResolvedValue(reader)
    const { container } = renderPanel()
    await waitFor(() => expect(getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(getInsiderActivity).not.toHaveBeenCalled()
    expect(container).toBeEmptyDOMElement()
  })

  it('while the reader is still being read: asks nothing and renders nothing', async () => {
    getCurrentUserSafe.mockReturnValue(new Promise(() => {}))
    const { container } = renderPanel()
    await waitFor(() => expect(getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(getInsiderActivity).not.toHaveBeenCalled()
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the foreign private issuer note to a beta account only', async () => {
    getCurrentUserSafe.mockResolvedValue(user({ is_beta: false }))
    const { container } = renderPanel('BABA', true)
    await waitFor(() => expect(getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(container).toBeEmptyDOMElement()
    expect(getInsiderActivity).not.toHaveBeenCalled()
  })

  it('asks once the reader is known to be a beta account', async () => {
    getCurrentUserSafe.mockResolvedValue(BETA)
    renderPanel()
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalledWith('AAPL', 90))
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
  })
})

describe('InsiderActivityPanel: what the stored scan says', () => {
  beforeEach(() => {
    getInsiderActivity.mockReset()
    getCurrentUserSafe.mockReset()
    getCurrentUserSafe.mockResolvedValue(BETA)
  })

  /** The panel's status region: the one live region with no name of its own (the skeleton's is named). */
  const statusRegion = () => screen.getAllByRole('status').find((el) => !el.getAttribute('aria-label'))!

  it('shows the card with its bones while the first answer loads: its page is never blank', async () => {
    getInsiderActivity.mockReturnValue(new Promise(() => {}))
    renderPanel()
    await waitFor(() => expect(getInsiderActivity).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('heading', { name: 'Insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Time window' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading insider activity' })).toBeInTheDocument()
  })

  it('shows the skeleton in the card, under its heading and window control, while another window loads', async () => {
    getInsiderActivity.mockResolvedValueOnce(RESP).mockReturnValue(new Promise(() => {}))
    renderPanel()
    await screen.findByText('Jane Doe')
    fireEvent.click(screen.getByRole('button', { name: '180D' }))
    expect(await screen.findByRole('status', { name: 'Loading insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Time window' })).toBeInTheDocument()
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
  })

  it('a first visit (scanning, nothing listed yet) says the filings are being read, with no count and no empty-window line', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'scanning', filings_listed: 0, filings_read: 0, oldest_filed_date: null, retry_after_seconds: 10 }, false),
    )
    renderPanel()
    const line = await screen.findByText('Reading this company’s recent Form 4 filings.')
    expect(statusRegion()).toContainElement(line)
    expect(statusRegion()).toHaveTextContent(/^Reading this company’s recent Form 4 filings\.$/)
    expect(screen.queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading insider activity' })).not.toBeInTheDocument()
  })

  /** A run that reports how far it has got shows a bar (DESIGN_SYSTEM.md §4 › Activity line). The count is the
   *  bar's to say and sits outside the status region, which would otherwise read it out with every answer. */
  const expectProgress = (read: number, listed: number) => {
    const bar = screen.getByRole('progressbar', { name: 'Form 4 filings read' })
    expect(bar).toHaveAttribute('aria-valuenow', String(read))
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', String(listed))
    expect(bar.firstElementChild).toHaveStyle({ width: `${Math.round((read / listed) * 100)}%` })
    const count = screen.getByText(new RegExp(`^${read} of ${listed} filings read`))
    expect(statusRegion()).not.toContainElement(count)
    expect(statusRegion()).not.toContainElement(bar)
    expect(statusRegion()).not.toHaveTextContent(/\d+ of \d+/)
  }

  it('a first visit shows no bar: nothing is listed to count against', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'scanning', filings_listed: 0, filings_read: 0, oldest_filed_date: null, retry_after_seconds: 10 }, false),
    )
    renderPanel()
    await screen.findByText('Reading this company’s recent Form 4 filings.')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.queryByText(/filings read/)).not.toBeInTheDocument()
  })

  it('scanning with nothing stored in the window: the words, and a bar that counts the filings read', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'scanning', filings_listed: 60, filings_read: 3, oldest_filed_date: '2024-04-20', retry_after_seconds: 10 }, false),
    )
    renderPanel()
    const line = await screen.findByText('Reading this company’s recent Form 4 filings.')
    expect(statusRegion()).toContainElement(line)
    expectProgress(3, 60)
    expect(screen.queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
  })

  it('scanning with trades stored: the trades, how far back they reach, and the bar', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'scanning', filings_listed: 60, filings_read: 12, oldest_filed_date: '2024-03-02', retry_after_seconds: 10 }),
    )
    renderPanel()
    const line = await screen.findByText('Reading this company’s recent Form 4 filings.')
    expect(statusRegion()).toContainElement(line)
    expect(statusRegion()).toHaveTextContent(/^Reading this company’s recent Form 4 filings\.$/)
    expect(screen.getByRole('progressbar', { name: 'Form 4 filings read' })).toHaveAttribute('aria-valuenow', '12')
    // How far back the scan has read, beside the count and outside the status region: it moves with every answer.
    expect(screen.getByText('12 of 60 filings read, back to Mar 2, 2024')).toBeInTheDocument()
    expect(screen.getByText(/Net insider buying/)).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.queryByText(/paused/)).not.toBeInTheDocument()
  })

  it('paused with trades stored: the trades, how far back they reach, and that reading resumes on its own', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'paused', filings_listed: 60, filings_read: 12, oldest_filed_date: '2024-03-02', retry_after_seconds: 300 }),
    )
    renderPanel()
    const line = await screen.findByText('Reading this company’s Form 4 filings is paused and resumes on its own.')
    expect(statusRegion()).toContainElement(line)
    expect(screen.getByText('12 of 60 filings read, back to Mar 2, 2024')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Form 4 filings read' })).toHaveAttribute('aria-valuenow', '12')
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
  })

  it('paused with nothing stored in the window: that reading is paused, and the bar where it stopped', async () => {
    getInsiderActivity.mockResolvedValue(
      answer({ status: 'paused', filings_listed: 60, filings_read: 3, oldest_filed_date: '2024-04-20', retry_after_seconds: 300 }, false),
    )
    renderPanel()
    expect(await screen.findByText('Reading this company’s Form 4 filings is paused and resumes on its own.')).toBeInTheDocument()
    expectProgress(3, 60)
    expect(screen.queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
  })

  it.each(['failed', 'complete'] as const)('a %s scan shows no bar', async (status) => {
    getInsiderActivity.mockResolvedValue(answer({ status, filings_listed: 60, filings_read: 60, retry_after_seconds: null }))
    renderPanel()
    await screen.findByText('Jane Doe')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('failed with nothing stored: a plain line that it is unavailable, and no empty-window line', async () => {
    getInsiderActivity.mockResolvedValue(answer({ status: 'failed', filings_listed: 0, filings_read: 0, oldest_filed_date: null }, false))
    renderPanel()
    const line = await screen.findByText('Insider activity is unavailable for this company right now.')
    expect(statusRegion()).toContainElement(line)
    expect(screen.queryByText(/No open-market insider trades/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('failed with trades stored: still shows them, under the line', async () => {
    getInsiderActivity.mockResolvedValue(answer({ status: 'failed', filings_listed: 60, filings_read: 20 }))
    renderPanel()
    expect(await screen.findByText('Insider activity is unavailable for this company right now.')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
  })

  it('complete: no status line, even when a refresh under way asks to be asked again', async () => {
    getInsiderActivity.mockResolvedValue(answer({ status: 'complete', retry_after_seconds: 3600 }))
    renderPanel()
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(statusRegion()).toBeEmptyDOMElement()
  })
})

describe('InsiderActivityPanel: a request that fails', () => {
  beforeEach(() => {
    getInsiderActivity.mockReset()
    getCurrentUserSafe.mockReset()
    getCurrentUserSafe.mockResolvedValue(BETA)
  })

  // The client here would retry three times at once: only the panel's own `retry: false` stops it.
  const retryingClient = () => newClient({ retry: 3, retryDelay: 0 })

  it.each([
    ['a server error', new ApiError(500, 'Internal Server Error')],
    ['the rate limit', new ApiError(429, 'Too Many Requests')],
    ['a dropped connection', new ApiError(0, 'Network Error')],
  ])('%s: an inline error whose Try again asks again, and no retry of its own', async (_, error) => {
    getInsiderActivity.mockRejectedValueOnce(error).mockResolvedValue(RESP)
    renderPanel('AAPL', false, retryingClient())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Couldn’t load insider activity')
    await settle()
    expect(getInsiderActivity).toHaveBeenCalledTimes(1)

    await userEvent.setup().click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(getInsiderActivity).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it.each([401, 403, 404])('a %i (a refusal: the endpoint off, or a company it does not know) is a plain line, not an error', async (status) => {
    getInsiderActivity.mockRejectedValue(new ApiError(status, 'Refused'))
    renderPanel('AAPL', false, retryingClient())
    expect(await screen.findByText('Insider activity isn’t available here right now.')).toBeInTheDocument()
    await settle()
    expect(getInsiderActivity).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading insider activity' })).not.toBeInTheDocument()
  })
})

describe('InsiderActivityPanel: asking again while a scan is under way', () => {
  const T0 = new Date('2026-11-14T12:00:00Z').getTime()
  /** Each request: when it was sent, from the start, and for which window. */
  let calls: { at: number; window: number }[]

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
    vi.setSystemTime(T0)
    calls = []
    getInsiderActivity.mockReset()
    getCurrentUserSafe.mockReset()
    getCurrentUserSafe.mockResolvedValue(BETA)
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  /** Answer each request with the next of `answers`, the last one for good. */
  const answering = (...answers: unknown[]) =>
    getInsiderActivity.mockImplementation(async (_ticker: string, window: number) => {
      calls.push({ at: Date.now() - T0, window })
      return answers[Math.min(calls.length - 1, answers.length - 1)]
    })
  const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
  /** Render, and let the reader's read, the first request and its answer land. */
  const start = async () => {
    renderPanel()
    await advance(0)
    await advance(0)
  }
  const scanning = (retryAfter: number) =>
    answer({ status: 'scanning', filings_listed: 60, filings_read: 12, retry_after_seconds: retryAfter })

  it('a later read the endpoint refuses takes the stored trades off the page: the line stands alone, with no bar', async () => {
    getInsiderActivity.mockResolvedValueOnce(scanning(10)).mockRejectedValue(new ApiError(404, 'Not Found'))
    await start()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    await advance(10_001)
    await advance(0)
    expect(screen.getByText('Insider activity isn’t available here right now.')).toBeInTheDocument()
    expect(screen.queryByText('Jane Doe')).toBeNull()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.queryByText(/Reading this company/)).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('asks again after the interval the response gives, and stops once nothing is pending', async () => {
    answering(scanning(10), scanning(10), answer({ status: 'complete', retry_after_seconds: null }))
    await start()
    expect(calls.map((c) => c.at)).toEqual([0])
    await advance(9_999)
    expect(calls).toHaveLength(1)
    await advance(1)
    expect(calls.map((c) => c.at)).toEqual([0, 10_000])
    await advance(10_000)
    expect(calls.map((c) => c.at)).toEqual([0, 10_000, 20_000])
    await advance(5 * 60_000)
    expect(calls).toHaveLength(3)
    expect(screen.queryByText(/filings read/)).not.toBeInTheDocument()
  })

  it('never asks sooner than every 5 seconds', async () => {
    answering(scanning(1))
    await start()
    await advance(4_999)
    expect(calls).toHaveLength(1)
    await advance(1)
    expect(calls.map((c) => c.at)).toEqual([0, 5_000])
  })

  it('stops asking 3 minutes after its first request', async () => {
    answering(scanning(10))
    await start()
    await advance(10 * 60_000)
    const times = calls.map((c) => c.at)
    expect(Math.max(...times)).toBe(180_000)
    expect(times).toHaveLength(19) // the first request, then one every 10 s up to 3 minutes
    // The data the scan had stays on screen.
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
  })

  it('a reader who comes back to a scan still under way is asked for again, though the cached answer is fresh', async () => {
    // Back from a filing within the answer's five minutes: the panel mounts over a cached "scanning" answer, so no
    // request is due on mount. The polling must still run, or the words and the bar would stand still for good.
    const client = newClient()
    answering(scanning(10))
    const first = renderPanel('AAPL', false, client)
    await advance(0)
    await advance(0)
    expect(calls).toHaveLength(1)
    first.unmount()
    await advance(60_000)
    expect(calls).toHaveLength(1) // nothing asks while no panel is mounted

    renderPanel('AAPL', false, client)
    await advance(0)
    expect(screen.getByRole('progressbar', { name: 'Form 4 filings read' })).toBeInTheDocument() // the cached answer
    expect(calls).toHaveLength(1)
    await advance(10_000)
    expect(calls).toHaveLength(2)
    // And this mount's three minutes end like any other's.
    await advance(10 * 60_000)
    expect(Math.max(...calls.map((c) => c.at))).toBeLessThanOrEqual(60_000 + 180_000)
    expect(screen.getByText(/^Reading continues in the background\. Reload the page to see more\./)).toBeInTheDocument()
  })

  it('announces nothing new while the scan only gets further: the status words stay the same from answer to answer', async () => {
    const progress = (read: number, oldest: string) =>
      answer({ status: 'scanning', filings_listed: 60, filings_read: read, oldest_filed_date: oldest, retry_after_seconds: 10 })
    answering(progress(8, '2024-04-20'), progress(16, '2024-03-02'), progress(24, '2024-01-15'))
    await start()
    const region = () => screen.getAllByRole('status').find((el) => !el.getAttribute('aria-label'))!
    const words = region().textContent
    expect(screen.getByText('8 of 60 filings read, back to Apr 20, 2024')).toBeInTheDocument()
    await advance(10_000)
    await advance(1) // the answer lands, and React Query's batched notice of it renders
    await advance(1)
    expect(screen.getByText('16 of 60 filings read, back to Mar 2, 2024')).toBeInTheDocument()
    expect(region().textContent).toBe(words)
    await advance(10_000)
    await advance(1)
    await advance(1)
    expect(screen.getByText('24 of 60 filings read, back to Jan 15, 2024')).toBeInTheDocument()
    expect(region().textContent).toBe(words)
    expect(words?.replace(/\u00a0/g, ' ')).toBe('Reading this company’s recent Form 4 filings.')
  })

  it('once it has stopped asking, a first visit that never listed a filing says so too, in place of the pulsing line', async () => {
    answering(answer({ status: 'scanning', filings_listed: 0, filings_read: 0, oldest_filed_date: null, retry_after_seconds: 10 }, false))
    await start()
    expect(screen.getByText('Reading this company’s recent Form 4 filings.')).toBeInTheDocument()
    await advance(180_000)
    expect(screen.getByText('Reading continues in the background. Reload the page to see more.')).toBeInTheDocument()
    expect(screen.queryByText('Reading this company’s recent Form 4 filings.')).not.toBeInTheDocument()
  })

  it('once it has stopped asking, a paused scan says to come back later', async () => {
    answering(answer({ status: 'paused', filings_listed: 60, filings_read: 12, retry_after_seconds: 170 }))
    await start()
    expect(screen.getByText('Reading this company’s Form 4 filings is paused and resumes on its own.')).toBeInTheDocument()
    await advance(180_000)
    expect(
      screen.getByText('Reading this company’s Form 4 filings is paused and resumes on its own. Reload the page later to see more.'),
    ).toBeInTheDocument()
  })

  it('says so once it has stopped asking, and how to see more, in place of words that would stand still', async () => {
    answering(scanning(10))
    await start()
    await advance(179_999)
    expect(screen.getByText(/^Reading this company’s recent Form 4 filings\./)).toBeInTheDocument()
    expect(screen.queryByText(/Reload the page/)).not.toBeInTheDocument()
    await advance(1)
    expect(screen.getByText(/^Reading continues in the background\. Reload the page to see more\./)).toBeInTheDocument()
    expect(screen.queryByText(/^Reading this company’s recent Form 4 filings\./)).not.toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Form 4 filings read' })).toHaveAttribute('aria-valuenow', '12')
  })

  it('a scan that completes inside the three minutes never says it stopped', async () => {
    answering(scanning(10), answer({ status: 'complete', retry_after_seconds: null }))
    await start()
    await advance(10 * 60_000)
    expect(screen.queryByText(/Reload the page/)).not.toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('a change of window does not start the 3 minutes again', async () => {
    answering(scanning(10))
    await start()
    await advance(120_000)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '1Y' })) })
    await advance(10 * 60_000)
    const year = calls.filter((c) => c.window === 365).map((c) => c.at)
    expect(year[0]).toBe(120_000)
    expect(year.length).toBeGreaterThan(1) // the new window is asked again too
    expect(Math.max(...year)).toBeLessThanOrEqual(180_000)
  })

  it('keeps showing complete data as complete while a refresh behind it asks to be asked again', async () => {
    answering(answer({ status: 'complete', retry_after_seconds: 60 }), answer({ status: 'complete', retry_after_seconds: null }))
    await start()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.queryByText(/filings read|Reading/)).not.toBeInTheDocument()
    await advance(60_000)
    expect(calls.map((c) => c.at)).toEqual([0, 60_000])
    await advance(5 * 60_000)
    expect(calls).toHaveLength(2)
  })

  it('asks nothing more after a request fails, and keeps the stored trades beside the error', async () => {
    getInsiderActivity.mockImplementation(async (_ticker: string, window: number) => {
      calls.push({ at: Date.now() - T0, window })
      if (calls.length === 2) throw new ApiError(503, 'Service Unavailable')
      return scanning(10)
    })
    await start()
    await advance(10_000)
    // A failure takes a few more turns to render than an answer (the failure hold's own render among them).
    for (let i = 0; i < 5; i++) await advance(1)
    expect(calls).toHaveLength(2)
    expect(screen.getByRole('alert')).toHaveTextContent('Couldn’t load insider activity')
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    await advance(5 * 60_000)
    expect(calls).toHaveLength(2)
  })
})

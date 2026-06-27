import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

    expect(await screen.findByText('Insider Activity')).toBeInTheDocument()
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

  it('refetches with a new window when the window is changed', async () => {
    getInsiderActivity.mockResolvedValue(RESP)
    const user = userEvent.setup()
    renderPanel('AAPL')

    await screen.findByText('Insider Activity')
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

    await waitFor(() => expect(screen.queryByText('Insider Activity')).not.toBeInTheDocument())
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
    expect(screen.queryByText('Insider Activity')).not.toBeInTheDocument()
  })
})

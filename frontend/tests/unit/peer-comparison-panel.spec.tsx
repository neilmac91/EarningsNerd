import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// recharts measures the DOM, which jsdom can't — stub it for deterministic rendering.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}))

const getPeers = vi.fn()
vi.mock('@/features/peers/api/peers-api', () => ({
  getPeers: (...args: unknown[]) => getPeers(...args),
}))

import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'

function renderPanel(ticker = 'AAPL') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PeerComparisonPanel ticker={ticker} />
    </QueryClientProvider>,
  )
}

const peer = (ticker: string, value: number, is_subject = false, rank = 1, percentile = 50) => ({
  ticker,
  company_name: `${ticker} Inc.`,
  value,
  period_end: '2023-12-31',
  fiscal_year: 2023,
  is_subject,
  rank,
  percentile,
})

const RESP = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  sic: '3571',
  concept: 'revenue',
  unit: 'USD',
  peer_count: 3,
  subject: peer('AAPL', 100, true, 3, 0),
  peers: [peer('BIGCO', 300, false, 1, 100), peer('MIDCO', 200, false, 2, 50), peer('AAPL', 100, true, 3, 0)],
}

describe('PeerComparisonPanel', () => {
  beforeEach(() => getPeers.mockReset())

  it('renders the rank headline and chart when there are peers', async () => {
    getPeers.mockResolvedValue(RESP)
    renderPanel()

    expect(await screen.findByText('Sector Peers')).toBeInTheDocument()
    expect(screen.getByText(/#3/)).toBeInTheDocument()
    expect(screen.getByText(/of 3 on Revenue/)).toBeInTheDocument()
    expect(screen.getByTestId('peers-chart')).toBeInTheDocument()
  })

  it('renders nothing when there are no meaningful peers', async () => {
    getPeers.mockResolvedValue({
      ...RESP,
      peer_count: 1,
      peers: [peer('AAPL', 100, true, 1, 100)],
    })
    renderPanel()

    await waitFor(() => expect(screen.queryByText('Sector Peers')).not.toBeInTheDocument())
  })
})

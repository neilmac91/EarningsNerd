import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

const peer = (
  ticker: string,
  value: number,
  is_subject = false,
  rank = 1,
  percentile = 50,
  reconciled = true,
) => ({
  ticker,
  company_name: `${ticker} Inc.`,
  value,
  period_end: '2023-12-31',
  fiscal_year: 2023,
  is_subject,
  rank,
  percentile,
  reconciled,
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

    expect(await screen.findByText('Sector peers')).toBeInTheDocument()
    expect(screen.getByText(/#3/)).toBeInTheDocument()
    expect(screen.getByText(/of 3 on Revenue/)).toBeInTheDocument()
    // The percentile reads as an ordinal (CO-13): 0 is "0th", and 1, 2, 3 and 21 take st, nd, rd, st.
    expect(screen.getByText(/of 3 on Revenue/)).toHaveTextContent('· 0th percentile')
    expect(screen.getByTestId('peers-chart')).toBeInTheDocument()
    // Clean data → no honesty badge.
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it('reads a percentile as an English ordinal', async () => {
    getPeers.mockResolvedValue({ ...RESP, subject: peer('AAPL', 100, true, 3, 21.4) })
    renderPanel()
    expect(await screen.findByText(/of 3 on Revenue/)).toHaveTextContent('· 21st percentile')
  })

  it('picks the metric through the SegmentedControl (CO-15): a named group of pressed buttons', async () => {
    getPeers.mockResolvedValue(RESP)
    renderPanel()
    const group = await screen.findByRole('group', { name: 'Metric' })
    expect(group.className).toContain('flex-wrap')
    expect(screen.getByRole('button', { name: 'Revenue' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Net Income' }))
    await waitFor(() => expect(getPeers).toHaveBeenCalledWith('AAPL', 'net_income'))
    expect(screen.getByRole('button', { name: 'Net Income' }).className).toContain('focus-visible:shadow-ring-brand')
  })

  it('shows a source check when a shown value is flagged', async () => {
    getPeers.mockResolvedValue({
      ...RESP,
      peers: [
        peer('BIGCO', 300, false, 1, 100),
        peer('MIDCO', 200, false, 2, 50, false), // flagged
        peer('AAPL', 100, true, 3, 0),
      ],
    })
    renderPanel()

    expect(await screen.findByText('Source check needed')).toBeInTheDocument()
  })

  it('keeps the reason for a withheld subject figure available without ranking it', async () => {
    const subject = { ...peer('AAPL', 100, true), value: null, rank: null, percentile: null, provenance: { version: 1, method: 'unknown', validation: 'unavailable', reasons: ['unsupported_eps_calculation'], formula: null, inputs: [], calculation_version: 'quarterly-v2' } }
    getPeers.mockResolvedValue({ ...RESP, subject, peers: [RESP.peers[0], RESP.peers[1], subject] })
    renderPanel()
    expect(await screen.findByText(/AAPL: unavailable\./)).toHaveTextContent('Use a reported quarterly EPS figure')
    expect(screen.queryByText(/Ranks/)).not.toBeInTheDocument()
  })

  it('renders nothing when there are no meaningful peers', async () => {
    getPeers.mockResolvedValue({
      ...RESP,
      peer_count: 1,
      peers: [peer('AAPL', 100, true, 1, 100)],
    })
    renderPanel()

    await waitFor(() => expect(screen.queryByText('Sector peers')).not.toBeInTheDocument())
  })
})

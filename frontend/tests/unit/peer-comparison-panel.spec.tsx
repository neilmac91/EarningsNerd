import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// recharts measures the DOM, which jsdom can't — stub it for deterministic rendering.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: ({ fill, fillOpacity }: { fill?: string; fillOpacity?: number }) => (
    <div data-testid="peer-bar" data-fill={fill} data-opacity={fillOpacity} />
  ),
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}))

const getPeers = vi.fn()
vi.mock('@/features/peers/api/peers-api', () => ({
  getPeers: (...args: unknown[]) => getPeers(...args),
}))

import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'
import { ThemeContext } from '@/components/ThemeProvider'
import { chartTheme, seriesColor } from '@/components/ui'

/** Without a theme the panel renders provider-less, as SSR does, and takes the light fallback. */
function renderPanel(ticker = 'AAPL', theme?: 'light' | 'dark') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const panel = (
    <QueryClientProvider client={qc}>
      <PeerComparisonPanel ticker={ticker} />
    </QueryClientProvider>
  )
  return render(theme ? <ThemeContext.Provider value={{ theme, toggleTheme: () => {} }}>{panel}</ThemeContext.Provider> : panel)
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

  it.each([['light', false], ['dark', true]] as const)(
    'draws the subject in the first series colour, in %s’s half, and the peers in the flat grey',
    async (theme, dark) => {
      getPeers.mockResolvedValue(RESP)
      renderPanel('AAPL', theme)
      await screen.findByTestId('peers-chart')
      const bars = screen.getAllByTestId('peer-bar').map((bar) => [bar.dataset.fill, bar.dataset.opacity])
      // RESP ranks BIGCO, MIDCO and the subject, AAPL, in that order.
      const grey = [chartTheme(dark).flat, '0.45']
      expect(bars).toEqual([grey, grey, [seriesColor(0, dark), '1']])
    },
  )

  it('reads a percentile as an English ordinal', async () => {
    getPeers.mockResolvedValue({ ...RESP, subject: peer('AAPL', 100, true, 3, 21.4) })
    renderPanel()
    expect(await screen.findByText(/of 3 on Revenue/)).toHaveTextContent('· 21st percentile')
  })

  it('picks the metric through a compact select beside its "Metric" label (CO-15), its options in sentence case', async () => {
    getPeers.mockResolvedValue(RESP)
    renderPanel()
    const picker = await screen.findByRole('combobox', { name: 'Metric' })
    expect(picker.tagName).toBe('SELECT')
    expect(picker.closest('label')).toHaveTextContent(/^Metric/)
    // inputClasses({ select: true, autoWidth: true }): sized to its content, capped at its container,
    // with the field's brand focus ring; nine metrics are never a row of pressed segments.
    expect(picker.className).toContain('max-w-full')
    expect(picker.className).not.toMatch(/(^| )w-full( |$)/)
    expect(picker.className).toContain('focus:shadow-ring-brand')
    expect(screen.queryByRole('group', { name: 'Metric' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Revenue' })).toBeNull()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Revenue', 'Net income', 'Gross profit', 'Operating income', 'Net margin', 'Operating margin',
      'Gross margin', 'Diluted EPS', 'Total assets',
    ])
    expect(picker).toHaveValue('revenue')
    fireEvent.change(picker, { target: { value: 'net_income' } })
    await waitFor(() => expect(getPeers).toHaveBeenCalledWith('AAPL', 'net_income'))
    expect(picker).toHaveValue('net_income')
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

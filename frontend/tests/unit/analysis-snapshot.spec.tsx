import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'
import { queryKeys } from '@/lib/queryKeys'
import api, { ApiError } from '@/lib/api/client'
import { exportAnalysisPdf, exportAnalysisXlsx, getAnalysisDataset, streamAnalysis, type AnalysisDataset } from '@/features/analysis/api/analysis-api'

vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }))
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: ({ onSelect }: { onSelect: (ticker: string) => void }) => <button onClick={() => onSelect('META')}>Select Meta</button> }))
vi.mock('@/lib/analytics', () => ({ default: { analysisRun: vi.fn() } }))
vi.mock('@/features/analysis/api/analysis-api', async (original) => ({ ...await original<typeof import('@/features/analysis/api/analysis-api')>(), getAnalysisDataset: vi.fn(), streamAnalysis: vi.fn() }))

const dataset: AnalysisDataset = {
  ticker: 'META', company_name: 'Meta', mode: 'annual', period_key: 'FY2022..FY2023',
  snapshot_id: 'd22f139cfa077417a5aa20d47e860fbf44e8bdd1f859590feb002d220db1b5d8', dataset_version: 'quarterly-v2',
  periods: [2022, 2023].map((year) => ({ key: `FY${year}`, fiscal_year: year, fiscal_period: 'FY', period_end: `${year}-12-31` })),
  series: [], inflections: [],
}

afterEach(() => vi.restoreAllMocks())

describe('analysis snapshot consistency', () => {
  it.each([false, true])('shows matching snapshot commentary and enables PDF export (cached=%s)', async (cached) => {
    vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async (_ticker, _range, handlers) => {
      handlers.onToken('Commentary still being checked')
      handlers.onComplete({ kind: 'analysis', analysis_id: 9, snapshot_id: dataset.snapshot_id, narrative: 'Commentary for the displayed source snapshot.', citations: [], grounded: 0, cached, n_periods: 2 })
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), { id: 7 })
    client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
    client.setQueryData(queryKeys.analysisCoverage('META'), { ticker: 'META', company_name: 'Meta', supported: true, annual: dataset.periods.map((period) => ({ ...period, has_core: true })), quarterly: [], limits: { annual: 10, quarterly: 12 } })
    render(<QueryClientProvider client={client}><AnalysisPageClient /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Select Meta' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Run analysis' }))
    expect(await screen.findByText('Commentary for the displayed source snapshot.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export PDF' })).toBeEnabled()
    expect(screen.queryByText(/Source data changed while this analysis was running/)).not.toBeInTheDocument()
    expect(screen.queryByText('Commentary still being checked')).not.toBeInTheDocument()
    // Downloads use responseType=blob, so a JSON 409 detail can be lost by axios. The status
    // must still explain that refreshing the displayed figures is required before export.
    const method = cached ? 'get' : 'post'
    vi.spyOn(api, method).mockRejectedValue(new ApiError(409, 'Request failed with status code 409'))
    fireEvent.click(screen.getByRole('button', { name: cached ? 'Export PDF' : 'Export Excel' }))
    expect(await screen.findByText('Source data changed. Run analysis again before exporting.')).toBeInTheDocument()
  })

  it.each(['changed-snapshot', undefined])('withholds commentary when the completed snapshot is %s', async (snapshot) => {
    vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async (_ticker, _range, handlers) => {
      handlers.onToken('Premature commentary')
      handlers.onComplete({ kind: 'analysis', analysis_id: 9, snapshot_id: snapshot, narrative: 'Mismatched commentary', citations: [], grounded: 0, cached: true, n_periods: 2 })
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), { id: 7 })
    client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
    client.setQueryData(queryKeys.analysisCoverage('META'), { ticker: 'META', company_name: 'Meta', supported: true, annual: dataset.periods.map((period) => ({ ...period, has_core: true })), quarterly: [], limits: { annual: 10, quarterly: 12 } })
    render(<QueryClientProvider client={client}><AnalysisPageClient /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Select Meta' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Run analysis' }))
    expect(await screen.findByText(/Source data changed while this analysis was running/)).toBeInTheDocument()
    expect(screen.queryByText('Premature commentary')).not.toBeInTheDocument()
    expect(screen.queryByText('Mismatched commentary')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Export PDF' })).not.toBeInTheDocument()
  })

  it('sends the displayed snapshot to both export formats', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: new Blob() })
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: new Blob() })
    await exportAnalysisPdf(9, 'shown-snapshot')
    await exportAnalysisXlsx('META', { mode: 'annual', start_period: 'FY2022', end_period: 'FY2023', snapshot_id: 'shown-snapshot' })
    expect(get).toHaveBeenCalledWith('/api/analysis/export/9/pdf', { responseType: 'blob', params: { snapshot_id: 'shown-snapshot' } })
    expect(post).toHaveBeenCalledWith('/api/analysis/META/export/xlsx', expect.objectContaining({ snapshot_id: 'shown-snapshot' }), { responseType: 'blob' })
  })
})

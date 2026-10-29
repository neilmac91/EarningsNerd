import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/api/client'
import { getAnalysisDataset, streamAnalysis, type AnalysisCompletion, type AnalysisDataset, type AnalysisStreamHandlers } from '@/features/analysis/api/analysis-api'

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

const completion = (cached: boolean): AnalysisCompletion => ({
  kind: 'analysis', analysis_id: 9, snapshot_id: dataset.snapshot_id, narrative: 'Revenue grew.', citations: [], grounded: 0, cached, n_periods: 2,
})

/** The page for a Pro reader with Meta picked: returns Run analysis once the picker shows it. */
async function mountPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  client.setQueryData(queryKeys.currentUser(), { id: 7 })
  client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
  client.setQueryData(queryKeys.analysisCoverage('META'), {
    ticker: 'META', company_name: 'Meta', supported: true,
    annual: dataset.periods.map((period) => ({ ...period, has_core: true })),
    quarterly: [{ key: 'Q1-2023', fiscal_year: 2023, fiscal_period: 'Q1', period_end: '2023-03-31', derived: false }],
    limits: { annual: 10, quarterly: 12 },
  })
  render(<QueryClientProvider client={client}><AnalysisPageClient /></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Select Meta' }))
  return screen.findByRole('button', { name: 'Run analysis' })
}

/** The status line is the element right after Run analysis. */
const lineBeside = (run: HTMLElement) => run.nextElementSibling as HTMLElement

const twoFrames = () => act(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))

afterEach(() => vi.restoreAllMocks())

describe("the trend analysis's status line", () => {
  it('says what the run is doing in a status line beside Run analysis, there before any run', async () => {
    const requests: AnalysisStreamHandlers[] = []
    vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async (_ticker, _range, handlers) => { requests.push(handlers) })
    const run = await mountPage()
    // Before any run the line is there, sr-only and empty.
    const line = lineBeside(run)
    expect(line).toHaveAttribute('role', 'status')
    expect(line).toHaveClass('sr-only')
    expect(line).toBeEmptyDOMElement()
    // Every change to the line, in order: what a screen reader is given.
    const said: string[] = []
    const observer = new MutationObserver(() => said.push(line.textContent ?? ''))
    observer.observe(line, { childList: true, characterData: true, subtree: true })

    // Run analysis: the first stage's words a frame after the press, then the stream's turn. The stream's own
    // "assembling" and a retry's "verifying" repeat the words the line holds, so nothing changes for them.
    fireEvent.click(run)
    await waitFor(() => expect(requests).toHaveLength(1))
    await waitFor(() => expect(line).toHaveTextContent('Assembling the numbers…'))
    for (const stage of ['assembling', 'writing', 'verifying']) await act(async () => requests[0].onProgress?.(stage))
    await act(async () => requests[0].onComplete(completion(false)))

    // Refresh analysis empties the line first, so the same words are heard again; a cached run has no writing stage.
    fireEvent.click(screen.getByRole('button', { name: 'Refresh analysis' }))
    await waitFor(() => expect(requests).toHaveLength(2))
    await waitFor(() => expect(line).toHaveTextContent('Assembling the numbers…'))
    await act(async () => requests[1].onComplete(completion(true)))

    // Run analysis again, and an error: the line empties, and the card's alert says what went wrong.
    fireEvent.click(run)
    await waitFor(() => expect(requests).toHaveLength(3))
    await waitFor(() => expect(line).toHaveTextContent('Assembling the numbers…'))
    await act(async () => requests[2].onError('The analysis could not be written.'))
    await waitFor(() => expect(said).toEqual([
      'Assembling the numbers…', 'Writing…', 'Analysis ready.',
      '', 'Assembling the numbers…', 'Analysis ready.',
      '', 'Assembling the numbers…', '',
    ]))
    observer.disconnect()
    expect(screen.getByRole('alert')).toHaveTextContent('The analysis could not be written.')
  })

  it('empties its status line on a reset and when the figures cannot be built', async () => {
    const requests: AnalysisStreamHandlers[] = []
    vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async (_ticker, _range, handlers) => { requests.push(handlers) })
    const run = await mountPage()
    const line = lineBeside(run)

    // A change of mode mid-run resets the results, and the line with them; the run it left says nothing after.
    fireEvent.click(run)
    await waitFor(() => expect(requests).toHaveLength(1))
    await waitFor(() => expect(line).toHaveTextContent('Assembling the numbers…'))
    fireEvent.click(screen.getByRole('button', { name: 'Quarterly' }))
    expect(line).toBeEmptyDOMElement()
    await act(async () => requests[0].onProgress?.('writing'))
    await act(async () => requests[0].onComplete(completion(false)))
    expect(line).toBeEmptyDOMElement()

    // The figures fail to build: the page's alert says so, and the line says nothing over it.
    vi.mocked(getAnalysisDataset).mockRejectedValue(new ApiError(503, 'The figures could not be built.'))
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The figures could not be built.')
    await twoFrames()
    expect(lineBeside(screen.getByRole('button', { name: 'Run analysis' }))).toBeEmptyDOMElement()
  })

  it.each([
    ['a completion', 'Analysis ready.'],
    ['a completion with too little history', 'Not enough reported history in the selected range for a meaningful analysis.'],
    ['a completion over changed figures', ''],
    ['an error', ''],
    ['a failed dataset', ''],
    ['a reset', ''],
  ])('drops the first words still a frame away when %s comes first', async (ending, expected) => {
    if (ending === 'a failed dataset') vi.mocked(getAnalysisDataset).mockRejectedValue(new ApiError(503, 'The figures could not be built.'))
    else if (ending === 'a reset') vi.mocked(getAnalysisDataset).mockReturnValue(new Promise<AnalysisDataset>(() => {}))
    else vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async (_ticker, _range, handlers) => {
      if (ending === 'a completion') handlers.onComplete(completion(false))
      // Over the figures shown, so it ends the run (the server sends no snapshot with one today: tasks/todo.md E239).
      else if (ending === 'a completion with too little history') handlers.onComplete({ ...completion(false), kind: 'not_enough_data', analysis_id: null, narrative: '', n_periods: 1 })
      // The figures changed under the run: the card's alert says so, as for an error.
      else if (ending === 'a completion over changed figures') handlers.onComplete({ ...completion(false), snapshot_id: 'a-newer-snapshot' })
      else handlers.onError('The analysis could not be written.')
    })
    const run = await mountPage()
    // Pressed and ended in one task, so the frame that would say "Assembling the numbers…" has not run yet.
    await act(async () => {
      fireEvent.click(run)
      if (ending === 'a reset') fireEvent.click(screen.getByRole('button', { name: 'Quarterly' }))
    })
    await twoFrames()
    // An exact match: toHaveTextContent('') matches any text.
    expect(lineBeside(screen.getByRole('button', { name: 'Run analysis' })).textContent).toBe(expected)
  })
})

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

/**
 * TrendCharts loads the spec renderer as its own chunk while CHARTS_V2 is set (E192). A chunk can fail to load (a stale
 * client after a deploy, a dropped connection), and the grid's ChartErrorBoundary sits outside it, so the card area
 * says the charts could not be drawn rather than the route's error page replacing the analysis. Vitest resolves
 * next/dynamic to its pages-router loader, which hands the error to `loading`; the App Router's lazy loader throws it.
 * Both reach the boundary. Its own file: the failing module is mocked for every import here.
 */
vi.mock('@/features/analysis/components/TrendChartsV2', () => {
  throw new Error('Loading chunk failed')
})

import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const dataset = { ticker: 'TST', company_name: 'Test Co', mode: 'annual', period_key: 'FY2024..FY2024', periods: [], series: [], inflections: [] } as unknown as AnalysisDataset

describe('the spec renderer’s chunk', () => {
  let consoleError: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    // React logs what the boundary catches; keep the output quiet.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => consoleError.mockRestore())

  it('that fails to load leaves the grid’s fallback, not an error thrown past it', async () => {
    render(<TrendCharts dataset={dataset} />)
    expect(await screen.findByText('These charts could not be drawn.')).toBeInTheDocument()
  })
})

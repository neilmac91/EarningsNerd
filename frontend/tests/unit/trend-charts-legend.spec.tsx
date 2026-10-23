import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as analysis-teaser.spec.tsx).
// `chartFault.on` makes the ComposedChart stub throw, so the chart fallback case can fail a panel.
const chartFault = vi.hoisted(() => ({ on: false }))
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => {
    if (chartFault.on) throw new Error('chart failed to draw')
    return <div>{children}</div>
  },
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

// The PNG export does real canvas/DOM work — spy it so the wiring tests can assert the header it
// receives without rasterizing. exportFilename (used alongside it) stays real.
vi.mock('@/features/analysis/lib/chartExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/analysis/lib/chartExport')>()
  return { ...actual, exportPanelPng: vi.fn().mockResolvedValue(true) }
})
vi.mock('@/lib/analytics', () => ({ default: { exportGenerated: vi.fn() } }))

import TrendCharts from '@/features/analysis/components/TrendCharts'
import { exportPanelPng } from '@/features/analysis/lib/chartExport'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const dataset: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'annual',
  period_key: 'FY2023..FY2024',
  periods: [
    { key: 'FY2023', fiscal_year: 2023, fiscal_period: 'FY', period_end: '2023-12-31' },
    { key: 'FY2024', fiscal_year: 2024, fiscal_period: 'FY', period_end: '2024-12-31' },
  ],
  series: [
    {
      concept: 'revenue',
      label: 'Revenue',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: 'FY2023', value: 100, marker: 'F1' },
        { period: 'FY2024', value: 120, marker: 'F2', yoy: 0.2 },
      ],
    },
    {
      concept: 'gross_margin',
      label: 'Gross margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      points: [
        { period: 'FY2023', value: 70.0, marker: 'F3' },
        { period: 'FY2024', value: 68.0, marker: 'F4', yoy: -2.0 },
      ],
    },
    {
      concept: 'operating_margin',
      label: 'Operating margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      points: [
        { period: 'FY2023', value: 40.0, marker: 'F5' },
        { period: 'FY2024', value: 42.0, marker: 'F6', yoy: 2.0 },
      ],
    },
    {
      concept: 'long_term_debt',
      label: 'Long-term debt',
      unit: 'USD',
      percent: false,
      tone: 'inverted',
      cagr: null,
      points: [
        { period: 'FY2023', value: 40, marker: 'F7' },
        { period: 'FY2024', value: 35, marker: 'F8' },
      ],
    },
    {
      concept: 'shareholders_equity',
      label: "Shareholders' equity",
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: 'FY2023', value: 900, marker: 'F9' },
        { period: 'FY2024', value: 1000, marker: 'F10' },
      ],
    },
  ],
  inflections: [],
}

describe('TrendCharts legends', () => {
  it('flags plotted growth even when the visible raw values passed reconciliation', () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].reconciled = true
    flagged.series[0].points[1].yoy_reconciled = false
    render(<TrendCharts dataset={flagged} />)
    const reviewNotes = screen.getAllByRole('button', { name: /^Review data notes a(?:,|$)/ })
    expect(reviewNotes).toHaveLength(1)
    expect(reviewNotes[0].closest('section')).toHaveTextContent('Revenue & growth')
  })

  it('labels only panels with plotted flagged values and preserves the caveat in PNG exports', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].reconciled = false
    // An out-of-window flag must not contaminate another visible panel.
    flagged.series[1].points.push({ period: 'FY1999', value: 50, reconciled: false })
    const { rerender } = render(<TrendCharts dataset={flagged} exportEnabled />)
    expect(screen.getAllByRole('button', { name: /^Review data notes a(?:,|$)/ })).toHaveLength(1)
    const panel = screen.getByRole('heading', { name: 'Revenue & growth' }).closest('section')!
    expect(within(panel).getByRole('button', { name: 'Review data notes a, b' })).toBeInTheDocument()
    fireEvent.click(within(panel).getByRole('button', { name: 'Download chart as PNG' }))
    expect(exportPanelPng).toHaveBeenCalledWith(expect.anything(), expect.anything(), expect.objectContaining({
      header: expect.objectContaining({ title: 'Revenue & growth', notes: expect.arrayContaining([expect.stringContaining('Note a: A source check remains unresolved')]) }),
    }))
    rerender(<TrendCharts dataset={dataset} />)
    expect(within(panel).queryByRole('button', { name: 'Review data notes a, b' })).not.toBeInTheDocument()
  })

  it('shows a legend naming each line for a multi-series panel (Margins)', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.getByText('Margins')).toBeInTheDocument()
    expect(screen.getByText('Gross')).toBeInTheDocument()
    expect(screen.getByText('Operating')).toBeInTheDocument()
  })

  it.each([{ concept: 'revenue', label: 'Revenue' }, { concept: 'net_interest_income', label: 'Net interest income' }])('shows the growth-line legend entry for the $concept top-line panel', ({ concept, label }) => {
    const data = structuredClone(dataset)
    data.series[0].concept = concept
    data.series[0].label = label
    render(<TrendCharts dataset={data} />)
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: `${label} & growth` })).toBeInTheDocument()
    expect(screen.getByText('YoY growth')).toBeInTheDocument()
  })

  it('marks BOTH axes symmetrically in the balance-sheet legend (dual axis)', () => {
    render(<TrendCharts dataset={dataset} />)
    // Equity dwarfs debt → it moves to the right axis. Both sides are named explicitly ("(left)"
    // is the positive word-binding for the left series, since the left axis can't be color-bound).
    expect(screen.getByText('Equity (right)')).toBeInTheDocument()
    expect(screen.getByText('Long-term debt (left)')).toBeInTheDocument()
  })

  it('adds NO left/right suffix on a single-axis panel (Margins)', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.getByText('Gross')).toBeInTheDocument()
    expect(screen.queryByText('Gross (left)')).not.toBeInTheDocument()
    expect(screen.queryByText('Operating (left)')).not.toBeInTheDocument()
  })

  it('keeps a single axis (no "(right)" suffix) when only the right-axis series is present', () => {
    const equityOnly: AnalysisDataset = {
      ...dataset,
      series: dataset.series.filter((s) =>
        ['revenue', 'shareholders_equity'].includes(s.concept)
      ),
    }
    render(<TrendCharts dataset={equityOnly} />)
    expect(screen.queryByText('Equity (right)')).not.toBeInTheDocument()
  })
})

describe('TrendCharts panel controls', () => {
  it('expands a panel to full grid width and back', () => {
    render(<TrendCharts dataset={dataset} />)
    const expand = screen.getAllByRole('button', { name: 'Expand chart' })[0]
    expect(expand).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(expand)
    expect(screen.getAllByRole('button', { name: 'Collapse chart' })[0]).toHaveAttribute(
      'aria-expanded',
      'true'
    )
    // The expanded panel spans both grid columns and grows h-56 → h-96.
    const card = expand.closest('section')
    expect(card?.className).toMatch(/md:col-span-2/)
    expect(card?.querySelector('.h-96')).not.toBeNull()

    fireEvent.click(screen.getAllByRole('button', { name: 'Collapse chart' })[0])
    expect(card?.className).not.toMatch(/md:col-span-2/)
    expect(card?.querySelector('.h-56')).not.toBeNull()
  })

  it('renders no data-label control (removed after the AAPL field test — dense series collide)', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.queryByRole('button', { name: /data labels/i })).not.toBeInTheDocument()
  })

  it('shows the PNG download only when exportEnabled (Pro results surface)', () => {
    const { rerender } = render(<TrendCharts dataset={dataset} />)
    expect(screen.queryByRole('button', { name: 'Download chart as PNG' })).not.toBeInTheDocument()
    rerender(<TrendCharts dataset={dataset} exportEnabled />)
    expect(screen.getAllByRole('button', { name: 'Download chart as PNG' }).length).toBeGreaterThan(0)
  })
})

describe('TrendCharts PNG export wiring', () => {
  beforeEach(() => vi.mocked(exportPanelPng).mockClear())

  const clickExport = (panelTitle: string) => {
    const card = screen.getByText(panelTitle).closest('section') as HTMLElement
    fireEvent.click(within(card).getByRole('button', { name: 'Download chart as PNG' }))
    return vi.mocked(exportPanelPng).mock.calls.at(-1)?.[2]?.header
  }

  it('passes company, ticker, metric, and a multi-series legend to the export', () => {
    render(<TrendCharts dataset={dataset} exportEnabled />)
    const header = clickExport('Margins')
    expect(header?.company).toBe('Test Co')
    expect(header?.ticker).toBe('TST')
    expect(header?.title).toBe('Margins')
    expect(header?.legend.map((i) => i.label)).toEqual(['Gross', 'Operating'])
  })

  it('omits a single-item legend from the export, matching PanelLegend', () => {
    // Balance sheet with only equity present → one series → title alone identifies it, no legend.
    const equityOnly: AnalysisDataset = {
      ...dataset,
      series: dataset.series.filter((s) => ['revenue', 'shareholders_equity'].includes(s.concept)),
    }
    render(<TrendCharts dataset={equityOnly} exportEnabled />)
    const header = clickExport('Balance sheet')
    expect(header?.title).toBe('Balance sheet')
    expect(header?.legend).toEqual([])
  })

  it("notes the source data's day in the export, not its instant (#1457)", () => {
    // Noon UTC falls on October 20 in every zone from UTC-12 to UTC+11, so the case reads the same day in any runner.
    const { unmount } = render(<TrendCharts dataset={{ ...dataset, data_as_of: '2026-10-20T12:00:00.008084Z' }} exportEnabled />)
    expect(clickExport('Margins')?.sourceNote).toBe('Source: SEC filings via EarningsNerd · data as of Oct 20, 2026')
    unmount()
    render(<TrendCharts dataset={{ ...dataset, data_as_of: null }} exportEnabled />)
    expect(clickExport('Margins')?.sourceNote).toBe('Source: SEC filings via EarningsNerd · source refresh time unavailable')
  })
})

describe('TrendCharts chart fallback', () => {
  let consoleError: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    chartFault.on = true
    // React and the boundary's componentDidCatch log the caught error; keep the output quiet.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    chartFault.on = false
    consoleError.mockRestore()
  })

  it('names the grid when more than one panel shows and a panel throws (chrome/F10)', () => {
    // Revenue and gross margin only: two visible panels (top line, margins), one boundary around both.
    const two = structuredClone(dataset)
    two.series = two.series.filter((s) => s.concept === 'revenue' || s.concept === 'gross_margin')
    render(<TrendCharts dataset={two} />)
    expect(screen.getByText('These charts could not be drawn.')).toBeInTheDocument()
    expect(screen.queryByText('This chart could not be drawn.')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Margins' })).toBeNull()
  })
})

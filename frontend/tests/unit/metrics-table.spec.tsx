import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import MetricsTable from '@/features/analysis/components/MetricsTable'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const dataset: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'quarterly',
  period_key: '2024Q3..2024Q4',
  periods: [
    { key: '2024Q3', fiscal_year: 2024, fiscal_period: 'Q3', period_end: '2024-09-30' },
    { key: '2024Q4', fiscal_year: 2024, fiscal_period: 'Q4', period_end: '2024-12-31' },
  ],
  series: [
    {
      concept: 'revenue',
      label: 'Revenue',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 310_000_000, marker: 'F1', yoy: 0.05, qoq: 0.02 },
        { period: '2024Q4', value: 330_000_000, marker: 'F2', yoy: 0.08, qoq: 0.0645, derived: true },
      ],
    },
    {
      concept: 'eps_diluted',
      label: 'EPS (diluted)',
      unit: 'USD/shares',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 1.52, marker: 'F3' },
        // EPS needs a reported quarter; this fixture has no reported Q4 value.
        { period: '2024Q4', value: null },
      ],
    },
  ],
  inflections: [],
}

describe('MetricsTable', () => {
  it('labels quarterly growth by its own reconciliation and selected QoQ/YoY basis', () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[0].reconciled = true
    flagged.series[0].points[0].qoq = null
    flagged.series[0].points[0].qoq_reconciled = true
    flagged.series[0].points[0].yoy_reconciled = false
    flagged.series[0].points[1].qoq_reconciled = false
    render(<MetricsTable dataset={flagged} />)
    const figures = screen.getAllByRole('button', { name: /comparison carries data note a/ })
    expect(figures).toHaveLength(2)
    expect(figures[0].closest('td')).toHaveTextContent('YoY Change vs same quarter last year +5.0%')
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it('labels flagged figures independently of derived Q4 and leaves other values unlabelled', () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[0].reconciled = false
    flagged.series[0].points[1].reconciled = true
    const { rerender } = render(<MetricsTable dataset={flagged} />)
    const flaggedValue = screen.getByRole('button', { name: /Revenue, Q3 2024:.*data note a/ })
    expect(flaggedValue).toHaveTextContent('$310.0M')
    expect(flaggedValue.querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    expect(screen.getByRole('button', { name: /Revenue, Q4 2024:.*calculated/ })).toBeInTheDocument()
    rerender(<MetricsTable dataset={dataset} />)
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it('renders values, deltas, the derived dagger, and — for missing points', () => {
    render(<MetricsTable dataset={dataset} />)

    expect(screen.getByText('Revenue')).toBeInTheDocument()
    expect(screen.getByText('EPS (diluted)')).toBeInTheDocument()
    // Derived Q4 revenue carries the computed dagger; the badge explains it.
    expect(screen.getByRole('button', { name: /Revenue, Q4 2024:.*calculated/ })).toBeInTheDocument()
    expect(screen.getByText('† calculated')).toBeInTheDocument()
    // The never-derived EPS Q4 renders an em-dash placeholder.
    expect(screen.getAllByRole('button', { name: /unavailable.*data note/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    // Quarterly mode shows QoQ deltas.
    expect(screen.getByText('+2.0%').parentElement).toHaveTextContent('Change vs prior quarter')
  })

  it('hides the CAGR column entirely in quarterly mode (dead UI otherwise)', () => {
    render(<MetricsTable dataset={dataset} />)
    expect(screen.queryByText('CAGR')).not.toBeInTheDocument()
  })

  it('makes the Metric column sticky', () => {
    const { container } = render(<MetricsTable dataset={dataset} />)
    const firstBodyCell = container.querySelector('tbody tr th[scope="row"]')
    expect(firstBodyCell).toHaveClass('sticky')
    expect(firstBodyCell).toHaveClass('left-0')
  })

  it('rounds unusually long table figures while source detail preserves value and full comparison', async () => {
    const large = structuredClone(dataset)
    large.series[1].points[0] = { period: '2024Q3', value: -15154, reconciled: false, qoq: 1234.567, qoq_reconciled: false }
    render(<MetricsTable dataset={large} />)
    const figure = screen.getByRole('button', { name: /EPS \(diluted\), Q3 2024:/ })
    expect(figure).toHaveTextContent('-$15.2K')
    expect(figure.closest('td')).toHaveTextContent('+123.5K%')
    expect(screen.getByText('Figures are rounded for display. Select a value for full precision.')).toBeVisible()
    await userEvent.click(figure)
    const detail = screen.getByRole('dialog')
    expect(within(detail).getByText('As stored: -15,154 USD per share')).toBeVisible()
    expect(within(detail).getAllByText('+123,456.7%')[0]).toBeVisible()
    expect(large.series[1].points[0].value).toBe(-15154)
  })

  it('states non-USD currency at the row and source control without a misleading dollar prefix', async () => {
    const canadian = structuredClone(dataset)
    canadian.series[1].unit = 'CAD/shares'
    canadian.series[1].points[0].value = -15154
    render(<MetricsTable dataset={canadian} />)
    expect(screen.getByRole('rowheader', { name: 'EPS (diluted) CAD per share' })).toBeVisible()
    const figure = screen.getByRole('button', { name: /EPS \(diluted\) \(CAD per share\), Q3 2024:/ })
    expect(figure).toHaveTextContent('-15.2K')
    expect(figure).not.toHaveTextContent('$')
    await userEvent.click(figure)
    expect(within(screen.getByRole('dialog')).getByText('As stored: -15,154 CAD per share')).toBeVisible()
  })

  it('shows the Export Excel button only when the handler is passed, and fires it', async () => {
    const onExportXlsx = vi.fn()
    const { rerender } = render(<MetricsTable dataset={dataset} />)
    expect(screen.queryByRole('button', { name: /export excel/i })).not.toBeInTheDocument()

    rerender(<MetricsTable dataset={dataset} onExportXlsx={onExportXlsx} />)
    await userEvent.click(screen.getByRole('button', { name: /export excel/i }))
    expect(onExportXlsx).toHaveBeenCalledTimes(1)
  })

  it('marks the export button busy (click-inert) while the workbook request is in flight', async () => {
    // Button's loading contract is aria-busy + a swallowed click, not the disabled attribute.
    const onExportXlsx = vi.fn()
    render(<MetricsTable dataset={dataset} onExportXlsx={onExportXlsx} exporting />)
    const button = screen.getByRole('button', { name: /export excel/i })
    expect(button).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(button)
    expect(onExportXlsx).not.toHaveBeenCalled()
  })
})

describe('MetricsTable — annual mode: CAGR column, pp deltas, tone policy', () => {
  const annualDataset: AnalysisDataset = {
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
        concept: 'net_margin',
        label: 'Net margin',
        unit: 'pure',
        percent: true,
        tone: 'normal',
        cagr: null,
        window_pp: -9.0,
        window_pp_range: 'FY2023..FY2024',
        points: [
          { period: 'FY2023', value: 47.3, marker: 'F1' },
          { period: 'FY2024', value: 38.3, marker: 'F2', yoy: -9.0 },
        ],
      },
      {
        concept: 'long_term_debt',
        label: 'Long-term debt',
        unit: 'USD',
        percent: false,
        tone: 'inverted',
        cagr: -0.05,
        points: [
          { period: 'FY2023', value: 42_000_000_000, marker: 'F3' },
          { period: 'FY2024', value: 31_400_000_000, marker: 'F4', yoy: -0.252 },
        ],
      },
      {
        concept: 'investing_cash_flow',
        label: 'Investing cash flow',
        unit: 'USD',
        percent: false,
        tone: 'neutral',
        cagr: null,
        points: [
          { period: 'FY2023', value: 503_000_000, marker: 'F5' },
          { period: 'FY2024', value: -71_925_000_000, marker: 'F6', yoy: 'nm' },
        ],
      },
    ],
    inflections: [],
  }

  it('shows the CAGR column and formats a margin series delta as pp, not relative %', () => {
    render(<MetricsTable dataset={annualDataset} />)
    expect(screen.getByText('CAGR')).toBeInTheDocument()
    // 47.3% -> 38.3% is -9.0pp — never "-19.0%" (the relative-change convention this fixes).
    expect(screen.getByRole('button', { name: /Net margin, FY2024:/ }).closest('td')).toHaveTextContent('Change vs prior year -9.0pp')
  })

  it('marks annual window growth from flagged inputs separately from the period values', () => {
    const flagged = structuredClone(annualDataset)
    flagged.series[0].window_pp_reconciled = false
    flagged.series[1].cagr_reconciled = false
    render(<MetricsTable dataset={flagged} />)
    const windows = screen.getAllByRole('button', { name: /(?:Chg|CAGR), .*data note a.*View source/ })
    expect(windows).toHaveLength(2)
    expect(windows[0]).toHaveTextContent('-9.0pp')
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it('opens exact annual window comparison detail on the compact value control', async () => {
    const large = structuredClone(annualDataset)
    large.series[1].cagr = 1234.567
    large.series[1].cagr_reconciled = false
    render(<MetricsTable dataset={large} />)
    const window = screen.getByRole('button', { name: /Long-term debt CAGR, FY2023\.\.FY2024:/ })
    expect(window).toHaveTextContent('+123.5K%')
    await userEvent.click(window)
    const detail = screen.getByRole('dialog')
    expect(within(detail).getByText('As stored: 1,234.567 (growth fraction)')).toBeVisible()
    expect(within(detail).getAllByText('+123,456.7%')[0]).toBeVisible()
  })

  it('renders "n/m" for a sign-flip growth value instead of a nonsensical percentage', () => {
    render(<MetricsTable dataset={annualDataset} />)
    expect(screen.getByText('n/m').parentElement).toHaveTextContent('Change vs prior year')
    expect(screen.getByText(/n\/m means not meaningful/)).toHaveTextContent('The final column shows CAGR, or percentage-point change for percent-unit rows. Each value’s source detail states its calculation range.')
  })

  it('inverts tone for long-term debt: a decrease renders gain-toned, not loss-toned', () => {
    render(<MetricsTable dataset={annualDataset} />)
    const delta = screen.getByText('-25.2%')
    expect(delta.parentElement?.className).toMatch(/gain/)
  })

  it('shows the window pp change in the CAGR column for a percent-unit row (never a dead —)', () => {
    render(<MetricsTable dataset={annualDataset} />)
    // net_margin: cagr is always null (unit "pure"), so the column resolves window_pp instead —
    // the same rule the KPI strip uses (windowGrowth). The tooltip names the basis window.
    const cell = screen.getAllByText('-9.0pp').find((node) => node.closest('[title]'))!
    expect(cell.closest('[title]')).toHaveAttribute('title', expect.stringContaining('FY2023..FY2024'))
  })
})


describe('MetricsTable period windows', () => {
  const twelve: AnalysisDataset = {
    ...dataset,
    period_key: '2023Q1..2025Q4',
    periods: Array.from({ length: 12 }, (_, index) => ({
      key: `${2023 + Math.floor(index / 4)}Q${index % 4 + 1}`,
      fiscal_year: 2023 + Math.floor(index / 4), fiscal_period: `Q${index % 4 + 1}`,
      period_end: `${2023 + Math.floor(index / 4)}-${['03', '06', '09', '12'][index % 4]}-28`,
    })),
    series: [{ ...dataset.series[0], points: Array.from({ length: 12 }, (_, index) => ({
      period: `${2023 + Math.floor(index / 4)}Q${index % 4 + 1}`, value: (index + 1) * 1e9,
      qoq: index ? 0.1 : null, derived: index === 3,
    })) }],
  }

  it('keeps All as the default, limits only table columns, and resets for a new dataset', async () => {
    const input = structuredClone(twelve)
    const { rerender } = render(<MetricsTable dataset={input} />)
    const table = screen.getByRole('table')
    expect(screen.getByRole('button', { name: 'All 12' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(table).getAllByRole('columnheader')).toHaveLength(13)
    await userEvent.click(screen.getByRole('button', { name: 'Newest 6' }))
    expect(screen.getByRole('status')).toHaveTextContent('Showing 6 of 12 quarters')
    expect(screen.getByRole('button', { name: 'Newest 6' })).toHaveFocus()
    expect(screen.queryByRole('button', { name: /Revenue, Q1 2023:/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revenue, Q4 2025:/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Earliest 6' }))
    expect(screen.getByRole('button', { name: /Revenue, Q1 2023:/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Revenue, Q4 2025:/ })).not.toBeInTheDocument()
    expect(input).toEqual(twelve)
    rerender(<MetricsTable dataset={{ ...input, ticker: 'OTHER' }} />)
    expect(screen.getByRole('button', { name: 'All 12' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByRole('columnheader')).toHaveLength(13)
    rerender(<MetricsTable dataset={input} />)
    expect(screen.getByRole('button', { name: 'All 12' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('marks only a populated, actually derived Q4 header and uses semantic row headers', () => {
    const input = structuredClone(twelve)
    input.series[0].points[7] = {
      ...input.series[0].points[7], derived: true,
      provenance: { version: 1, method: 'reported', validation: 'passed', reasons: [], formula: null, inputs: [] },
    }
    // An ordinary calculated ratio is not a quarter-derived input to the Q4 column marker.
    input.series[0].points[11].provenance = { version: 1, method: 'calculated', validation: 'passed', reasons: [], formula: 'ratio', inputs: [] }
    render(<MetricsTable dataset={input} />)
    const headers = screen.getAllByRole('columnheader')
    expect(headers[4]).toHaveTextContent('†')
    expect(headers[4]).toHaveAccessibleName('Q4 2023, includes calculated fourth-quarter flow figures')
    expect(headers[4].querySelector('[data-period-label]')).toHaveTextContent('Q4’23 †')
    expect(screen.getByRole('columnheader', { name: 'Q1 2023' })).toBeInTheDocument()
    expect(headers[8]).not.toHaveTextContent('†')
    expect(headers[12]).not.toHaveTextContent('†')
    expect(screen.getByRole('rowheader', { name: 'Revenue' })).toHaveAttribute('scope', 'row')
    expect(screen.getByRole('table')).toHaveAccessibleName(/value and change versus prior quarter.*YoY labels/)
    expect(screen.getByText(/Fiscal quarters follow/)).toHaveTextContent('A Q4 header † means some flow figures are calculated from annual totals less the first nine months; it does not mark the column’s balance-sheet figures as calculated.')
  })

  it('shows every period and suppresses window controls for an explicit illustrative sample', async () => {
    const { rerender } = render(<MetricsTable dataset={twelve} />)
    await userEvent.click(screen.getByRole('button', { name: 'Newest 6' }))
    rerender(<MetricsTable dataset={twelve} sample />)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 12 of 12 quarters')
    expect(screen.getAllByRole('columnheader')).toHaveLength(13)
    expect(screen.queryByRole('group', { name: 'Table window' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Newest 6' })).not.toBeInTheDocument()
  })
})

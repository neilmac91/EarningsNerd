import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import MetricsTable from '@/features/analysis/components/MetricsTable'
import { tableTokenBudget } from '@/features/analysis/lib/tableFormat'

const TAILWIND_FONT_SIZE = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { fontSize: Record<string, [string, unknown]> } } }).theme.extend.fontSize
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

  it('frames the sheet: the heading row and the Metric column keep the panel surface and its inks, the figures sit on the sheet', () => {
    // The founder's call on the sheet: the labels keep the normal theme colours, for slight contrast with the data.
    const { container } = render(<MetricsTable dataset={dataset} />)
    const table = container.querySelector('table')!
    const frame = table.parentElement!.parentElement!
    expect(frame).toHaveClass('rounded-xl', 'outline', 'outline-1', 'outline-rule-light', 'bg-well-light', 'dark:outline-rule-dark', 'dark:bg-well-dark')
    expect(table.querySelector('thead tr')).toHaveClass('text-text-secondary-light', 'dark:text-text-secondary-dark')
    for (const th of table.querySelectorAll('thead th')) expect(th).toHaveClass('bg-panel-light', 'dark:bg-panel-dark')
    for (const row of table.querySelectorAll('tbody tr')) {
      const [label, ...figures] = [...row.children]
      expect(label).toHaveClass('bg-panel-light', 'dark:bg-panel-dark', 'border-r', 'border-rule-light', 'dark:border-rule-dark')
      for (const cell of figures) expect(cell.className, 'a figure cell shows the sheet').not.toMatch(/(?:^|\s)(?:dark:)?bg-/)
    }
    expect(within(table).getByRole('rowheader', { name: 'Revenue' }).firstElementChild).toHaveClass('text-figure-light', 'dark:text-figure-dark')
  })

  it('sets every figure and change line in the figure face, with tabular lining numerals and no tracking', () => {
    render(<MetricsTable dataset={dataset} />)
    const control = screen.getByRole('button', { name: /^Revenue, Q3 2024:/ })
    const cell = control.closest('td')!
    expect(cell.firstElementChild).toHaveClass('font-figure', 'tabular-nums', 'lining-nums', 'tracking-normal')
    // A button's UA font shorthand resets font-variant-numeric, so the control re-declares the figure's numerals.
    expect(control).toHaveClass('tabular-nums', 'lining-nums')
    // The change line is 12px too, and its own size class would bring caption tracking back: it zeroes it again.
    expect(within(cell).getByText(/Change vs prior quarter/).closest('[class*="text-gain-data"]')).toHaveClass('tracking-normal')
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
    const window = screen.getByRole('button', { name: /Long-term debt CAGR, FY2023–FY2024:/ })
    expect(window).toHaveTextContent('+123.5K%')
    await userEvent.click(window)
    const detail = screen.getByRole('dialog')
    expect(within(detail).getByText('As stored: 1,234.567 (growth fraction)')).toBeVisible()
    expect(within(detail).getAllByText('+123,456.7%')[0]).toBeVisible()
  })

  it('renders "n/m" for a sign-flip growth value instead of a nonsensical percentage', () => {
    render(<MetricsTable dataset={annualDataset} />)
    expect(screen.getByText('n/m').parentElement).toHaveTextContent('Change vs prior year')
    // Read aloud as words, not "n slash m": the abbreviation is hidden and the words stand in for it.
    const token = screen.getByText('n/m')
    expect(token).toHaveAttribute('aria-hidden', 'true')
    expect(token.nextElementSibling).toHaveClass('sr-only')
    expect(token.nextElementSibling).toHaveTextContent(/^not meaningful$/)
    expect(screen.getByText(/n\/m means not meaningful/)).toHaveTextContent('The final column shows CAGR, or percentage-point change for percent-unit rows. Each value’s source detail states its calculation range.')
  })

  it('says in the caption what the legend says of the final column, with no window left to select', () => {
    const { container } = render(<MetricsTable dataset={annualDataset} />)
    const caption = container.querySelector('caption')!.textContent!
    expect(caption).toMatch(/: value and change versus prior year\. The final column shows CAGR, or percentage-point change for percent-unit rows\.$/)
    expect(screen.getByText(/n\/m means not meaningful/).textContent).toContain('The final column shows CAGR, or percentage-point change for percent-unit rows.')
    expect(caption).not.toMatch(/select/)
  })

  it('drops the final column, its legend and its caption on a one-year run, whose count reads in the singular (E185)', () => {
    // A run of one year has no window: the engine's CAGR and window change need two years, so the column
    // would show the missing-value mark in every row (chief design on #1586, comment 6384261233).
    const oneYear: AnalysisDataset = {
      ...annualDataset,
      period_key: 'FY2024..FY2024',
      periods: annualDataset.periods.slice(-1),
      series: annualDataset.series.map((series) => ({ ...series, cagr: null, window_pp: null, window_pp_range: null, points: series.points.slice(-1) })),
    }
    const { container } = render(<MetricsTable dataset={oneYear} />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(2)
    expect(screen.getByRole('columnheader', { name: 'FY2024' })).toBeInTheDocument()
    expect(screen.queryByText('CAGR')).not.toBeInTheDocument()
    expect(screen.getByText(/n\/m means not meaningful/).textContent).toBe('n/m means not meaningful.')
    expect(container.querySelector('caption')?.textContent).toBe('Metrics by period, 1 year: value and change versus prior year.')
    expect(container.textContent).not.toMatch(/Showing \d/)
  })

  it('names the metric names as what lies left of a one-period table on a phone, annual or quarterly (E185)', () => {
    // A phone opens the table at its end. One period under enlarged text at 390px (a 208px label and a 136px period in a
    // 292px region) overflows, and only the labels lie to its left (chief design on #1590, comment 6385421681).
    const media = window.matchMedia('(max-width: 639px)')
    vi.spyOn(window, 'matchMedia').mockReturnValue({ ...media, matches: true })
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(292)
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
      const columns = this.querySelectorAll('thead th').length
      return Math.max(292, 208 + 136 * Math.max(columns - 1, 0) + Number.parseFloat(this.style.paddingInlineEnd || '0'))
    })
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const width = this.tagName === 'TH' ? (this === this.parentElement?.firstElementChild ? 208 : 136) : 292
      return { x: 0, y: 0, top: 0, bottom: 24, left: 0, right: width, width, height: 24, toJSON: () => ({}) }
    })
    try {
      const oneYear: AnalysisDataset = {
        ...annualDataset,
        period_key: 'FY2024..FY2024',
        periods: annualDataset.periods.slice(-1),
        series: annualDataset.series.map((series) => ({ ...series, cagr: null, window_pp: null, window_pp_range: null, points: series.points.slice(-1) })),
      }
      const oneQuarter: AnalysisDataset = {
        ...dataset,
        period_key: '2024Q3..2024Q3',
        periods: dataset.periods.slice(0, 1),
        series: dataset.series.map((series) => ({ ...series, points: series.points.slice(0, 1) })),
      }
      for (const [run, unit] of [[oneYear, 'year'], [oneQuarter, 'quarter']] as const) {
        const { unmount } = render(<MetricsTable dataset={run} />)
        expect(screen.getByRole('region', { name: `Metrics by period, scrollable table of 1 ${unit}` })).toHaveAccessibleDescription('← Metric names')
        unmount()
      }
      render(<MetricsTable dataset={annualDataset} />)
      expect(screen.getByRole('region', { name: 'Metrics by period, scrollable table of 2 years' })).toHaveAccessibleDescription('← Earlier years')
    } finally {
      vi.restoreAllMocks()
    }
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
    expect(cell.closest('[title]')).toHaveAttribute('title', expect.stringContaining('FY2023–FY2024'))
  })
})


describe('MetricsTable periods', () => {
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

  it('shows every period with no window control, and starts a new report on a fresh scroller', () => {
    // The 6-of-N window is retired: the table always holds the whole run and scrolls sideways where it must.
    const input = structuredClone(twelve)
    const { rerender } = render(<MetricsTable dataset={input} />)
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader')).toHaveLength(13)
    expect(screen.queryByRole('group', { name: 'Table window' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^(All 12|Newest 6|Earliest 6)$/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revenue, Q1 2023:/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revenue, Q4 2025:/ })).toBeInTheDocument()
    expect(input).toEqual(twelve)
    // The same report keeps its scroller (and so its scroll position); another report gets a new one.
    const scroller = table.parentElement
    rerender(<MetricsTable dataset={structuredClone(input)} />)
    expect(screen.getByRole('table').parentElement).toBe(scroller)
    rerender(<MetricsTable dataset={{ ...input, ticker: 'OTHER' }} />)
    expect(screen.getByRole('table').parentElement).not.toBe(scroller)
    expect(screen.getAllByRole('columnheader')).toHaveLength(13)
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
    expect(screen.getByRole('table')).toHaveAccessibleName(/value and change versus prior quarter\. Fiscal quarters follow the company’s reporting calendar\. YoY labels/)
    expect(screen.getByText(/^n\/m means not meaningful\./)).toHaveTextContent('A Q4 header † means some flow figures are calculated from annual totals less the first nine months; it does not mark the column’s balance-sheet figures as calculated.')
  })

})

/**
 * The column arithmetic (DESIGN_SYSTEM.md, Data note mark): a figure is 12px Geist Mono (DataTable's compact text-xs),
 * a mark 11px (text-data-xs), each glyph 0.6em wide (Geist Mono's 600-unit advance, which the e2e "analysis phone
 * marks" gate measures on the real glyphs), and every mark keeps 2px (ml-0.5) from what precedes it; a note's letters
 * share one box. The gutter is one mark and its gap, so a marked and an unmarked figure share one edge, and a period
 * column holds the widest line tableTokenBudget allows inside its inset (1px a side on a phone, 4px from md).
 */
describe('MetricsTable column widths', () => {
  const source = readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../features/analysis/components/MetricsTable.tsx'), 'utf8')
  const rem = (name: string, prefix = '') => {
    const match = new RegExp(`(?:^|[\\s"])${prefix.replace(':', '\\:')}\\[--${name}:([\\d.]+)rem\\]`).exec(source)
    if (!match) throw new Error(`${prefix}--${name} is not a rem value in MetricsTable.tsx`)
    return Number(match[1])
  }
  const ADVANCE = 0.6
  const FIGURE = parseFloat(TAILWIND_FONT_SIZE.xs[0]) // rem, text-xs
  const MARK = parseFloat(TAILWIND_FONT_SIZE['data-xs'][0]) // rem, text-data-xs
  const GAP = 0.125 // rem, ml-0.5
  /** Each line the budget allows: [label, width in rem], over a dagger or none and a note of none, one or two letters. */
  const lines = [false, true].flatMap((calculated) => ['', 'a', 'ab'].map((letter) => {
    const glyphs = tableTokenBudget(calculated, letter)
    const marks = [calculated, letter !== ''].filter(Boolean).length
    const width = glyphs * ADVANCE * FIGURE + marks * GAP + (Number(calculated) + letter.length) * ADVANCE * MARK
    return [`${glyphs} glyphs${calculated ? ' †' : ''}${letter ? ` ${letter}` : ''}`, width] as const
  }))
  const widest = Math.max(...lines.map(([, width]) => width))

  it('lets the metric column give up to 6px only below md, where that buys a phone its third whole period', () => {
    const base = /\[--metric-col:min\(([\d.]+)rem,100cqi\)\]/.exec(source)
    const bands = [...source.matchAll(/(\S*)\[@container\(([\d.]+)rem<=width<([\d.]+)rem\)\]:\[--metric-col:/g)]
    expect(base && bands.length === 1, 'the metric column and its one band').toBeTruthy()
    // From md the band would cut the 8.25rem column, not the phone's 6.5rem: at 200% text an 816px screen falls in it.
    expect(bands[0][1], 'the band\'s variant').toBe('max-md:')
    const band = /max-md:\[@container\(([\d.]+)rem<=width<([\d.]+)rem\)\]:\[--metric-col:calc\(100cqi-3\*var\(--period-col\)\)\]/.exec(source)
    expect(band, 'the band\'s rule').toBeTruthy()
    const [low, high] = [Number(band![1]), Number(band![2])]
    // From the top of the band three periods fit beside the full metric column anyway; below its foot they cannot.
    expect(high).toBeCloseTo(Number(base![1]) + 3 * rem('period-col'), 6)
    expect(high - low).toBeCloseTo(0.375, 6)
  })

  it('keeps the mark gutter one mark and its 2px gap wide', () => {
    expect(rem('mark-gutter')).toBeCloseTo(GAP + ADVANCE * MARK, 6)
  })

  it('gives every period column room for its widest line inside its inset, at the default and a doubled text size', () => {
    expect(widest * 16, lines.map(([label, width]) => `${label}: ${(width * 16).toFixed(1)}px`).join(', ')).toBeCloseTo(67.6, 6)
    for (const root of [16, 32]) {
      expect(rem('period-col') * root - 2, `phone, ${root}px root`).toBeGreaterThanOrEqual(widest * root)
      expect(rem('period-col', 'md:') * root - 0.5 * root, `md, ${root}px root`).toBeGreaterThanOrEqual(widest * root) // px-1 a side
    }
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const getFilingFundamentals = vi.fn()
vi.mock('@/features/fundamentals/api/fundamentals-api', () => ({
  getFilingFundamentals: (...args: unknown[]) => getFilingFundamentals(...args),
}))

import FundamentalsTrendChart from '@/features/fundamentals/components/FundamentalsTrendChart'
import { ThemeContext } from '@/components/ThemeProvider'
import { BROKEN_BARS } from '@/features/analysis/lib/charts/barChart'
import { CARD_HEIGHT } from '@/features/analysis/lib/charts/layout'
import { CHART_TOKENS } from '@/features/analysis/lib/charts/theme'

/** The metric picker: a compact select beside its "Metric" label, its options in sentence case. */
const metricPicker = () => screen.findByRole('combobox', { name: 'Metric' })
const pick = (picker: HTMLElement, label: string) =>
  fireEvent.change(picker, { target: { value: (screen.getByRole('option', { name: label }) as HTMLOptionElement).value } })

/** Without a theme the chart renders provider-less, as SSR does, and takes the light fallback. */
function renderChart(filingId = 285, subtitle?: string, theme?: 'light' | 'dark') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const chart = (
    <QueryClientProvider client={qc}>
      <FundamentalsTrendChart filingId={filingId} subtitle={subtitle} />
    </QueryClientProvider>
  )
  return render(theme ? <ThemeContext.Provider value={{ theme, toggleTheme: () => {} }}>{chart}</ThemeContext.Provider> : chart)
}

/** The engine's drawing of the active metric (TrendChartSvg), once its font wait is over: jsdom has no Font Loading
 *  API, so the plot paints at once. */
const drawn = async (name: string) => {
  const svg = await screen.findByRole('img', { name: `${name} chart` })
  return {
    svg,
    fills: [...svg.querySelectorAll('rect[data-series]')].map((bar) => bar.getAttribute('fill')),
    printed: (role: string) => [...svg.querySelectorAll(`text[data-text="${role}"]`)].map((text) => text.textContent),
  }
}

const point = (fy: number | null, value: number | null, unit: string, reconciled = true, extra: Record<string, unknown> = {}) => ({
  period_end: fy == null ? null : `${fy}-12-31`,
  fiscal_year: fy,
  fiscal_period: 'FY',
  value,
  unit,
  form: '10-K',
  accession: `acc-${fy}`,
  reconciled,
  ...extra,
})

const RESP = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  concepts: [
    { concept: 'revenue', unit: 'USD', points: [point(2022, 394328000000, 'USD'), point(2023, 383285000000, 'USD')] },
    { concept: 'net_margin', unit: 'pure', points: [point(2023, 25.3, 'pure')] },
    { concept: 'some_unfeatured_concept', unit: 'USD', points: [point(2023, 1, 'USD')] },
  ],
}

const respOf = (...concepts: { concept: string; unit: string; points: ReturnType<typeof point>[] }[]) => ({ ticker: 'TEST', company_name: 'Test Co.', concepts })

describe('FundamentalsTrendChart', () => {
  beforeEach(() => {
    getFilingFundamentals.mockReset()
  })

  it('shows only featured concepts present in the response, defaulting to the first', async () => {
    getFilingFundamentals.mockResolvedValue(RESP)
    renderChart()

    // Wait on the data-driven picker (the heading also shows during loading).
    const picker = await metricPicker()
    expect(picker).toHaveValue('revenue')
    expect(screen.getByText('Financial trends')).toBeInTheDocument()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Revenue', 'Net margin'])
    expect(screen.queryByText('some_unfeatured_concept')).not.toBeInTheDocument()
    expect(screen.getByTestId('fundamentals-chart')).toBeInTheDocument()
    // Clean data → no honesty badge.
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
    expect(getFilingFundamentals).toHaveBeenCalledWith(285)
  })

  it('shows the Unverified badge when the active series has a flagged value', async () => {
    getFilingFundamentals.mockResolvedValue({
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      concepts: [
        { concept: 'revenue', unit: 'USD', points: [point(2022, 100, 'USD'), point(2023, 0, 'USD', false)] },
      ],
    })
    renderChart()

    const badge = await screen.findByText('Source check needed')
    // Its row wraps and, below a 24rem viewport, so may its label (SourceCheckBadge), in the 16px step (the hero
    // example's badge, E156): under 200% text the one-line badge is wider than a phone's card.
    expect(badge.parentElement?.className).toMatch(/(^| )flex-wrap( |$)/)
    expect(badge.className).toContain('[@media(max-width:24rem)]:whitespace-normal')
    expect(badge.className).toContain('[@media(max-width:24rem)]:rounded-xl')
  })

  it('switches the active metric from the select', async () => {
    getFilingFundamentals.mockResolvedValue(RESP)
    renderChart()

    const picker = await metricPicker()
    pick(picker, 'Net margin')

    expect(picker).toHaveValue('net_margin')
    expect((screen.getByRole('option', { name: 'Net margin' }) as HTMLOptionElement).selected).toBe(true)
    expect((screen.getByRole('option', { name: 'Revenue' }) as HTMLOptionElement).selected).toBe(false)
  })

  it('picks the metric through a compact select of one width beside its label, 14rem, never a segmented row', async () => {
    getFilingFundamentals.mockResolvedValue(RESP)
    renderChart()

    const picker = await metricPicker()
    expect(picker.tagName).toBe('SELECT')
    expect(picker.closest('label')).toHaveTextContent(/^Metric/)
    // One width the loading card can know (E253): 14rem, the smallest step that holds every FEATURED label, whatever
    // options the filing brings, capped at its row and never filling it; pr-9 clears the chevron.
    const classes = picker.className.split(/\s+/)
    expect(classes).toEqual(expect.arrayContaining(['w-56', 'max-w-full', 'pr-9']))
    expect(classes).not.toContain('w-full')
    expect(screen.queryByRole('group', { name: 'Metric' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Revenue' })).toBeNull()
  })

  it('draws every metric in chart-1, in each theme’s half, with each value printed on its bar (D-067)', async () => {
    for (const theme of ['light', 'dark'] as const) {
      getFilingFundamentals.mockResolvedValue(RESP)
      const { unmount } = renderChart(285, undefined, theme)
      const chart1 = CHART_TOKENS[theme].series[0]

      const picker = await metricPicker()
      const revenue = await drawn('Revenue')
      expect(revenue.fills, `${theme}: revenue`).toEqual([chart1, chart1])
      expect(revenue.printed('label')).toEqual(['$394B', '$383B'])
      expect(revenue.printed('x')).toEqual(['2022', '2023'])

      // Net margin was the second option, so it took the second series colour; now every metric is chart-1.
      pick(picker, 'Net margin')
      const margin = await drawn('Net margin')
      expect(margin.fills, `${theme}: net margin`).toEqual([chart1])
      expect(margin.printed('label')).toEqual(['25.3%'])
      expect(margin.printed('tick')).toContain('0%')
      unmount()
    }
  })

  it('reads each year through one values stop, from the newest: its fiscal year and end, and a derived figure says so', async () => {
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'revenue', unit: 'USD', points: [point(2024, 391035000000, 'USD'), point(2025, 416161000000, 'USD')] },
      { concept: 'net_margin', unit: 'pure', points: [point(2025, 26.9, 'pure', true, { provenance: { version: 1, method: 'calculated', validation: 'passed', reasons: [] } })] },
    ))
    renderChart()

    const picker = await metricPicker()
    await drawn('Revenue')
    const stop = screen.getByRole('slider', { name: 'Revenue chart values' })
    expect(stop).toHaveAttribute('aria-valuetext', 'FY2025, year ended December 31, 2025. Revenue: $416.2 billion.')
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    expect(stop).toHaveAttribute('aria-valuetext', 'FY2024, year ended December 31, 2024. Revenue: $391.0 billion.')

    pick(picker, 'Net margin')
    await drawn('Net margin')
    expect(screen.getByRole('slider', { name: 'Net margin chart values' }))
      .toHaveAttribute('aria-valuetext', 'FY2025, year ended December 31, 2025. Net margin: 26.9%, calculated.')
  })

  it('keeps a withheld year’s slot and prints "—" in it, and Sources & checks still names it', async () => {
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'revenue', unit: 'USD', points: [
        point(2023, 383285000000, 'USD'),
        point(2024, null, 'USD', true, { provenance: { version: 1, method: 'reported', validation: 'unavailable', reasons: [] } }),
        point(2025, 416161000000, 'USD'),
      ] },
    ))
    renderChart()

    const { printed } = await drawn('Revenue')
    expect(printed('x')).toEqual(['2023', '2024', '2025'])
    expect(printed('label')).toEqual(['$383B', '$416B'])
    expect(printed('gap')).toEqual(['—'])
    expect(screen.getByText(/^Revenue, 2024: unavailable\./)).toBeInTheDocument()
  })

  it('says why at the plot’s height when every year is withheld, and draws no plot', async () => {
    const withheld = { provenance: { version: 1, method: 'calculated', validation: 'unavailable', reasons: ['unsupported_eps_calculation'] } }
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'eps_diluted', unit: 'USD/shares', points: [point(2024, null, 'USD/shares', true, withheld), point(2025, null, 'USD/shares', true, withheld)] },
    ))
    renderChart()

    await metricPicker()
    const sentence = await screen.findByText('No multi-year data available for this metric.')
    expect(sentence).toHaveAttribute('data-chart-text', 'unavailable')
    expect(sentence.style.height).toBe(`${CARD_HEIGHT}px`)
    expect(screen.getByTestId('fundamentals-chart')).toContainElement(sentence)
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('slider')).toBeNull()
  })

  it('a margin bar the axis clips prints its true value, and the card says so under the plot', async () => {
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'net_margin', unit: 'pure', points: [point(2023, -18093, 'pure'), point(2024, -301.5, 'pure'), point(2025, -255.3, 'pure')] },
    ))
    renderChart()

    const { printed } = await drawn('Net margin')
    expect(printed('label')).toContain('−18,093%')
    expect(screen.getByText(BROKEN_BARS.text)).toHaveAttribute('data-chart-text', 'footnote')
  })

  it('prints an amount in its own currency, named in the footnote, and a per-share one in cents', async () => {
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'revenue', unit: 'CNY', points: [point(2024, 941168000000, 'CNY'), point(2025, 996347000000, 'CNY')] },
      { concept: 'eps_diluted', unit: 'CNY/shares', points: [point(2024, 3.13, 'CNY/shares'), point(2025, 5.66, 'CNY/shares')] },
    ))
    renderChart()

    const picker = await metricPicker()
    const revenue = await drawn('Revenue')
    // A2: one unit per axis, the top tick's (CN¥1.2T).
    expect(revenue.printed('label')).toEqual(['CN¥0.941T', 'CN¥0.996T'])
    expect(screen.getByText(/Annual figures from SEC filings \(XBRL\), reported in CNY\./)).toBeInTheDocument()

    pick(picker, 'Diluted EPS')
    const eps = await drawn('Diluted EPS')
    expect(eps.printed('label')).toEqual(['CN¥3.13', 'CN¥5.66'])
    expect(screen.getByRole('slider', { name: 'Diluted EPS chart values' }))
      .toHaveAttribute('aria-valuetext', 'FY2025, year ended December 31, 2025. Diluted EPS: CN¥5.66.')
  })

  it('says only that values don’t fit where no label tier fits the card’s width: no metrics table here lists the years', async () => {
    // A phone's card (217px at 320px) and amounts in thousands of trillions of won, printed by code (E203).
    const width = vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(217)
    try {
      getFilingFundamentals.mockResolvedValue(respOf(
        { concept: 'revenue', unit: 'KRW', points: [point(2023, 123.456e12, 'KRW'), point(2024, 580.756e12, 'KRW'), point(2025, 1038.056e12, 'KRW')] },
      ))
      renderChart()

      const { printed } = await drawn('Revenue')
      expect(await screen.findByText('Values don’t fit at this width.')).toHaveAttribute('data-chart-text', 'fit')
      expect(printed('label')).toEqual([])
      expect(screen.queryByText(/metrics table/)).toBeNull()
    } finally {
      width.mockRestore()
    }
  })

  it('names a year the backend leaves unnamed by its period end, and draws a year two points share twice', async () => {
    getFilingFundamentals.mockResolvedValue(respOf(
      { concept: 'revenue', unit: 'USD', points: [
        { ...point(null, 100, 'USD'), period_end: '2023-06-30' },
        { ...point(2024, 200, 'USD'), period_end: '2024-01-31' },
        { ...point(2024, 300, 'USD'), period_end: '2024-12-31' },
      ] },
    ))
    renderChart()

    const { printed, svg } = await drawn('Revenue')
    expect(printed('x')).toEqual(['2023', '2024', '2024'])
    expect(printed('label')).toEqual(['$100', '$200', '$300'])
    expect(new Set([...svg.querySelectorAll('rect[data-series]')].map((bar) => bar.getAttribute('data-period'))).size).toBe(3)
  })

  it('while loading holds the room of what replaces it, the plot’s height first, and shows no footnote or Sources & checks yet', async () => {
    getFilingFundamentals.mockReturnValue(new Promise(() => {}))
    renderChart()

    const loading = await screen.findByRole('status', { name: 'Loading financial trends' })
    expect((loading.firstElementChild as HTMLElement).style.height).toBe(`${CARD_HEIGHT}px`)
    // The footnote's bone holds its room with the footnote as it reads for revenue, the picker's first metric:
    // invisible, inside an aria-hidden bone, so no line names a metric before there is one.
    const held = screen.getByText('Annual figures from SEC filings (XBRL). Revenue by fiscal year.')
    expect(held).toHaveClass('invisible')
    expect(held.closest('[aria-hidden="true"]')).not.toBeNull()
    const shown = { ignore: '[aria-hidden="true"] *' }
    expect(screen.queryByText(/Annual figures from SEC filings/, shown)).toBeNull()
    expect(screen.queryByText('Sources & checks', shown)).toBeNull()
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('renders nothing once loaded for a filing with no facts', async () => {
    getFilingFundamentals.mockResolvedValue({ ticker: 'AAPL', company_name: 'Apple Inc.', concepts: [] })
    renderChart()

    await waitFor(() => expect(screen.queryByText('Financial trends')).not.toBeInTheDocument())
  })

  it('shows the optional subtitle when provided, and omits it by default', async () => {
    getFilingFundamentals.mockResolvedValue(RESP)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <FundamentalsTrendChart filingId={285} subtitle="AAPL · figures as reported in this 10-K" />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('AAPL · figures as reported in this 10-K')).toBeInTheDocument()

    // No subtitle prop → no context line.
    rerender(
      <QueryClientProvider client={qc}>
        <FundamentalsTrendChart filingId={285} />
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.queryByText('AAPL · figures as reported in this 10-K')).not.toBeInTheDocument(),
    )
  })

  it('offers the richer 2.6 metrics (cash-flow + working capital) as options when present', async () => {
    // Roadmap 2.6 (Phase A): the new concepts self-gate — they only appear when the response
    // carries them (i.e. once RICHER_FINANCIALS_ENABLED extracted them). Here they're present.
    getFilingFundamentals.mockResolvedValue({
      ticker: 'LLY',
      company_name: 'Eli Lilly',
      concepts: [
        { concept: 'revenue', unit: 'USD', points: [point(2023, 34, 'USD')] },
        { concept: 'investing_cash_flow', unit: 'USD', points: [point(2023, -5, 'USD')] },
        { concept: 'financing_cash_flow', unit: 'USD', points: [point(2023, -3, 'USD')] },
        { concept: 'current_assets', unit: 'USD', points: [point(2023, 30, 'USD')] },
        { concept: 'current_liabilities', unit: 'USD', points: [point(2023, 20, 'USD')] },
        { concept: 'working_capital', unit: 'USD', points: [point(2023, 10, 'USD')] },
        { concept: 'current_ratio', unit: 'pure', points: [point(2023, 1.5, 'pure')] },
      ],
    })
    renderChart()

    await metricPicker()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Revenue', 'Investing cash flow', 'Financing cash flow', 'Current assets', 'Current liabilities',
      'Working capital', 'Current ratio',
    ])
  })

  it('names every metric in sentence case as stored, and the footnote reads it at its start (E34)', async () => {
    const keys = [
      'revenue', 'net_interest_income', 'noninterest_income', 'premiums_earned', 'net_investment_income', 'net_income',
      'gross_profit', 'operating_income', 'operating_cash_flow', 'investing_cash_flow', 'financing_cash_flow',
      'free_cash_flow', 'eps_diluted', 'earnings_per_share', 'gross_margin', 'operating_margin', 'net_margin',
      'total_assets', 'current_assets', 'current_liabilities', 'working_capital', 'current_ratio', 'shareholders_equity',
    ]
    getFilingFundamentals.mockResolvedValue({
      ticker: 'JPM',
      company_name: 'JPMorgan Chase',
      concepts: keys.map((concept) => ({ concept, unit: 'USD', points: [point(2023, 10, 'USD')] })),
    })
    renderChart()

    const picker = await metricPicker()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Revenue', 'Net interest income', 'Non-interest income', 'Premiums earned', 'Net investment income', 'Net income',
      'Gross profit', 'Operating income', 'Operating cash flow', 'Investing cash flow', 'Financing cash flow',
      'Free cash flow', 'Diluted EPS', 'EPS', 'Gross margin', 'Operating margin', 'Net margin', 'Total assets',
      'Current assets', 'Current liabilities', 'Working capital', 'Current ratio', "Shareholders' equity",
    ])
    fireEvent.change(picker, { target: { value: 'free_cash_flow' } })
    expect(await screen.findByText(/Free cash flow by fiscal year\./)).toBeInTheDocument()
    // The values stop speaks the stored name too.
    expect(await screen.findByRole('slider', { name: 'Free cash flow chart values' })).toHaveAttribute('aria-valuetext', expect.stringContaining('. Free cash flow: $10.'))
  })

  it('fetches by filingId (roadmap B), not any company-wide endpoint', async () => {
    getFilingFundamentals.mockResolvedValue(RESP)
    renderChart(285, 'LLY · figures as reported in this 10-K')

    expect(await metricPicker()).toHaveValue('revenue')
    expect(screen.getByText('LLY · figures as reported in this 10-K')).toBeInTheDocument()
    expect(getFilingFundamentals).toHaveBeenCalledWith(285)
  })
})

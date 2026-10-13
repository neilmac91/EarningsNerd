import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import DataNotes, { DataNotesList } from '@/features/analysis/components/DataNotes'
import KpiStrip from '@/features/analysis/components/KpiStrip'
import SourceValue from '@/features/analysis/components/SourceValue'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { FactProvenance } from '@/features/analysis/lib/provenance'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import DataNotesLink from '@/features/analysis/components/DataNotesLink'
import { groupDataNotes } from '@/features/analysis/lib/dataNotes'
import { decodeDataNotes } from '@/features/analysis/lib/dataNotesContract'

const calculated: FactProvenance = {
  version: 1, method: 'calculated', validation: 'passed', reasons: [],
  formula: 'annual_revenue - nine_month_revenue', calculation_version: 'quarterly-v2',
  inputs: [{ concept: 'revenue', value: 134902000000, unit: 'USD', period_start: '2023-01-01', period_end: '2023-12-31', accession: '0001326801-24-000012', source_url: 'https://www.sec.gov/Archives/edgar/data/1326801/000132680124000012/' }],
}
const dataset: AnalysisDataset = {
  ticker: 'META', company_name: 'Meta Platforms', mode: 'quarterly', period_key: '2023Q3..2023Q4',
  dataset_version: 'quarterly-v2', snapshot_id: 'snapshot-a', data_as_of: '2024-02-02',
  periods: [{ key: '2023Q3', fiscal_year: 2023, fiscal_period: 'Q3', period_end: '2023-09-30' }, { key: '2023Q4', fiscal_year: 2023, fiscal_period: 'Q4', period_end: '2023-12-31' }],
  series: [{ concept: 'revenue', label: 'Revenue', unit: 'USD', percent: false, cagr: null, points: [
    { period: '2023Q3', value: 34146000000, reconciled: true, provenance: { ...calculated, method: 'reported', formula: null, inputs: [] } },
    { period: '2023Q4', period_end: '2023-12-31', value: 40111000000, reconciled: false, derived: true, provenance: calculated, qoq: 0.1747, qoq_reconciled: false, qoq_provenance: calculated },
  ] }], inflections: [],
}

function locatorDataset(bank = false): AnalysisDataset {
  const passed: FactProvenance = { ...calculated, method: 'reported', inputs: [], formula: null }
  const review: FactProvenance = { ...calculated, validation: 'needs_review', reasons: ['source_conflict'] }
  const periods = Array.from({ length: 8 }, (_, index) => ({
    key: `${2024 + Math.floor(index / 4)}Q${index % 4 + 1}`,
    fiscal_year: 2024 + Math.floor(index / 4), fiscal_period: `Q${index % 4 + 1}`,
    period_end: `${2024 + Math.floor(index / 4)}-${['03', '06', '09', '12'][index % 4]}-28`,
  }))
  const concepts = [bank ? 'net_interest_income' : 'revenue', 'net_income', 'free_cash_flow', 'net_margin', 'operating_margin']
  return { ...dataset, snapshot_id: 'locator-one', period_key: '2024Q1..2025Q4', periods,
    series: concepts.map((concept, seriesIndex) => ({
      concept, label: concept.replaceAll('_', ' ').replace(/^./, first => first.toUpperCase()),
      unit: concept.endsWith('margin') ? 'pure' : 'USD', percent: concept.endsWith('margin'), cagr: null,
      points: periods.map((period, index) => ({
        period: period.key,
        value: concept === 'free_cash_flow' && index === 7 ? null : concept === 'free_cash_flow' && index === 6 ? 0 : 100,
        provenance: passed,
        qoq: (seriesIndex === 0 && index === 0) || (concept === 'free_cash_flow' && index === 6) || concept === 'operating_margin' ? null : 0,
        qoq_provenance: seriesIndex === 0 && index === 7 ? review : passed,
        yoy: seriesIndex === 0 ? index === 5 ? 'nm' : 0 : concept === 'free_cash_flow' && index === 6 ? 0 : index === 7 ? 'nm' : null,
        yoy_provenance: review,
      })),
    })),
  }
}

describe('Financial origin and source checks', () => {
  it.each([false, true])('locates distinct comparisons using actual headline, growth-chart and fallback membership (bank=%s)', async bank => {
    const report = locatorDataset(bank)
    const view = (input: AnalysisDataset) => <DataNotesProvider dataset={input}><KpiStrip dataset={input} /><DataNotes dataset={input} /><MetricsTable dataset={input} /></DataNotesProvider>
    const { container, rerender } = render(view(report))
    const note = document.getElementById('analysis-data-note-a')!
    const locator = () => within(note).getByText(/^13 year-over-year comparisons carry this note/)
    expect(locator()).toHaveTextContent(`The headline cards show 4. The ${bank ? 'net interest income' : 'revenue'} growth chart shows 7. The table shows 3 as its labelled fallback. Exports carry all 13.`)
    expect(within(note).getByText(/^1 quarter-over-quarter comparison carries/)).toHaveTextContent('The table shows 1.')
    expect(within(note).getByText(/^1 quarter-over-quarter comparison carries/)).not.toHaveTextContent('headline')
    const headlines = [...container.querySelectorAll('[data-analysis-kpi]')]
    expect(headlines).toHaveLength(4)
    expect(headlines.map(tile => tile.querySelector('dt')?.textContent)).not.toContain('Operating margin')
    expect(within(headlines[2] as HTMLElement).getByRole('button', { name: /Free cash flow, Q3 2025: \$0.*comparison carries data note a/ })).toBeInTheDocument()
    expect(headlines[2]).toHaveTextContent('latest available')
    const summary = container.querySelector('[data-analysis-data-notes] > details > summary')!
    const originalSummary = summary.textContent
    expect(summary).toHaveTextContent('14 comparisons carry note a')
    expect(screen.getByRole('button', { name: 'Review data notes a, b' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Newest 6' }))
    expect(locator()).toHaveTextContent('The table shows 3 as its labelled fallback (2 in the 6 quarters shown).')
    expect(summary.textContent).toBe(originalSummary)
    await userEvent.click(screen.getByRole('button', { name: 'Earliest 6' }))
    expect(screen.getByRole('button', { name: 'Review data notes a' })).toBeInTheDocument()
    expect(locator()).toHaveTextContent('The table shows 3 as its labelled fallback (1 in the 6 quarters shown).')
    expect(within(note).getByText(/^1 quarter-over-quarter comparison carries/)).toHaveTextContent('The table shows 1 (0 in the 6 quarters shown).')
    expect(summary.textContent).toBe(originalSummary)
    rerender(view({ ...report, snapshot_id: 'locator-two' }))
    expect(screen.getByRole('status')).toHaveTextContent('Showing 8 of 8 quarters')
    expect(locator()).not.toHaveTextContent('quarters shown')
    expect(screen.getByRole('button', { name: 'All 8' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps citation-only and illustrative note lists free of invented report surface claims', () => {
    const report = locatorDataset()
    const { rerender, container } = render(<DataNotesList notes={groupDataNotes(report).notes} />)
    expect(container).toHaveTextContent('13 YoY comparisons')
    expect(container).not.toHaveTextContent(/headline|growth chart|table shows|Exports carry/)
    rerender(<DataNotes dataset={report} sample />)
    expect(container).not.toHaveTextContent(/headline|growth chart|table shows|Exports carry/)
  })

  it('lists visible table note letters in admitted report order, including unavailable cells', async () => {
    const report = locatorDataset()
    const grouped = groupDataNotes(report)
    grouped.notes = grouped.notes.map((note, index) => ({ ...note, letter: ['z', 'a'][index], id: `analysis-data-note-${['z', 'a'][index]}` }))
    report.data_notes = decodeDataNotes({ version: 1, notes: grouped.notes, totals: grouped.totals }, report)
    render(<MetricsTable dataset={report} />)
    expect(screen.getByRole('button', { name: 'Review data notes z, a' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Earliest 6' }))
    expect(screen.getByRole('button', { name: 'Review data notes z' })).toBeInTheDocument()
  })

  it('counts annual CAGR and percentage-point windows independently of the table period window', async () => {
    const report = locatorDataset()
    report.mode = 'annual'
    report.period_key = 'FY2018..FY2025'
    report.periods = report.periods.map((period, index) => ({ ...period, key: `FY${2018 + index}`, fiscal_year: 2018 + index, fiscal_period: 'FY' }))
    report.series = [report.series[0], report.series[3]].map(series => ({ ...series,
      points: series.points.map((point, index) => ({ ...point, period: report.periods[index].key, yoy: null })),
      ...(series.percent ? { window_pp: 0, window_pp_range: 'FY2018..FY2025', window_pp_reconciled: false }
        : { cagr: 0, cagr_window: 'FY2020..FY2025', cagr_reconciled: false }),
    }))
    render(<DataNotesProvider dataset={report}><DataNotes dataset={report} /><MetricsTable dataset={report} /></DataNotesProvider>)
    const note = document.getElementById('analysis-data-note-a')!
    expect(note).toHaveTextContent('Revenue CAGR (FY2020 – FY2025)')
    for (const basis of ['CAGR', 'window percentage-point']) {
      expect(within(note).getByText(`1 ${basis} comparison carries this note. The headline cards show 1. The table shows 1. Exports carry all 1.`)).toBeInTheDocument()
    }
    await userEvent.click(screen.getByRole('button', { name: 'Newest 6' }))
    expect(note).not.toHaveTextContent('years shown')
    expect(screen.getByRole('columnheader', { name: 'FY2018–FY2025 CAGR' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review data notes a' })).toBeInTheDocument()
  })

  it('names a comparison note once in the source control and identifies the recorded input carrying it', async () => {
    const report = structuredClone(dataset)
    const prior: FactProvenance = { ...calculated, method: 'reported', formula: null, inputs: [], validation: 'needs_review', reasons: ['source_conflict'] }
    report.series[0].points[1].yoy = 0.1
    report.series[0].points[1].yoy_provenance = { ...calculated, validation: 'needs_review', reasons: ['source_conflict'], inputs: [
      { concept: 'revenue', value: 100, period_end: '2022-12-31', provenance: prior },
      { concept: 'revenue', value: 110, period_end: '2023-12-31', provenance: { ...prior, validation: 'passed', reasons: [] } },
    ] }
    report.series[0].points[1].qoq = null
    const { container } = render(<DataNotesProvider dataset={report}><KpiStrip dataset={report} /><MetricsTable dataset={report} /></DataNotesProvider>)
    const controls = screen.getAllByRole('button', { name: /Revenue, Q4 2023:.*comparison carries data note a/ })
    expect(controls).toHaveLength(2)
    expect([...container.querySelectorAll('.sr-only')].filter(node => /data note/.test(node.textContent ?? ''))).toHaveLength(0)
    await userEvent.click(controls[1])
    expect(screen.getByRole('dialog')).toHaveTextContent('Carries note a: it uses revenue (period ended 31 Dec 2022), which needs review.')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('31 Dec 2023), which needs review')
  })

  it('does not invent an inherited input or repeat a shared figure/comparison note', async () => {
    const report = structuredClone(dataset)
    const review: FactProvenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'], inputs: [] }
    report.series[0].points[1].provenance = review
    report.series[0].points[1].qoq_provenance = review
    render(<MetricsTable dataset={report} />)
    const control = screen.getByRole('button', { name: /Revenue, Q4 2023:.*data note a, also applies to the comparison/ })
    expect(control.getAttribute('aria-label')?.match(/data note a/g)).toHaveLength(1)
    await userEvent.click(control)
    expect(screen.getByRole('dialog')).toHaveTextContent('Carries note a. The recorded inputs do not identify which input carries this note.')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('it uses')
  })

  it.each([true, false])('uses admitted server letters and explanations with report context: %s', (withProvider) => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    const grouped = groupDataNotes(flagged)
    grouped.notes[0] = { ...grouped.notes[0], letter: 'z', id: 'analysis-data-note-z', message: 'The server retained the original currency concern.' }
    const admitted = Object.assign(flagged, { data_notes: decodeDataNotes({ version: 1, notes: grouped.notes, totals: grouped.totals }, flagged) })
    const children = <><DataNotes dataset={admitted} /><MetricsTable dataset={admitted} /></>
    render(withProvider ? <DataNotesProvider dataset={admitted}>{children}</DataNotesProvider> : children)
    expect(screen.getByRole('button', { name: /Revenue, Q4 2023:.*comparison carries data note z/ })).toBeInTheDocument()
    expect(document.getElementById('analysis-data-note-z')).toHaveTextContent('The server retained the original currency concern.')
    expect(screen.getByText(/1 comparison carries note z/)).toBeInTheDocument()
    expect(screen.getByText(/No figures need review · 2 checked/)).toBeInTheDocument()
    expect(document.getElementById('analysis-data-note-a')).not.toBeInTheDocument()
  })

  it('presents a validated Q4 calculation and its growth without false warnings, with inspectable operands', async () => {
    const user = userEvent.setup()
    render(<><DataNotes dataset={dataset} /><MetricsTable dataset={dataset} /></>)
    expect(screen.queryByText(/Source check needed|Growth source check needed|Unverified/)).not.toBeInTheDocument()
    expect(screen.getByText('† calculated')).not.toHaveClass('bg-warning-light/10')
    const value = screen.getByRole('button', { name: /Revenue, Q4 2023.*View source/ })
    value.focus()
    await user.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog', { name: 'Revenue · Q4 2023' })
    expect(within(dialog).getByText(/Calculated by EarningsNerd from recorded inputs/)).toBeInTheDocument()
    expect(within(dialog).getAllByText('Calculated from reported figures with compatible periods and units.')).toHaveLength(2)
    expect(within(dialog).getByText('Quarter ended 31 Dec 2023.')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('heading').map((heading) => heading.textContent)).toEqual(['Revenue · Q4 2023', 'Checks', 'Method', 'Inputs and source filings', 'QoQ comparison'])
    expect(within(dialog).getAllByText(/134,902,000,000 USD/)).toHaveLength(2)
    for (const link of within(dialog).getAllByRole('link', { name: /Open original SEC filing for revenue/ })) {
      expect(link).toHaveAttribute('href', calculated.inputs[0].source_url)
    }
    await user.keyboard('{Escape}')
    expect(value).toHaveFocus()
    await user.click(screen.getByRole('button', { name: /Revenue, Q3 2023.*View source/ }))
    const reported = screen.getByRole('dialog')
    expect(reported).toHaveTextContent('Taken from the company’s XBRL data as filed with the SEC.')
    expect(reported).not.toHaveTextContent('Calculated from reported figures with compatible periods and units.')
  })

  it('retains genuine exceptions and explains their reason even if a legacy boolean is true', () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[0].provenance!.validation = 'needs_review'
    flagged.series[0].points[0].provenance!.reasons = ['unit_mismatch']
    render(<><DataNotes dataset={flagged} /><MetricsTable dataset={flagged} /></>)
    expect(screen.getByRole('button', { name: /Revenue, Q3 2023:.*data note a/ }).querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    const note = screen.getByText(/The source inputs use different units or currencies/).closest('li')
    expect(note).toHaveTextContent('Revenue (Q3 2023)')
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it.each([
    { label: 'legacy true', quality: { reconciled: true }, status: 'No validation record' },
    { label: 'legacy false', quality: { reconciled: false }, status: 'Needs review' },
    { label: 'absent validation', quality: {}, status: 'No validation record' },
    { label: 'populated figure with unavailable validation', quality: { provenance: { ...calculated, method: 'unknown' as const, validation: 'unavailable' as const, reasons: ['legacy_unknown'], formula: null, inputs: [] } }, status: 'No validation record' },
  ])('retains $label as $status without a passed-check claim', async ({ quality, status }) => {
    render(<SourceValue point={{ period: '2024Q4', value: 8.02, ...quality }} label="EPS">$8.02</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    expect(screen.getByText(status)).toBeInTheDocument()
    expect(screen.queryByText(/Automated checks passed/)).not.toBeInTheDocument()
  })

  it('keeps an unknown comparison distinct from the passed figures and names its letter at rest', () => {
    const unknown = structuredClone(dataset)
    unknown.series[0].points[1].qoq_provenance = null
    unknown.series[0].points[1].qoq_reconciled = true
    render(<DataNotes dataset={unknown} />)
    const summary = document.querySelector('[data-analysis-data-notes] > details > summary')!
    expect(summary).toHaveTextContent('No figures need review · 2 checked')
    expect(summary).toHaveTextContent('1 comparison has no validation record (a)')
    expect(summary).not.toHaveTextContent('1 figure has no validation record')
    expect(summary.querySelector('[class*="text-brand"]')).toBeNull()
  })

  it('shows a legacy margin in financial units with its exact saved value and absent lineage', async () => {
    render(<SourceValue point={{ period: '2026Q2', value: 26.065360767092647, unit: 'pure', provenance: { ...calculated, inputs: [], formula: null, validation: 'needs_review', reasons: ['legacy_calculation'] } }} label="Net margin" concept="net_margin">26.1%</SourceValue>)
    const trigger = screen.getByRole('button', { name: /Net margin, Q2 2026: 26.1%/ })
    trigger.focus()
    await userEvent.keyboard(' ')
    const dialog = screen.getByRole('dialog', { name: 'Net margin · Q2 2026' })
    expect(dialog).toHaveTextContent('As stored: 26.065360767092645%')
    expect(dialog).toHaveTextContent('Source lineage is not recorded for this saved calculation.')
    expect(within(dialog).getByText('Calculated figure.')).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent('from recorded inputs')
    expect(dialog).not.toHaveTextContent('from reported inputs')
    expect(dialog).toHaveTextContent('Needs review')
    expect(dialog).not.toHaveTextContent('pure')
    expect(dialog).not.toHaveTextContent('scheduled')
    expect(within(dialog).queryByRole('link')).not.toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
  })

  it.each([
    { label: 'Revenue CAGR', concept: 'revenue', value: 0.123456789, unit: 'growth fraction', display: '+12.3%', exact: '0.123456789 (growth fraction)' },
    { label: 'Net margin window change', concept: 'net_margin', value: -1.23456789, unit: 'percentage points', display: '-1.2pp', exact: '-1.23456789 percentage points' },
  ])('presents $label in comparison units while retaining its raw value and source concern', async ({ label, concept, value, unit, display, exact }) => {
    const provenance: FactProvenance = { ...calculated, formula: null, inputs: [], validation: 'needs_review', reasons: ['legacy_calculation'] }
    render(<SourceValue point={{ period: 'FY2020..FY2024', value, unit, provenance }} label={label} concept={concept}>{display}</SourceValue>)
    const trigger = screen.getByRole('button', { name: `${label}, FY2020..FY2024: ${display}, calculated. View source and calculation` })
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(display, { exact: false })).toBeInTheDocument()
    expect(dialog).toHaveTextContent(`As stored: ${exact}`)
    expect(dialog).toHaveTextContent('Needs review')
    expect(dialog).not.toHaveTextContent('Automated checks passed')
    expect(dialog).toHaveTextContent('Its inputs need review.')
  })

  it('substitutes margin operands by concept rather than input order, and retains real source links', async () => {
    const provenance: FactProvenance = { ...calculated, formula: '100 * net_income / revenue', inputs: [
      { ...calculated.inputs[0], concept: 'revenue', value: 60801000000 },
      { ...calculated.inputs[0], concept: 'net_income', value: 15848000000 },
    ] }
    const { rerender } = render(<SourceValue point={{ period: '2026Q2', value: 26.065360767092647, unit: 'pure', provenance }} label="Net margin" concept="net_margin">26.1%</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('15,848,000,000 ÷ 60,801,000,000 × 100 = 26.065360767092645%')
    expect(within(dialog).getAllByRole('link')).toHaveLength(2)
    for (const link of within(dialog).getAllByRole('link')) expect(link).toHaveAttribute('href', calculated.inputs[0].source_url)
    rerender(<SourceValue point={{ period: '2026Q2', value: 27, unit: 'pure', provenance: { ...provenance, validation: 'needs_review', reasons: ['source_conflict'] } }} label="Net margin" concept="net_margin">27.0%</SourceValue>)
    expect(dialog).toHaveTextContent('Recorded inputs: 15,848,000,000 ÷ 60,801,000,000 × 100')
    expect(dialog).not.toHaveTextContent('× 100 = 27%')
    expect(dialog).toHaveTextContent('Available sources disagree on this figure.')
  })

  it('retains the nested reported operands of a quarterly free-cash-flow calculation', async () => {
    const reported: FactProvenance = { ...calculated, method: 'reported', formula: null, inputs: [] }
    const provenance: FactProvenance = { ...calculated, formula: 'operating_cash_flow - abs(capital_expenditures)', inputs: [
      { concept: 'operating_cash_flow', value: 2000000000, unit: 'EUR', provenance: { ...calculated, formula: 'YTD6 - Q1', inputs: [
        { ...calculated.inputs[0], concept: 'operating_cash_flow', unit: 'EUR', value: 3000000000, provenance: reported },
        { ...calculated.inputs[0], concept: 'operating_cash_flow', unit: 'EUR', value: 1000000000, provenance: reported },
      ] } },
      { ...calculated.inputs[0], concept: 'capital_expenditures', unit: 'EUR', value: -500000000, provenance: reported },
    ] }
    render(<SourceValue point={{ period: '2026Q2', value: 1500000000, unit: 'EUR', provenance }} label="Free cash flow" concept="free_cash_flow">€1.5B</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('€1.5B')
    expect(dialog).toHaveTextContent('2,000,000,000 − |-500,000,000| = 1,500,000,000 EUR')
    expect(dialog).toHaveTextContent('3,000,000,000 EUR')
    expect(dialog).toHaveTextContent('1,000,000,000 EUR')
    expect(within(dialog).getAllByRole('link')).toHaveLength(3)
    expect(dialog).toHaveTextContent('It excludes finance lease principal payments')
    expect(dialog).not.toHaveTextContent('USD')
  })

  it('shows unavailable EPS with its reason and no invented figure', async () => {
    const missing = structuredClone(dataset)
    missing.series[0].points[1] = { period: '2023Q4', value: null, provenance: { ...calculated, validation: 'unavailable', reasons: ['eps_requires_reported_quarter'] } }
    render(<MetricsTable dataset={missing} />)
    await userEvent.click(screen.getByRole('button', { name: /Q4 2023: unavailable/ }))
    expect(screen.getByText('A reported quarterly earnings-per-share figure is unavailable.')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toHaveTextContent('Unavailable · Note a')
    expect(screen.getByRole('dialog')).toHaveTextContent('Changes that need this quarter are not shown.')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('Withheld')
    expect(screen.queryByText('$40.1B')).not.toBeInTheDocument()
  })

  it('keeps a comparison-only concern inspectable without marking the current value as needing review', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    render(<DataNotesProvider dataset={flagged}><DataNotes dataset={flagged} /><MetricsTable dataset={flagged} /></DataNotesProvider>)
    expect(screen.getByText(/1 comparison carries note a/)).toBeInTheDocument()
    expect(screen.getByText(/No figures need review · 2 checked/)).toBeInTheDocument()
    expect(screen.getByText(/Comparisons: Revenue QoQ \(Q4 2023\)/)).toBeInTheDocument()
    const figure = screen.getByRole('button', { name: /Revenue, Q4 2023:.*comparison carries data note a/ })
    expect(figure.querySelector('[data-note-kind="review"]')).not.toBeInTheDocument()
    await userEvent.click(figure)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · Q4 2023' })
    expect(within(dialog).getByRole('heading', { name: 'QoQ comparison' })).toBeInTheDocument()
    expect(within(dialog).getByText('Needs review · Note a')).toBeInTheDocument()
    expect(within(dialog).getByText(/The source inputs use different units or currencies/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Calculated by EarningsNerd from recorded inputs/)).toBeInTheDocument()
  })

  it('explains an absent metric-period slot with the same unavailable note counted in the report', async () => {
    const missing = structuredClone(dataset)
    missing.series[0].points.pop()
    render(<DataNotesProvider dataset={missing}><DataNotes dataset={missing} /><MetricsTable dataset={missing} /></DataNotesProvider>)
    expect(screen.getByText(/1 unavailable/)).toBeInTheDocument()
    const value = screen.getByRole('button', { name: /Revenue, Q4 2023: unavailable, data note a/ })
    expect(value.querySelector('[data-note-kind="unavailable"]')).toHaveTextContent('a')
    await userEvent.click(value)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · Q4 2023' })
    expect(within(dialog).getByText(/Not available in this dataset/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/Automated checks passed/)).not.toBeInTheDocument()
  })

  it('opens and focuses the report note from its keyboard-activated note control', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    render(<DataNotesProvider dataset={flagged}><DataNotes dataset={flagged} /><DataNotesLink notes={groupDataNotes(flagged).notes} /></DataNotesProvider>)
    const note = document.getElementById('analysis-data-note-a')!
    const disclosure = note.closest('details')!
    expect(disclosure).not.toHaveAttribute('open')
    screen.getByRole('button', { name: 'Review data notes a' }).focus()
    await userEvent.keyboard('{Enter}')
    expect(disclosure).toHaveAttribute('open')
    expect(note).toHaveFocus()
    expect(note).toHaveTextContent('1 QoQ comparison')
    expect(note).toHaveTextContent('Comparisons: Revenue QoQ (Q4 2023)')
    expect(note).toHaveTextContent('The source inputs use different units or currencies')
  })
})

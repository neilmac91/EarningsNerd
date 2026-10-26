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
  it.each([false, true])('names a concern on growth figures alone by its places and words, the headline cards unchanged (bank=%s)', async bank => {
    const report = locatorDataset(bank)
    const view = (input: AnalysisDataset) => <DataNotesProvider dataset={input}><KpiStrip dataset={input} /><DataNotes dataset={input} /><MetricsTable dataset={input} /></DataNotesProvider>
    const { container, rerender } = render(view(report))
    const note = document.getElementById('analysis-data-note-a')!
    // The detail counts the note's growth figures; it no longer says where on the page each appears.
    expect(note).toHaveTextContent('1 QoQ comparison · 13 YoY comparisons.')
    expect(note).not.toHaveTextContent(/carry this note|headline cards|growth chart shows|table shows|Exports carry/)
    const headlines = [...container.querySelectorAll('[data-analysis-kpi]')]
    expect(headlines).toHaveLength(4)
    expect(headlines.map(tile => tile.querySelector('dt')?.textContent)).not.toContain('Operating margin')
    expect(within(headlines[2] as HTMLElement).getByRole('button', { name: /Free cash flow, Q3 2025: \$0.*comparison carries data note a/ })).toBeInTheDocument()
    expect(headlines[2]).toHaveTextContent('latest available')
    const summary = container.querySelector('[data-analysis-data-notes] > details > summary')!
    const originalSummary = summary.textContent
    // A note only on growth figures is named by them: the first three metrics, then a count of the rest.
    const topLine = bank ? 'Net interest income' : 'Revenue'
    expect(summary.querySelector('[data-note-letter="a"]')).not.toBeNull()
    expect(summary).toHaveTextContent(`${topLine} YoY Q1 2024, Q2 2024, Q3 2024, Q4 2024, Q1 2025, Q2 2025, Q3 2025, Q4 2025; ${topLine} QoQ Q4 2025; Net income YoY Q4 2025 and 3 more: Available sources disagree on this figure`)
    expect(summary).toHaveTextContent('1 not in our data, shown as a dash')
    // b is free cash flow's gap, which marks nothing.
    expect(screen.getByRole('button', { name: 'Review data notes a' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Table window' })).not.toBeInTheDocument()
    rerender(view({ ...report, snapshot_id: 'locator-two' }))
    expect(container.querySelector('[data-analysis-data-notes] > details > summary')?.textContent).toBe(originalSummary)
  })

  it('keeps citation-only and illustrative note lists free of invented report surface claims', () => {
    const report = locatorDataset()
    const { rerender, container } = render(<DataNotesList notes={groupDataNotes(report).notes} />)
    expect(container).toHaveTextContent('13 YoY comparisons')
    expect(container).not.toHaveTextContent(/headline|growth chart|table shows|Exports carry/)
    rerender(<DataNotes dataset={report} sample />)
    expect(container).not.toHaveTextContent(/headline|growth chart|table shows|Exports carry/)
  })

  it("gives a live report its reference and a sample none: a saved run's snapshot resolves nowhere a reader can check (#1457)", () => {
    const report = { ...locatorDataset(), dataset_version: 'quarterly-v2', data_as_of: '2026-10-20T18:38:47.008084Z' }
    const { rerender, container } = render(<DataNotes dataset={report} />)
    const references = () => [...container.querySelectorAll('summary')].filter((summary) => summary.textContent === 'Report reference').length
    expect(references(), 'Report references in a live report').toBe(1)
    expect(container).toHaveTextContent('quarterly-v2 · locator-one')
    rerender(<DataNotes dataset={report} sample />)
    expect(references(), 'Report references in a sample').toBe(0)
    expect(container.textContent?.includes('locator-one'), 'the sample shows its snapshot id').toBe(false)
    // The as-of line stays, as its day, written as a live report writes it (analysis-source-date.spec.tsx pins the
    // day in a fixed zone; this case reads it in the runner's).
    expect(container).toHaveTextContent(/Source data as of October 2[01], 2026\./)
    expect(container.textContent).not.toContain('2026-10-20T')
  })

  it("lists the table's marked letters in admitted report order, leaving out a gap's note", () => {
    const report = locatorDataset()
    const grouped = groupDataNotes(report)
    grouped.notes = grouped.notes.map((note, index) => ({ ...note, letter: ['z', 'a'][index], id: `analysis-data-note-${['z', 'a'][index]}` }))
    report.data_notes = decodeDataNotes({ version: 1, notes: grouped.notes, totals: grouped.totals }, report)
    render(<MetricsTable dataset={report} />)
    expect(screen.getByRole('button', { name: 'Review data notes z' })).toBeInTheDocument()
  })

  it('counts annual CAGR and percentage-point windows once each, beside every period of the table', () => {
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
    expect(note).toHaveTextContent('Revenue CAGR (FY2020–FY2025)')
    expect(note).toHaveTextContent('1 CAGR comparison · 1 window percentage-point comparison.')
    expect(note).not.toHaveTextContent('years shown')
    expect(screen.getAllByRole('columnheader')).toHaveLength(report.periods.length + 2)
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
    expect(screen.getByRole('dialog')).toHaveTextContent('Carries note a. The recorded inputs do not identify which input this note comes from.')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('it uses')
  })

  it.each([true, false])('uses admitted server letters and explanations with report context: %s', (withProvider) => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    const grouped = groupDataNotes(flagged)
    grouped.notes[0] = { ...grouped.notes[0], letter: 'z', id: 'analysis-data-note-z', message: 'The server retained the original currency concern.' }
    const admitted = Object.assign(flagged, { data_notes: decodeDataNotes({ version: 1, notes: grouped.notes, totals: grouped.totals }, flagged) })
    const children = <><DataNotes dataset={admitted} /><MetricsTable dataset={admitted} /></>
    const { container } = render(withProvider ? <DataNotesProvider dataset={admitted}>{children}</DataNotesProvider> : children)
    expect(screen.getByRole('button', { name: /Revenue, Q4 2023:.*comparison carries data note z/ })).toBeInTheDocument()
    expect(document.getElementById('analysis-data-note-z')).toHaveTextContent('The server retained the original currency concern.')
    // The summary takes the server's words, up to the first clause.
    expect(container.querySelector('[data-analysis-data-notes] summary')).toHaveTextContent('Revenue QoQ Q4 2023: The server retained the original currency concern')
    expect(screen.getByText(/No figures need review · 2 checked/)).toBeInTheDocument()
    expect(document.getElementById('analysis-data-note-a')).not.toBeInTheDocument()
  })

  it('presents a validated Q4 calculation and its growth without false warnings, with inspectable operands', async () => {
    const user = userEvent.setup()
    const { container } = render(<><DataNotes dataset={dataset} /><MetricsTable dataset={dataset} /></>)
    expect(screen.queryByText(/Source check needed|Growth source check needed|Unverified/)).not.toBeInTheDocument()
    // A calculation is not a concern: no † label, and nothing on the table or in its fine print takes warning ink.
    expect(screen.queryByText(/† calculated/)).not.toBeInTheDocument()
    expect(container.querySelector('[class*="text-warning"]')).toBeNull()
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
    expect(reported).toHaveTextContent('Taken from the figures the company filed with the SEC (its XBRL data).')
    expect(reported).not.toHaveTextContent('Calculated from reported figures with compatible periods and units.')
  })

  it('retains genuine exceptions and explains their reason even if a legacy boolean is true', () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[0].provenance!.validation = 'needs_review'
    flagged.series[0].points[0].provenance!.reasons = ['unit_mismatch']
    render(<><DataNotes dataset={flagged} /><MetricsTable dataset={flagged} /></>)
    expect(screen.getByRole('button', { name: /Revenue, Q3 2023:.*data note a/ }).querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    const note = document.getElementById('analysis-data-note-a')!
    expect(note).toHaveTextContent('The source inputs use different units or currencies')
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

  it('keeps an unknown comparison distinct from the passed figures and counts it at rest', () => {
    const unknown = structuredClone(dataset)
    unknown.series[0].points[1].qoq_provenance = null
    unknown.series[0].points[1].qoq_reconciled = true
    render(<DataNotes dataset={unknown} />)
    const summary = document.querySelector('[data-analysis-data-notes] > details > summary')!
    expect(summary).toHaveTextContent('No figures need review · 2 checked')
    expect(summary).toHaveTextContent('1 growth figure with no check recorded')
    expect(summary).not.toHaveTextContent('1 figure with no check recorded')
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
    const trigger = screen.getByRole('button', { name: `${label}, FY2020–FY2024: ${display}, calculated. View source and calculation` })
    trigger.focus()
    await userEvent.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent(`${label} · FY2020–FY2024`)
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

  it('substitutes current-ratio operands by concept when their input order is reversed', async () => {
    const provenance: FactProvenance = { ...calculated, formula: 'current_assets / current_liabilities', inputs: [
      { ...calculated.inputs[0], concept: 'current_liabilities', value: 2000000000 },
      { ...calculated.inputs[0], concept: 'current_assets', value: 2500000000 },
    ] }
    render(<SourceValue point={{ period: '2023Q4', value: 1.25, unit: 'pure', provenance }} label="Current ratio" concept="current_ratio">1.25×</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('Current assets ÷ current liabilities')
    expect(dialog).toHaveTextContent('2,500,000,000 ÷ 2,000,000,000 = 1.25 (ratio)')
    expect(dialog).toHaveTextContent('As stored: 1.25 (ratio)')
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
    // A gap's note marks nothing, so the dialog names no letter; its reason is above.
    expect(screen.getByRole('dialog')).toHaveTextContent('Unavailable')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('Note a')
    expect(screen.getByRole('dialog')).toHaveTextContent('Changes that need this quarter are not shown.')
    expect(screen.getByRole('dialog')).not.toHaveTextContent('Withheld')
    expect(screen.queryByText('$40.1B')).not.toBeInTheDocument()
  })

  it('keeps a comparison-only concern inspectable without marking the current value as needing review', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    render(<DataNotesProvider dataset={flagged}><DataNotes dataset={flagged} /><MetricsTable dataset={flagged} /></DataNotesProvider>)
    const summary = document.querySelector('[data-analysis-data-notes] summary')!
    expect(summary).toHaveTextContent('Revenue QoQ Q4 2023: The source inputs use different units or currencies')
    expect(summary).toHaveTextContent('No figures need review · 2 checked')
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
    expect(screen.getByText(/1 not in our data, shown as a dash/)).toBeInTheDocument()
    // The gap shows its dash; its note is counted and listed, and marks nothing (D-061).
    const value = screen.getByRole('button', { name: /^Revenue, Q4 2023: unavailable\. View source/ })
    expect(value.querySelector('[data-note-kind]')).toBeNull()
    expect(document.getElementById('analysis-data-note-a')).toHaveTextContent('Not available in this dataset.')
    await userEvent.click(value)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · Q4 2023' })
    expect(within(dialog).getByText(/Not available in this dataset/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/Automated checks passed/)).not.toBeInTheDocument()
  })

  it("keeps a legacy calculation's note in its dialog and the data notes, with no letter beside the figure (D-061)", async () => {
    const legacy = structuredClone(dataset)
    legacy.series[0].points[1].provenance = { ...calculated, inputs: [], formula: null, validation: 'needs_review', reasons: ['legacy_calculation'] }
    legacy.series[0].points[1].qoq_provenance = { ...calculated, validation: 'passed' }
    const { container } = render(<DataNotesProvider dataset={legacy}><DataNotes dataset={legacy} /><MetricsTable dataset={legacy} /></DataNotesProvider>)
    const figure = screen.getByRole('button', { name: /^Revenue, Q4 2023: \$40\.1B, calculated\. View source/ })
    expect(figure.querySelector('[data-note-letter]')).toBeNull()
    expect(screen.queryByRole('button', { name: /Review data notes/ })).not.toBeInTheDocument()
    const summary = container.querySelector('[data-analysis-data-notes] summary')!
    expect(summary).not.toHaveTextContent('No figures need review')
    expect(summary.querySelector('[data-note-letter]')).toBeNull()
    const note = document.getElementById('analysis-data-note-a')!
    expect(note).toHaveTextContent('This saved calculation predates the current source checks.')
    expect(note).toHaveTextContent('Revenue (Q4 2023)')
    expect(note).toHaveTextContent('1 figure.')
    await userEvent.click(figure)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · Q4 2023' })
    // The figure's own checks: never passed, the note's words in full, no letter and no warning ink.
    const checks = within(dialog).getByRole('heading', { name: 'Checks' }).closest('section')!
    expect(within(checks).getByText('Needs review')).not.toHaveClass('text-warning-light')
    expect(checks).not.toHaveTextContent('Automated checks passed')
    expect(checks).not.toHaveTextContent('Note a')
    expect(checks).toHaveTextContent('This saved calculation predates the current source checks. Its inputs need review.')
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

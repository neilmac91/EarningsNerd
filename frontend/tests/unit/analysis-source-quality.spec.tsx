import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import DataNotes from '@/features/analysis/components/DataNotes'
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
    { period: '2023Q4', value: 40111000000, reconciled: false, derived: true, provenance: calculated, qoq: 0.1747, qoq_reconciled: false, qoq_provenance: calculated },
  ] }], inflections: [],
}

describe('Financial origin and source checks', () => {
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
    expect(screen.getByText(/1 comparison needs review/)).toBeInTheDocument()
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
    expect(within(dialog).getAllByText(/134,902,000,000 USD/)).toHaveLength(2)
    for (const link of within(dialog).getAllByRole('link', { name: 'Open original SEC filing' })) {
      expect(link).toHaveAttribute('href', calculated.inputs[0].source_url)
    }
    await user.keyboard('{Escape}')
    expect(value).toHaveFocus()
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

  it('does not promote legacy true or absent quality into a passed validation claim', async () => {
    render(<SourceValue point={{ period: '2024Q4', value: 8.02, reconciled: true }} label="EPS">$8.02</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    expect(screen.getByText(/No validation record/)).toBeInTheDocument()
    expect(screen.queryByText(/Automated source checks passed/)).not.toBeInTheDocument()
  })

  it('shows a legacy margin in financial units with its exact saved value and absent lineage', async () => {
    render(<SourceValue point={{ period: '2026Q2', value: 26.065360767092647, unit: 'pure', provenance: { ...calculated, inputs: [], formula: null, validation: 'needs_review', reasons: ['legacy_calculation'] } }} label="Net margin" concept="net_margin">26.1%</SourceValue>)
    const trigger = screen.getByRole('button', { name: /Net margin, Q2 2026: 26.1%/ })
    trigger.focus()
    await userEvent.keyboard(' ')
    const dialog = screen.getByRole('dialog', { name: 'Net margin · Q2 2026' })
    expect(dialog).toHaveTextContent('Exact 26.065360767092645%')
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
    expect(dialog).toHaveTextContent(`Exact ${exact}`)
    expect(dialog).toHaveTextContent('Needs review')
    expect(dialog).not.toHaveTextContent('Automated source checks passed')
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
    expect(screen.queryByText('$40.1B')).not.toBeInTheDocument()
  })

  it('keeps a comparison-only concern inspectable without marking the current value as needing review', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    render(<DataNotesProvider dataset={flagged}><DataNotes dataset={flagged} /><MetricsTable dataset={flagged} /></DataNotesProvider>)
    expect(screen.getByText(/1 comparison needs review/)).toBeInTheDocument()
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
    expect(within(dialog).queryByText(/Automated source checks passed/)).not.toBeInTheDocument()
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

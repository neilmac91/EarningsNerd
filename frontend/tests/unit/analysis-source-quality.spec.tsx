import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import SourcesMethods from '@/features/analysis/components/SourcesMethods'
import SourceValue from '@/features/analysis/components/SourceValue'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { FactProvenance } from '@/features/analysis/lib/provenance'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'

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
  it('presents a validated Q4 calculation and its growth without false warnings, with inspectable operands', async () => {
    const user = userEvent.setup()
    render(<><SourcesMethods dataset={dataset} /><MetricsTable dataset={dataset} /></>)
    expect(screen.queryByText(/Source check needed|Growth source check needed|Unverified/)).not.toBeInTheDocument()
    expect(screen.getByText('† calculated')).not.toHaveClass('bg-warning-light/10')
    const value = screen.getByRole('button', { name: /Revenue, 2023Q4.*View source/ })
    value.focus()
    await user.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog', { name: 'Revenue · 2023Q4' })
    expect(within(dialog).getByText(/Calculated by EarningsNerd from source figures\. Automated checks passed/)).toBeInTheDocument()
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
    render(<><SourcesMethods dataset={flagged} /><MetricsTable dataset={flagged} /></>)
    expect(screen.getByRole('button', { name: /Revenue, 2023Q3:.*data note a/ }).querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    const note = screen.getByText(/The source inputs use different units or currencies/).closest('li')
    expect(note).toHaveTextContent('Revenue (2023Q3)')
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
  })

  it('does not promote legacy true or absent quality into a passed validation claim', async () => {
    render(<SourceValue point={{ period: '2024Q4', value: 8.02, reconciled: true }} label="EPS">$8.02</SourceValue>)
    await userEvent.click(screen.getByRole('button', { name: /View source/ }))
    expect(screen.getByText(/Validation unavailable/)).toBeInTheDocument()
    expect(screen.queryByText(/Automated checks passed/)).not.toBeInTheDocument()
  })

  it('shows unavailable EPS with its reason and no invented figure', async () => {
    const missing = structuredClone(dataset)
    missing.series[0].points[1] = { period: '2023Q4', value: null, provenance: { ...calculated, validation: 'unavailable', reasons: ['eps_requires_reported_quarter'] } }
    render(<MetricsTable dataset={missing} />)
    await userEvent.click(screen.getByRole('button', { name: /2023Q4: unavailable/ }))
    expect(screen.getByText('A reported quarterly earnings-per-share figure is unavailable.')).toBeInTheDocument()
    expect(screen.queryByText('$40.1B')).not.toBeInTheDocument()
  })

  it('keeps a comparison-only concern inspectable without marking the current value as needing review', async () => {
    const flagged = structuredClone(dataset)
    flagged.series[0].points[1].qoq_provenance = { ...calculated, validation: 'needs_review', reasons: ['unit_mismatch'] }
    render(<DataNotesProvider dataset={flagged}><SourcesMethods dataset={flagged} /><MetricsTable dataset={flagged} /></DataNotesProvider>)
    expect(screen.getByText(/1 comparison needs review/)).toBeInTheDocument()
    expect(screen.getByText(/Comparisons: Revenue QoQ \(2023Q4\)/)).toBeInTheDocument()
    const figure = screen.getByRole('button', { name: /Revenue, 2023Q4:.*comparison carries data note a/ })
    expect(figure.querySelector('[data-note-kind="review"]')).not.toBeInTheDocument()
    await userEvent.click(figure)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · 2023Q4' })
    expect(within(dialog).getByRole('heading', { name: 'QoQ comparison' })).toBeInTheDocument()
    expect(within(dialog).getByText(/Data note a\. The source inputs use different units or currencies/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Calculated by EarningsNerd from source figures\. Automated checks passed/)).toBeInTheDocument()
  })

  it('explains an absent metric-period slot with the same unavailable note counted in the report', async () => {
    const missing = structuredClone(dataset)
    missing.series[0].points.pop()
    render(<DataNotesProvider dataset={missing}><SourcesMethods dataset={missing} /><MetricsTable dataset={missing} /></DataNotesProvider>)
    expect(screen.getByText(/1 unavailable/)).toBeInTheDocument()
    const value = screen.getByRole('button', { name: /Revenue, 2023Q4: unavailable, data note a/ })
    expect(value.querySelector('[data-note-kind="unavailable"]')).toHaveTextContent('a')
    await userEvent.click(value)
    const dialog = screen.getByRole('dialog', { name: 'Revenue · 2023Q4' })
    expect(within(dialog).getByText(/Not available in this dataset/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/Automated checks passed/)).not.toBeInTheDocument()
  })
})

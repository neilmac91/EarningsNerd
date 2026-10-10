'use client'

import { Card } from '@/components/ui'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import { useDataNotes } from './DataNotesContext'

const comparisonLabel = (basis: string) => basis === 'qoq' ? 'QoQ' : basis === 'yoy' ? 'YoY' : basis === 'window_pp' ? 'window percentage-point' : 'CAGR'

export function DataNotesList({ notes }: { notes: DataNote[] }) {
  return (
    <ul className="space-y-3">
      {notes.map((note) => {
        const values = new Map<string, string[]>()
        for (const value of note.values) values.set(value.label, [...(values.get(value.label) ?? []), value.period])
        const comparisons = Object.entries(note.counts).filter(([, count]) => count > 0)
        const comparisonPlaces = new Map<string, string[]>()
        for (const comparison of note.comparisons) {
          const label = `${comparison.label} ${comparisonLabel(comparison.basis)}${comparison.basis === 'window_pp' ? ' change' : ''}`
          comparisonPlaces.set(label, [...(comparisonPlaces.get(label) ?? []), comparison.period])
        }
        return <li id={note.id} key={note.key} tabIndex={-1} className="rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          <p><span className={`font-data font-medium ${note.kind === 'review' ? 'text-warning-light dark:text-warning-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>Note {note.letter}.</span> {note.message}</p>
          {values.size > 0 && <p>{[...values].map(([label, periods]) => `${label} (${[...new Set(periods)].join(', ')})`).join('; ')}.</p>}
          {comparisons.length > 0 && <p>{comparisons.map(([basis, count]) => `${count} ${comparisonLabel(basis)} ${count === 1 ? 'comparison' : 'comparisons'}`).join(' · ')}.</p>}
          {comparisonPlaces.size > 0 && <p>Comparisons: {[...comparisonPlaces].map(([label, periods]) => `${label} (${[...new Set(periods)].join(', ')})`).join('; ')}.</p>}
        </li>
      })}
    </ul>
  )
}

export default function SourcesMethods({ dataset, sample = false }: { dataset: AnalysisDataset; sample?: boolean }) {
  const model = useDataNotes(dataset)
  const { totals } = model
  const unknownComparisons = model.notes.filter((note) => note.kind === 'unknown').reduce((count, note) => count + note.comparisons.length, 0)
  return (
    <Card as="section" className="p-4">
      <details>
        <summary className="cursor-pointer rounded text-sm font-medium text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark">
          Data notes
          <span className="font-normal text-text-secondary-light dark:text-text-secondary-dark">
            {sample ? ' · illustrative sample' : null}
            {totals.reviewValues > 0 ? ` · ${totals.reviewValues} ${totals.reviewValues === 1 ? 'figure needs' : 'figures need'} review` : ''}
            {totals.reviewComparisons > 0 ? ` · ${totals.reviewComparisons} ${totals.reviewComparisons === 1 ? 'comparison needs' : 'comparisons need'} review` : ''}
            {totals.unknown > 0 ? ` · ${totals.unknown} ${totals.unknown === 1 ? 'figure has' : 'figures have'} no validation record` : ''}
            {unknownComparisons > 0 ? ` · ${unknownComparisons} ${unknownComparisons === 1 ? 'comparison has' : 'comparisons have'} no validation record` : ''}
            {totals.unavailable > 0 ? ` · ${totals.unavailable} unavailable` : ''}
            {!sample && totals.reviewValues === 0 && totals.reviewComparisons === 0 && totals.unknown === 0 && unknownComparisons === 0 && totals.passed > 0 ? ` · ${totals.passed} ${totals.passed === 1 ? 'figure' : 'figures'} passed automated checks` : ''}
            {totals.calculated > 0 ? ` · ${totals.calculated} calculated †` : ''}
          </span>
        </summary>
        <div className="mt-3 space-y-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <DataNotesList notes={model.notes} />
          <p>Select a figure to inspect its source, reporting period and calculation. Letters identify data notes; † marks a calculated figure, not an error. Comparisons retain notes from their source inputs. Counts describe distinct figures and comparisons, not the number of places they appear.</p>
          <details>
            <summary className="cursor-pointer rounded font-medium focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Sources &amp; methods</summary>
            <div className="mt-2 space-y-2">
              <p>Figures come from SEC filings; some are calculated. Quarterly cash flows may be calculated by subtracting earlier year-to-date totals. Fourth-quarter flow figures may be calculated from annual totals less the first nine months. Earnings per share uses a reported quarterly figure; it is not subtracted from annual EPS.</p>
              <p>{FCF_DEFINITION}</p>
              <p>Missing values are unavailable in this dataset, not zero. Growth is unavailable when its comparison period or compatible inputs are missing. Missing validation is not a claim that a figure passed checks.</p>
              <p>{dataset.data_as_of ? `Source data as of ${dataset.data_as_of}.` : 'Source refresh time is unavailable.'} Source matching and automated checks do not constitute an audit of the company’s accounts.</p>
              {dataset.snapshot_id && <details><summary className="cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Report reference</summary><p className="font-data break-all text-xs">{dataset.dataset_version} · {dataset.snapshot_id}</p></details>}
            </div>
          </details>
        </div>
      </details>
    </Card>
  )
}

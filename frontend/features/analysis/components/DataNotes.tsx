'use client'

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { useDataNotes } from './DataNotesContext'

const comparisonLabel = (basis: string) => basis === 'qoq' ? 'QoQ' : basis === 'yoy' ? 'YoY' : basis === 'window_pp' ? 'window percentage-point' : 'CAGR'
const periodLabel = (period: string) => period.split('..').map((key) => formatAnalysisPeriod(key)).join(' – ')

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
        return <li id={note.id} key={note.key} tabIndex={-1} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-2 rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          <span className={`relative font-data font-medium ${note.kind === 'review' ? 'text-warning-light dark:text-warning-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}><span className="sr-only">Note </span>{note.letter}.</span>
          <div className="min-w-0 space-y-1">
            <p>{note.message}</p>
            {values.size > 0 && <p>{[...values].map(([label, periods]) => `${label} (${[...new Set(periods)].map(periodLabel).join(', ')})`).join('; ')}.</p>}
            {(note.values.length > 0 || comparisons.length > 0) && <p className="font-data text-xs">{[
              ...(note.values.length ? [`${note.values.length} ${note.values.length === 1 ? 'figure' : 'figures'}`] : []),
              ...comparisons.map(([basis, count]) => `${count} ${comparisonLabel(basis)} ${count === 1 ? 'comparison' : 'comparisons'}`),
            ].join(' · ')}.</p>}
            {comparisonPlaces.size > 0 && <p>Comparisons: {[...comparisonPlaces].map(([label, periods]) => `${label} (${[...new Set(periods)].map(periodLabel).join(', ')})`).join('; ')}.</p>}
          </div>
        </li>
      })}
    </ul>
  )
}

export default function DataNotes({ dataset, sample = false }: { dataset: AnalysisDataset; sample?: boolean }) {
  const model = useDataNotes(dataset)
  const { totals } = model
  const unknownComparisons = model.notes.filter((note) => note.kind === 'unknown').reduce((count, note) => count + note.comparisons.length, 0)
  const allPopulatedPassed = totals.reviewValues === 0 && totals.reviewComparisons === 0 && totals.unknown === 0 && unknownComparisons === 0
  return (
    <section className="min-w-0 border-y border-border-light py-1 dark:border-border-dark" data-analysis-data-notes>
      <details>
        <summary className="cursor-pointer rounded py-2 text-sm text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark">
          <span className="font-medium">Data notes</span>
          <span className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
            {sample && <span> · illustrative sample</span>}
            {totals.reviewValues > 0 && <span className="text-warning-light dark:text-warning-dark"> · {totals.reviewValues} {totals.reviewValues === 1 ? 'figure needs' : 'figures need'} review</span>}
            {totals.reviewComparisons > 0 && <span className="text-warning-light dark:text-warning-dark"> · {totals.reviewComparisons} {totals.reviewComparisons === 1 ? 'comparison needs' : 'comparisons need'} review</span>}
            {totals.unknown > 0 && <span> · {totals.unknown} {totals.unknown === 1 ? 'figure has' : 'figures have'} no validation record</span>}
            {unknownComparisons > 0 && <span> · {unknownComparisons} {unknownComparisons === 1 ? 'comparison has' : 'comparisons have'} no validation record</span>}
            {!sample && allPopulatedPassed && totals.passed > 0 && <span className="text-brand-strong dark:text-brand-strong-dark"> · {totals.passed} {totals.passed === 1 ? 'figure' : 'figures'} passed automated checks</span>}
            {totals.unavailable > 0 && <span> · {totals.unavailable} unavailable</span>}
            {totals.calculated > 0 && <span> · {totals.calculated} calculated †</span>}
          </span>
        </summary>
        <div className="space-y-3 pb-3 pt-1 text-xs leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
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
    </section>
  )
}

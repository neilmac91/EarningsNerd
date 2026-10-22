'use client'

import { useMemo, useSyncExternalStore } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { usePrintDetails } from '@/features/analysis/lib/usePrintDetails'
import { comparisonLocations, tablePeriods } from '@/features/analysis/lib/reportPresentation'
import { formatInstant, formatLocalDate } from '@/lib/format'
import { useAnalysisTableWindow, useDataNotes } from './DataNotesContext'

/** Nothing to subscribe to: the source date asks only whether it renders in the browser. */
const noSubscription = () => () => {}

const comparisonLabel = (basis: string) => basis === 'qoq' ? 'QoQ' : basis === 'yoy' ? 'YoY' : basis === 'window_pp' ? 'window percentage-point' : 'CAGR'
const periodLabel = (period: string) => period.split('..').map((key) => formatAnalysisPeriod(key)).join(' – ')

type ComparisonLocations = ReturnType<typeof comparisonLocations>

function comparisonLocator(location: ReturnType<ComparisonLocations>[number]) {
  const { basis, total, headline, chart, chartLabel, table, fullTable, windowed, periods, quarterly } = location
  const label = basis === 'qoq' ? 'quarter-over-quarter' : basis === 'yoy' ? 'year-over-year' : basis === 'window_pp' ? 'window percentage-point' : 'CAGR'
  const surfaces = [
    headline ? `The headline cards show ${headline}.` : '',
    chart ? `The ${chartLabel} growth chart shows ${chart}.` : '',
    fullTable ? `The table shows ${fullTable}${quarterly && basis === 'yoy' ? ' as its labelled fallback' : ''}${windowed && (basis === 'qoq' || basis === 'yoy') ? ` (${table} in the ${periods} ${quarterly ? 'quarters' : 'years'} shown)` : ''}.` : '',
    `Exports carry all ${total}.`,
  ].filter(Boolean)
  return `${total} ${label} ${total === 1 ? 'comparison carries' : 'comparisons carry'} this note. ${surfaces.join(' ')}`
}

/** Citation supplements omit locations because they have no report surface membership to inspect. */
export function DataNotesList({ notes, locations }: { notes: DataNote[]; locations?: ComparisonLocations }) {
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
            {locations?.(note).map(location => <p key={location.basis}>{comparisonLocator(location)}</p>)}
          </div>
        </li>
      })}
    </ul>
  )
}

export default function DataNotes({ dataset, sample = false }: { dataset: AnalysisDataset; sample?: boolean }) {
  const printScope = usePrintDetails()
  const model = useDataNotes(dataset)
  const { window } = useAnalysisTableWindow(dataset)
  const locations = useMemo(() => sample ? undefined : comparisonLocations(dataset, tablePeriods(dataset, window), model),
    [dataset, window, model, sample])
  const { totals } = model
  // data_as_of is an instant, the source data's sync time, so it prints as the day it falls on in the reader's zone.
  // The server (the landing renders its demo there) and the hydrating render cannot know that zone, so they print the
  // day the API writes, iso_z's UTC day, which every zone renders alike; React renders again right after hydrating,
  // with the reader's day (useTodayEasternIso's pattern, E136). Suppressing the mismatch kept the server's day instead.
  const inBrowser = useSyncExternalStore(noSubscription, () => true, () => false)
  const sourceDate = inBrowser
    ? formatInstant(dataset.data_as_of, 'MMMM d, yyyy')
    : formatLocalDate(dataset.data_as_of, 'MMMM d, yyyy')
  const unknownComparisons = model.notes.filter((note) => note.kind === 'unknown').reduce((count, note) => count + note.comparisons.length, 0)
  const allPopulatedPassed = totals.reviewValues === 0 && totals.unknown === 0 && totals.passed > 0
  const letters = (kind: DataNote['kind'], scope: 'values' | 'comparisons') => model.notes
    .filter((note) => note.kind === kind && note[scope].length > 0).map((note) => note.letter)
  const reviewComparisonLetters = letters('review', 'comparisons')
  return (
    <section className="min-w-0 border-y border-border-light py-1 dark:border-border-dark" data-analysis-data-notes data-analysis-print-scope={printScope}>
      <details>
        <summary className="cursor-pointer rounded py-2 text-sm text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark">
          <span className="font-medium">Data notes</span>
          <span className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
            {/* The same words NarrativePane's sample labels use for the one payload (D-046). */}
            {sample && <span> · sample data (one saved run)</span>}
            {!sample && allPopulatedPassed && <span> · No figures need review · {totals.passed} checked</span>}
            {totals.reviewValues > 0 && <span className="text-warning-light dark:text-warning-dark"> · {totals.reviewValues} {totals.reviewValues === 1 ? 'figure needs' : 'figures need'} review ({letters('review', 'values').join(', ')})</span>}
            {totals.reviewComparisons > 0 && <span className="text-warning-light dark:text-warning-dark"> · {totals.reviewComparisons} {totals.reviewComparisons === 1 ? 'comparison carries' : 'comparisons carry'} {reviewComparisonLetters.length === 1 ? 'note' : 'notes'} {reviewComparisonLetters.join(', ')}</span>}
            {totals.unknown > 0 && <span> · {totals.unknown} {totals.unknown === 1 ? 'figure has' : 'figures have'} no validation record ({letters('unknown', 'values').join(', ')})</span>}
            {unknownComparisons > 0 && <span> · {unknownComparisons} {unknownComparisons === 1 ? 'comparison has' : 'comparisons have'} no validation record ({letters('unknown', 'comparisons').join(', ')})</span>}
            {totals.unavailable > 0 && <span> · {totals.unavailable} unavailable ({letters('unavailable', 'values').join(', ')})</span>}
            {totals.calculated > 0 && <span> · {totals.calculated} calculated †</span>}
          </span>
        </summary>
        <div className="space-y-3 pb-3 pt-1 text-xs leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          <DataNotesList notes={model.notes} locations={locations} />
          <p>Automated checks confirm that reported figures come from the company’s SEC XBRL data and that calculations combine compatible periods and units; they are not an audit of the company’s accounts.</p>
          <p>Select a figure to inspect its source, reporting period and calculation. Letters identify data notes; † marks a calculated figure, not an error. Comparisons retain notes from their source inputs. Counts describe distinct figures and comparisons, not the number of places they appear.</p>
          <details>
            <summary className="cursor-pointer rounded font-medium focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Sources &amp; methods</summary>
            <div className="mt-2 space-y-2">
              <p>Figures come from SEC filings; some are calculated. Quarterly cash flows may be calculated by subtracting earlier year-to-date totals. Fourth-quarter flow figures may be calculated from annual totals less the first nine months. Earnings per share uses a reported quarterly figure; it is not subtracted from annual EPS.</p>
              <p>{FCF_DEFINITION}</p>
              <p>Missing values are unavailable in this dataset, not zero. Growth is unavailable when its comparison period or compatible inputs are missing. Missing validation is not a claim that a figure passed checks.</p>
              <p>{sourceDate ? `Source data as of ${sourceDate}.` : 'Source refresh time is unavailable.'} Source matching and automated checks do not constitute an audit of the company’s accounts.</p>
              {/* A sample's snapshot is a saved run's, which no reader can resolve against production: no reference. */}
              {!sample && dataset.snapshot_id && <details><summary className="cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Report reference</summary><p className="font-data break-all text-xs">{dataset.dataset_version} · {dataset.snapshot_id}</p></details>}
            </div>
          </details>
        </div>
      </details>
    </section>
  )
}

'use client'

import { MissingValue } from '@/components/ui/MissingValue'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { noteMarksFigure, noteSummary, type DataNote } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { usePrintDetails } from '@/features/analysis/lib/usePrintDetails'
import { useSourceDate } from '@/features/analysis/lib/useSourceDate'
import DataNoteMark from './DataNoteMark'
import { useDataNotes } from './DataNotesContext'

const comparisonLabel = (basis: string) => basis === 'qoq' ? 'QoQ' : basis === 'yoy' ? 'YoY' : basis === 'window_pp' ? 'window percentage-point' : 'CAGR'

/** A summary names at most this many metrics for a note, then counts the rest. */
const SUMMARY_PLACES = 3

/** Each metric with its periods, in the note's order: "Revenue FY2018, FY2019". */
function placesOf(refs: readonly { label: string; period: string }[]): [string, string[]][] {
  const places = new Map<string, string[]>()
  for (const ref of refs) places.set(ref.label, [...new Set([...(places.get(ref.label) ?? []), formatAnalysisPeriod(ref.period)])])
  return [...places]
}

/** Where a marked note sits, for the summary line: its figures, or, for a note only on growth figures, those. */
function summaryPlaces(note: DataNote): string {
  const places = note.values.length ? placesOf(note.values)
    : placesOf(note.comparisons.map((ref) => ({ ...ref, label: `${ref.label} ${comparisonLabel(ref.basis)}${ref.basis === 'window_pp' ? ' change' : ''}` })))
  const shown = places.slice(0, SUMMARY_PLACES).map(([label, periods]) => `${label} ${periods.join(', ')}`).join('; ')
  return places.length > SUMMARY_PLACES ? `${shown} and ${places.length - SUMMARY_PLACES} more` : shown
}

/** Every note, the ones that mark a figure first (their letters are the ones the page shows). Citation supplements and
 *  the sample's notes list here too; none of them makes a claim about where on the page a note appears. */
export function DataNotesList({ notes }: { notes: DataNote[] }) {
  const ordered = [...notes.filter(noteMarksFigure), ...notes.filter((note) => !noteMarksFigure(note))]
  return (
    <ul className="space-y-3">
      {ordered.map((note) => {
        const figures = note.values.length
        const growth = note.comparisons.length
        const comparisonPlaces = placesOf(note.comparisons.map((comparison) => ({ ...comparison, label: `${comparison.label} ${comparisonLabel(comparison.basis)}${comparison.basis === 'window_pp' ? ' change' : ''}` })))
        // A note that marks nothing has no letter on the page, so none here; its id stays, so a link to it still lands.
        return <li id={note.id} key={note.key} tabIndex={-1} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-2 rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          <span className="relative font-data font-medium">{noteMarksFigure(note) && <><span className="sr-only">Note </span>{note.letter}.</>}</span>
          <div className="min-w-0 space-y-1">
            <p>{note.message}</p>
            {note.values.length > 0 && <p>{placesOf(note.values).map(([label, periods]) => `${label} (${periods.join(', ')})`).join('; ')}.</p>}
            {/* Its counts: the figures, and apart from them the growth figures that carry the note (#1610 §3.2). */}
            {(figures > 0 || growth > 0) && <p className="font-data text-xs">{[
              ...(figures ? [`${figures} ${figures === 1 ? 'figure' : 'figures'}`] : []),
              ...(growth ? [`${growth} ${growth === 1 ? 'growth figure' : 'growth figures'}${figures ? ` built on ${figures === 1 ? 'it' : 'them'}` : ''}`] : []),
            ].join('; ')}.</p>}
            {comparisonPlaces.length > 0 && <p>Comparisons: {comparisonPlaces.map(([label, periods]) => `${label} (${periods.join(', ')})`).join('; ')}.</p>}
          </div>
        </li>
      })}
    </ul>
  )
}

/** The data notes: one line of fine print under the metrics table, the detail one click away (D-061). The summary names
 *  each note that marks a figure, with its places and its summary words (noteSummary), and
 *  counts the gaps, the figures with no check recorded and the calculated figures; the open detail lists every note
 *  with its message and counts. Nothing here is in warning ink. */
export default function DataNotes({ dataset, sample = false }: { dataset: AnalysisDataset; sample?: boolean }) {
  const printScope = usePrintDetails()
  const model = useDataNotes(dataset)
  const { totals } = model
  // The day the source data was synced, in the reader's zone once hydrated (useSourceDate), as the results header prints it.
  const sourceDate = useSourceDate(dataset.data_as_of)
  const marked = model.notes.filter(noteMarksFigure)
  const unknownComparisons = model.notes.filter((note) => note.kind === 'unknown').reduce((count, note) => count + note.comparisons.length, 0)
  // Decision 9 says it whenever every populated figure passed, whatever a comparison carries. D-061 keeps "never mark a
  // legacy record validated", so it never stands beside a note that needs review but marks nothing, a growth figure's
  // included.
  const allPopulatedPassed = totals.reviewValues === 0 && totals.unknown === 0 && totals.passed > 0
    && !model.notes.some((note) => note.kind === 'review' && !noteMarksFigure(note))
  const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`
  return (
    <section className="min-w-0 text-xs leading-relaxed text-text-secondary-light dark:text-text-secondary-dark" data-analysis-data-notes data-analysis-print-scope={printScope}>
      <details>
        <summary className="cursor-pointer rounded py-1 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          <span className="font-medium text-text-primary-light dark:text-text-primary-dark">Data notes</span>
          {/* The same words NarrativePane's sample labels use for the one payload (D-046). */}
          {sample && <span> · sample data (one saved run)</span>}
          {marked.map((note) => <span key={note.key} className="relative"> · <span className="sr-only">Note {note.letter}: </span><DataNoteMark note={note} /> {summaryPlaces(note)}: {noteSummary(note.reasons)}</span>)}
          {/* The table's dash itself, as the one sanctioned token in an element of its own; a screen reader hears "a dash". */}
          {totals.unavailable > 0 && <span> · {totals.unavailable} not in our data, shown as <MissingValue label="a dash" /></span>}
          {totals.unknown > 0 && <span> · {plural(totals.unknown, 'figure', 'figures')} with no check recorded</span>}
          {unknownComparisons > 0 && <span> · {plural(unknownComparisons, 'growth figure', 'growth figures')} with no check recorded</span>}
          {totals.calculated > 0 && <span> · {totals.calculated} calculated from filed figures</span>}
          {!sample && allPopulatedPassed && <span> · No figures need review · {totals.passed} checked</span>}
        </summary>
        <div className="space-y-3 pb-3 pt-1">
          <DataNotesList notes={model.notes} />
          <p>Select any figure to see its source filing, method and inputs. Automated checks confirm that reported figures come from the company’s filed data (XBRL); they are not an audit of the company’s accounts.</p>
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

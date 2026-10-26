import type { AnalysisDataset, AnalysisPoint, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import type { DataNote, DataNotesModel } from './dataNotes'
import { chartTopLine, fullyCalculated } from './charts/model'
import { windowGrowth } from './growth'

export const reportIdentity = (dataset: AnalysisDataset) =>
  JSON.stringify([dataset.ticker, dataset.mode, dataset.period_key, dataset.snapshot_id ?? null])

/** The top line the KPI strip and the first chart share: revenue, else a bank's net
 *  interest income, else an insurer's premiums earned (spec D16), whichever has a value in the window. */
export const topLineConcept = (dataset: AnalysisDataset) => chartTopLine(dataset)?.concept ?? 'revenue'

/** The KPI renderer's four concepts and the latest populated point of each. */
export function selectHeadlineFigures(dataset: AnalysisDataset) {
  const byConcept = Object.fromEntries(dataset.series.map(series => [series.concept, series]))
  return [topLineConcept(dataset), 'net_income', 'free_cash_flow', 'net_margin'].flatMap(concept => {
    const series = byConcept[concept]
    if (!series) return []
    for (let index = dataset.periods.length - 1; index >= 0; index--) {
      const point = series.points.find(point => point.period === dataset.periods[index].key)
      if (point?.value != null) return [{ series, point }]
    }
    return []
  })
}

export const tableComparisonBasis = (mode: AnalysisDataset['mode'], point: AnalysisPoint) =>
  mode === 'quarterly' && point.qoq != null ? 'qoq' as const : 'yoy' as const

/** Actual rendered table membership: every period, including gaps, and the full annual window column. The table's
 *  Notes chip takes the notes that mark from these (DataNotesLink). */
export function tablePresentation(dataset: AnalysisDataset, notes: DataNotesModel) {
  const letters = new Set<string>()
  const include = (note: DataNote | null) => { if (note) letters.add(note.key) }
  for (const series of dataset.series) {
    for (const period of dataset.periods) {
      const point = series.points.find(point => point.period === period.key) ?? { period: period.key, value: null }
      include(notes.noteFor(point))
      if (point.value == null) continue
      const basis = tableComparisonBasis(dataset.mode, point)
      if (point[basis] == null) continue
      include(notes.noteForComparison(point, basis))
    }
    if (dataset.mode === 'annual' && windowGrowth(series).value != null) include(notes.noteForWindow(series))
  }
  return { notes: notes.notes.filter(note => letters.has(note.key)) }
}

/** A metric's label inside a sentence: its first letter lowercased, unless it opens an abbreviation ("EPS (diluted)");
 *  a ratio takes its article ("the current ratio"). */
const inSentence = (label: string) => {
  const name = /^.[A-Z]/.test(label) ? label : label.charAt(0).toLowerCase() + label.slice(1)
  return / ratio$/.test(name) ? `the ${name}` : name
}
const isMargin = (series: AnalysisSeries) => /\bmargin$/i.test(series.label)

/** The sentence above the metrics table. It names the metrics whose every value in the run is calculated, as the
 *  dataset labels them, since the figures themselves carry no dagger (D-061); a run with none says nothing about
 *  calculation. Two or more margins read as "margins" when every margin of the run is calculated, so a run with a
 *  reported gross margin names its calculated margins one by one. A row calculated only in some periods is not named:
 *  each such figure's control says "calculated", its dialog gives the method, and the quarterly legend explains the
 *  derived fourth quarters. */
export function calculatedMetricsSentence(dataset: AnalysisDataset): string {
  const calculated = dataset.series.filter(series => fullyCalculated(series, dataset))
  const margins = dataset.series.filter(isMargin)
  const grouped = margins.length > 1 && margins.every(series => calculated.includes(series))
  // "Margins" stands where the run's first margin would.
  const names = calculated.flatMap(series => !grouped || !isMargin(series) ? [inSentence(series.label)] : series === margins[0] ? ['margins'] : [])
  const list = names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
  return `Figures are rounded for display${list ? `; ${list} ${names.length > 1 || grouped ? 'are' : 'is'} calculated from filed figures` : ''}. Select any value for its source and full precision.`
}

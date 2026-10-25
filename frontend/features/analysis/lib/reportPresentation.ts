import type { AnalysisDataset, AnalysisPoint } from '@/features/analysis/api/analysis-api'
import type { DataNote, DataNoteBasis, DataNotesModel } from './dataNotes'
import { chartCurrency, chartTopLine } from './charts/model'
import { windowGrowth, windowRange } from './growth'

export const reportIdentity = (dataset: AnalysisDataset) =>
  JSON.stringify([dataset.ticker, dataset.mode, dataset.period_key, dataset.snapshot_id ?? null])

/** The top line the KPI strip, the notes' chart locators and the first chart share: revenue, else a bank's net
 *  interest income, else an insurer's premiums earned (spec D16), whichever has a value in the window. */
export const topLineConcept = (dataset: AnalysisDataset) => chartTopLine(dataset)?.concept ?? 'revenue'

/** The KPI renderer and note locators use the same four concepts and latest populated point. */
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

const comparisonId = (concept: string, period: string, basis: DataNoteBasis) => JSON.stringify([concept, period, basis])

/** Actual rendered table membership: every period, including gaps, and the full annual window column. */
export function tablePresentation(dataset: AnalysisDataset, notes: DataNotesModel) {
  const letters = new Set<string>()
  const comparisons = new Set<string>()
  const include = (note: DataNote | null) => { if (note) letters.add(note.key) }
  for (const series of dataset.series) {
    for (const period of dataset.periods) {
      const point = series.points.find(point => point.period === period.key) ?? { period: period.key, value: null }
      include(notes.noteFor(point))
      if (point.value == null) continue
      const basis = tableComparisonBasis(dataset.mode, point)
      if (point[basis] == null) continue
      include(notes.noteForComparison(point, basis))
      comparisons.add(comparisonId(series.concept, period.key, basis))
    }
    if (dataset.mode === 'annual' && windowGrowth(series).value != null) {
      include(notes.noteForWindow(series))
      comparisons.add(comparisonId(series.concept, windowRange(series) ?? dataset.period_key, series.percent ? 'window_pp' : 'cagr'))
    }
  }
  return { notes: notes.notes.filter(note => letters.has(note.key)), comparisons }
}

/** Count distinct concept/period/basis identities; a second appearance never adds a comparison. */
export function comparisonLocations(dataset: AnalysisDataset, notes: DataNotesModel) {
  const headline = new Set(selectHeadlineFigures(dataset).flatMap(({ series, point }) => {
    const annual = dataset.mode === 'annual'
    if ((annual ? windowGrowth(series).value : point.yoy) == null) return []
    return [comparisonId(series.concept, annual ? windowRange(series) ?? dataset.period_key : point.period,
      annual ? series.percent ? 'window_pp' : 'cagr' : 'yoy')]
  }))
  const topLine = chartTopLine(dataset)
  // TrendCharts plots numeric YoY only; n/m is a table/card label, never a plotted point. A top line filed in two
  // currencies draws no chart (it prints MIXED_CURRENCY), so it shows none of its comparisons.
  const plotted = topLine && !chartCurrency(dataset, [topLine.concept]).mixed ? topLine : undefined
  const chart = new Set(dataset.periods.flatMap(period => {
    const point = plotted?.points.find(point => point.period === period.key)
    return typeof point?.yoy === 'number' ? [comparisonId(plotted!.concept, period.key, 'yoy')] : []
  }))
  const table = tablePresentation(dataset, notes).comparisons
  return (note: DataNote) => (['qoq', 'yoy', 'cagr', 'window_pp'] as const).flatMap(basis => {
    const identities = new Set(note.comparisons.filter(comparison => comparison.basis === basis)
      .map(comparison => comparisonId(comparison.concept, comparison.period, basis)))
    if (!identities.size) return []
    const count = (surface: Set<string>) => [...identities].filter(identity => surface.has(identity)).length
    return [{ basis, total: identities.size, headline: count(headline), chart: count(chart), table: count(table),
      chartLabel: topLine?.label.toLowerCase() ?? 'top-line', quarterly: dataset.mode === 'quarterly' }]
  })
}

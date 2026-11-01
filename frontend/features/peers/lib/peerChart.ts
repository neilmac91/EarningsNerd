/**
 * The Sector peers panel's chart (E251): a cohort as the trend charts' engine draws it, a one-metric bar chart
 * (`buildBarChart`) of the companies the panel draws (cohort.ts `drawn`), the subject in chart-1 and every other company
 * a context bar in the context ink, at the narrower width; the chart starting at the subject, so a phone opens on it,
 * and naming its categories companies; a gap before a subject the bars' order would misrank (E258, cohort.ts
 * `breaksBefore`). And the describer its values stop and tooltip read each company through. Pure,
 * so the panel and the engine's sweeps over every cohort the panel shows (tests/unit/chartPlan.ts, chart-engine.spec.ts,
 * chart-readout.spec.ts, trend-charts-v2.spec.tsx) build them the same way.
 */
import { buildBarChart, type BarAxis, type BarCategory, type BarChartDef } from '@/features/analysis/lib/charts/barChart'
import type { ChartModel, ChartReading } from '@/features/analysis/lib/charts/model'
import { periodHeader, readouts, type PeriodReadout, type ReadoutDescriber } from '@/features/analysis/lib/charts/readout'
import type { FmtKind } from '@/features/fundamentals/lib/featuredMetrics'
import type { PeerComparisonResponse, PeerEntry } from '@/features/peers/api/peers-api'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { breaksBefore, drawn, metricOf, rankOf } from './cohort'

/** What the plot calls its categories: its scroll region reads "Scroll horizontally to view all companies.", and a
 *  step past either end says "First company." or "Last company.". */
export const COMPANY_READING: ChartReading = { items: 'companies', first: 'First company.', last: 'Last company.' }

/** The words the values stop says for the subject, after its name and ticker. */
const THIS_COMPANY = 'this company'

/** The value axis a metric takes: an amount in the answer's XBRL unit, whose currency the engine prints (CNY, never "$";
 *  "USD/shares" is a per-share amount), a margin in percentage points, or a multiple. */
const axisOf = (fmt: FmtKind, unit: string | null): BarAxis =>
  fmt === 'pct' ? { kind: 'percent' } : fmt === 'ratio' ? { kind: 'ratio' } : { kind: 'money', unit: unit ?? '' }

/** Each drawn company's slot: its ticker names it, ticks it and is its long name; a company the chart is not about is a
 *  context bar. A slot is keyed by its ticker, or by its place where two companies answer one ticker (Company.ticker is
 *  not unique, and buildBarChart refuses a key given twice), as Financial trends keys a year two points share. */
export function slotsOf(entries: PeerEntry[]): BarCategory[] {
  const tickers = entries.map((entry) => entry.ticker)
  return entries.map((entry, i) => {
    const own = entry.ticker !== '' && tickers.indexOf(entry.ticker) === tickers.lastIndexOf(entry.ticker)
    return {
      key: own ? entry.ticker : `${entry.ticker || 'company'}#${i}`,
      tick: entry.ticker,
      long: entry.ticker,
      ...(entry.is_subject ? {} : { context: true as const }),
    }
  })
}

/** A fiscal year's name, "FY2025", or its period end's year where the backend names none. */
const yearOf = (entry: PeerEntry) => (entry.fiscal_year != null ? `FY${entry.fiscal_year}` : entry.period_end?.slice(0, 4) ?? null)

/** Each company as the tooltip prints it and the values stop says it, in one order: who it is, where it ranks, which
 *  year. The tooltip, "AAPL · Apple Inc. · #3 of 9 · FY2025 · year ended Sep 27, 2025": the ticker first, since the
 *  reader hovered its bar, then the name, which no tick or label prints (two companies can answer one ticker), the rank
 *  over the companies with a value, kept on one line, and its own fiscal year, which can differ by company; it wraps
 *  inside the plot's visible width (TrendChartPlot's placeTip). The values stop, "Apple Inc., AAPL, this company, rank 3 of 9, FY2025, year
 *  ended September 27, 2025." (no "·", "#" or unit letter). A figure the backend derived reads as calculated from its
 *  own provenance. `slots` are `slotsOf(entries)`. */
export function peerDescriber(answer: PeerComparisonResponse, entries: PeerEntry[], slots: BarCategory[]): ReadoutDescriber {
  const at = new Map(slots.map((slot, i) => [slot.key, entries[i]]))
  const of = rankOf(answer)?.of
  return {
    header: (period) => {
      const entry = at.get(period.key)
      if (!entry) return { shown: period.long, spoken: period.long }
      const name = formatCompanyName(entry.company_name)
      // No-break spaces keep the shown rank on one line where the header wraps on a phone ("#6 of" never ends a line).
      const rank = entry.rank != null && of != null ? { shown: `#${entry.rank}\u00a0of\u00a0${of}`, spoken: `rank ${entry.rank} of ${of}` } : null
      const year = yearOf(entry)
      const when = year ? periodHeader(year, 'year', entry.period_end) : null
      const shown = [entry.ticker, name, rank?.shown, when?.shown]
      const spoken = [name, entry.ticker, entry.is_subject ? THIS_COMPANY : null, rank?.spoken, when?.spoken]
      return { shown: shown.filter(Boolean).join(' · '), spoken: spoken.filter(Boolean).join(', ') }
    },
    calculated: (_mark, key) => at.get(key)?.provenance?.method === 'calculated',
  }
}

/** The answer as the engine's bar chart: the drawn companies in order, the answered metric's label (a bank's "Net
 *  interest income"), its axis by the metric's kind in the answer's unit, starting at the subject. Only for an answer
 *  the panel shows (cohort.ts `shows`): it refuses a metric FEATURED does not name and a subject that draws no bar (one
 *  with no fact, which the service lists only as `subject`, outside `peers`, or a withheld one), since a ranked company
 *  chart starts at its subject, as the engine's sweeps refused one before this builder (E251's PR 1). */
export function peerChartDef(answer: PeerComparisonResponse): BarChartDef {
  const metric = metricOf(answer.concept)
  if (!metric) throw new Error(`peerChartDef: no metric names "${answer.concept}"`)
  const entries = drawn(answer)
  const subject = entries.findIndex((entry) => entry.is_subject)
  if (subject < 0) throw new Error(`peerChartDef: the subject ${answer.subject.ticker} draws no bar on ${answer.concept}, so a chart that starts at it draws none`)
  // A subject drawn past companies ranked above it that the chart leaves out stands after a gap (E258), so its bar never
  // reads as next in rank; it is never the first bar, since the top companies come before it.
  const broken = breaksBefore(answer)
  const categories = slotsOf(entries).map((slot, i) => (broken && i === subject ? { ...slot, gapBefore: true as const } : slot))
  return {
    id: 'sector-peers',
    // The plot announces "{title} chart", and its values stop "{title} chart values".
    title: metric.label,
    categories,
    series: { key: answer.concept, label: metric.label, values: entries.map((entry) => entry.value) },
    axis: axisOf(metric.fmt, answer.unit),
    start: categories[subject].key,
    reading: COMPANY_READING,
  }
}

/** The answer's model and each company's readout, for the panel's plot. */
export function peerChart(answer: PeerComparisonResponse): { model: ChartModel; reads: PeriodReadout[] } {
  const entries = drawn(answer)
  const model = buildBarChart(peerChartDef(answer))
  return { model, reads: readouts(model, peerDescriber(answer, entries, slotsOf(entries))) }
}

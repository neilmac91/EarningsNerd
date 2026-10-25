/* =============================================================================
   chart-table-agreement.spec.ts — M15: a chart and the metrics table print one number (E194)
   -----------------------------------------------------------------------------
   docs/design/analysis-trend-charts-spec-2026-10.md §6, M15: every value a trend chart prints agrees with the metrics
   table's cell for the same figure, the minus sign's code point aside (the chart prints U+2212, the table "-"). Each
   prints at its own precision, the chart often coarser ("$16B" on a phone's bar against the table's "$16.1B"), so the
   check is that both strings could print one value: they lie less than half a unit of each one's last digit apart,
   |chart − table| < (unit_chart + unit_table) / 2, so two strings at one precision agree only when they are equal.
   Rounding either to the other's precision cannot be the
   test: "$16B" cannot be rounded to a tenth, and "$89.5B" rounds to $90B where the true $89.498B prints "$89B" (spec
   §0.5 records this reading). Each chart string is also held within half its own unit of the true value, so a figure
   from the wrong period or series fails even where the two could agree.

   Every printed value of every chart on the 19 fixtures, card and expanded, at a phone's, a desktop card's and an
   expanded plot's width: bar and growth labels, A13b's near-zero labels, the off-scale values, the expanded strip's
   cells, the legend's latest values (and the period a stale one names), and the tooltip's readouts. The table's cell
   is built as MetricsTable builds it (formatTableValue at the cell's budget, by its calculated mark and note letter),
   its growth as the table prints a YoY (formatTableGrowth): the chart's growth panel is always YoY, where a quarterly
   table shows QoQ when it has it, so the agreement is with the YoY the table prints beside or in place of it.
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { layoutChart } from '@/features/analysis/lib/charts/layout'
import { buildChartModel, CHART_IDS, type ChartModel, type ChartView } from '@/features/analysis/lib/charts/model'
import { chartReadouts } from '@/features/analysis/lib/charts/readout'
import { resolveDataNotes, type DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { formatTableGrowth, formatTableValue, tableTokenBudget } from '@/features/analysis/lib/tableFormat'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { dataset: AnalysisDataset }>
}
const NAMES = Object.keys(FIXTURE.datasets)

const UNIT: Record<string, number> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 }

/** A printed number: its value and one unit in its last digit. "−$3.6M" → −3.6e6 ± 1e5; "CHF 20.45B", "+28.0%",
 *  "-12.3pp" and "1,234%" read the same way, a currency prefix or code and a sign of either kind aside. */
export function printed(text: string): { value: number; unit: number } {
  const bare = text.replace(/^[−-]/, '-').replace(/^\+/, '').replace(/^(-?)(?:[A-Z]{2,3}\s|[A-Z]{0,2}\$|[¥€£₹])/, '$1').replace(/,/g, '').replace(/(%|pp|×)$/, '')
  const match = /^(-?\d+(?:\.(\d+))?)([KMBT]?)$/.exec(bare)
  if (!match) throw new Error(`not a printed number: ${text}`)
  const scale = UNIT[match[3]] ?? 1
  return { value: Number(match[1]) * scale, unit: 10 ** -(match[2]?.length ?? 0) * scale }
}

/** The metrics table's cell for a series key (`concept`, or `concept:yoy` for its YoY) and period, as MetricsTable
 *  formats it; null where the table prints no number. */
function tableCell(dataset: AnalysisDataset, notes: DataNotesModel, key: string, period: string): { text: string; truth: number } | null {
  const [concept, basis] = key.split(':')
  const series = dataset.series.find((candidate) => candidate.concept === concept) as AnalysisSeries
  const point = series?.points.find((candidate) => candidate.period === period)
  if (!point) return null
  if (basis === 'yoy') {
    if (typeof point.yoy !== 'number') return null
    return { text: formatTableGrowth(point.yoy, series.percent, tableTokenBudget(false, notes.noteForComparison(point, 'yoy')?.letter)), truth: series.percent ? point.yoy : point.yoy * 100 }
  }
  if (point.value == null) return null
  const calculated = point.provenance?.method === 'calculated' || (!point.provenance && Boolean(point.derived))
  return { text: formatTableValue(point.value, series, tableTokenBudget(calculated, notes.noteFor(point)?.letter)), truth: point.value }
}

/** Whether two printed numbers could be one value's: each prints the values less than half its unit from it. */
export function agree(a: { value: number; unit: number }, b: { value: number; unit: number }): boolean {
  return Math.abs(a.value - b.value) < (a.unit + b.unit) / 2 - 1e-9 * Math.max(a.unit, b.unit)
}

interface Printed { where: string; key: string; period: string; text: string }

/** Every value one chart prints in `view` at `width`, with the series and period it reads. */
function printedValues(model: ChartModel, view: ChartView, width: number): Printed[] {
  const layout = layoutChart(model, width, view)
  const marks = model.panels.flatMap((panel) => panel.marks)
  const byLabel = (label: string) => marks.find((mark) => mark.label === label)!
  const values: Printed[] = []
  for (const box of layout.panels) {
    for (const bar of box.bars) if (bar.label) values.push({ where: 'bar label', key: bar.seriesKey, period: bar.period, text: bar.label.text })
    const signed = box.panel.marks.find((mark) => mark.kind === 'signedBar')
    for (const label of box.nearZero) values.push({ where: 'near-zero label', key: signed!.seriesKey, period: label.period, text: label.text })
    for (const band of [box.offAbove, box.offBelow]) for (const item of band?.items ?? []) values.push({ where: 'off-scale value', key: item.seriesKey, period: item.period, text: item.text })
  }
  if (layout.stripTop != null) for (const row of model.strip) for (const [period, text] of Object.entries(row.cells)) {
    if (text !== '—' && text !== 'n/m') values.push({ where: 'strip cell', key: byLabel(row.label).seriesKey, period, text })
  }
  return values
}

describe.each(NAMES)('%s: every value a chart prints agrees with the metrics table (M15)', (name) => {
  it.each(CHART_IDS)('%s', (chart) => {
    const dataset = structuredClone(FIXTURE.datasets[name].dataset)
    const notes = resolveDataNotes(dataset)
    const model = buildChartModel(chart, dataset, notes)
    if (model.unavailable) return
    const marks = model.panels.flatMap((panel) => panel.marks)
    const values: Printed[] = []
    for (const view of ['card', 'expanded'] as ChartView[]) for (const width of [342, 502, 1030]) {
      values.push(...printedValues(model, view, width).map((value) => ({ ...value, where: `${value.where}, ${view} at ${width} px` })))
    }
    // The legend's latest value, and the period a stale one names (" (FY2024)").
    for (const item of model.legend) {
      if (!item.value) continue
      const mark = marks.find((candidate) => candidate.label === item.label)!
      const latest = [...mark.points].reverse().find((point) => point.value != null)!.period
      const named = /\(([^)]+)\)$/.exec(item.value)?.[1]
      expect(named ?? null, `${item.label}: names its period when it is not the window's last`).toBe(latest === model.periods.at(-1)!.key ? null : formatAnalysisPeriod(latest, 'short'))
      values.push({ where: 'legend value', key: mark.seriesKey, period: latest, text: item.value.replace(/\s*\([^)]*\)$/, '') })
    }
    for (const readout of chartReadouts(model, dataset, notes)) for (const row of readout.rows) {
      if (row.value) values.push({ where: 'tooltip', key: row.seriesKey, period: readout.period, text: row.value })
    }
    expect(values.length, 'the chart prints values').toBeGreaterThan(0)

    const disagree: string[] = []
    for (const value of values) {
      const cell = tableCell(dataset, notes, value.key, value.period)
      if (!cell) {
        disagree.push(`${value.where} ${value.key} ${value.period} "${value.text}": the table prints no number`)
        continue
      }
      const chartNumber = printed(value.text)
      const tableNumber = printed(cell.text)
      if (!agree(chartNumber, tableNumber)) {
        disagree.push(`${value.where} ${value.key} ${value.period}: the chart's "${value.text}", the table's "${cell.text}"`)
      }
      if (Math.abs(chartNumber.value - cell.truth) > chartNumber.unit / 2 + 1e-9 * Math.abs(cell.truth)) {
        disagree.push(`${value.where} ${value.key} ${value.period}: "${value.text}" is not ${cell.truth}`)
      }
    }
    expect(disagree).toEqual([])
  })
})

describe('reading a printed number', () => {
  it.each([
    ['$14.3B', 14.3e9, 0.1e9],
    ['−$3.6M', -3.6e6, 0.1e6],
    ['-$3.6M', -3.6e6, 0.1e6],
    ['$0.61B', 0.61e9, 0.01e9],
    ['CHF 20.45B', 20.45e9, 0.01e9],
    ['20.5B', 20.5e9, 0.1e9],
    ['+28.0%', 28, 0.1],
    ['−5,619%', -5619, 1],
    ['$0', 0, 1],
    ['¥2B', 2e9, 1e9],
    ['CA$2.5B', 2.5e9, 0.1e9],
    ['+1.2pp', 1.2, 0.1],
  ] as const)('%s', (text, value, unit) => {
    const read = printed(text)
    expect(read.value).toBeCloseTo(value, 6)
    expect(read.unit).toBeCloseTo(unit, 9)
  })

  it('and the agreement it allows: one value each string could print, and no further', () => {
    const both = (a: string, b: string) => agree(printed(a), printed(b))
    expect(both('$89B', '$89.5B')).toBe(true) // $89.498B prints both
    expect(both('$0.61B', '$608.2M')).toBe(true)
    expect(both('$16B', '$16.1B')).toBe(true)
    expect(both('$16B', '$16.6B')).toBe(false) // $16.6B prints "$17B"
    expect(both('+28.0%', '+28.1%')).toBe(false) // one precision: equal or not at all
    expect(both('+28.0%', '+28.0%')).toBe(true)
    expect(both('−$3.6M', '-$3.6M')).toBe(true)
    expect(both('−$3.6M', '$3.6M')).toBe(false)
  })
})

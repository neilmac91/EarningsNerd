/* =============================================================================
   chart-readout.spec.ts — the trend charts' per-period readout (features/analysis/lib/charts/readout.ts)
   -----------------------------------------------------------------------------
   What the spec renderer's tooltip prints and its values stop says for each period (docs/design/analysis-trend-
   charts-spec-2026-10.md §3.9, §3.13; DESIGN_SYSTEM.md §10): the period and its end date, one row per drawn series in
   legend order, each value at tooltip precision (§3.1), its state text, "Calculated" for a calculated point, and its
   own note letter, value and YoY notes independent. Every fixture dataset and chart, plus synthetic notes. The golden
   plans (chart-engine.spec.ts) carry the six golden datasets' announcements.
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { buildChartModel, CHART_IDS, isCalculated } from '@/features/analysis/lib/charts/model'
import { chartReadouts, periodEndText } from '@/features/analysis/lib/charts/readout'
import { tooltipMoney } from '@/features/analysis/lib/charts/scale'
import { resolveDataNotes } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
}
const DATASETS = Object.keys(FIXTURE.datasets)
const dataset = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)

function readouts(ds: AnalysisDataset, chart: (typeof CHART_IDS)[number]) {
  const notes = resolveDataNotes(ds)
  const model = buildChartModel(chart, ds, notes)
  return { model, notes, readouts: chartReadouts(model, ds, notes) }
}

describe('tooltip precision (spec §3.1): 4 significant figures in the amount’s own unit', () => {
  it.each([
    [14_340_000_000, 'USD', '$14.34B'],
    [14_340_000_000, null, '14.34B'],
    [1_234_000_000, 'USD', '$1.234B'],
    [-987_600_000, 'USD', '−$987.6M'],
    [85_000_000, 'USD', '$85.00M'],
    [999_960_000, 'USD', '$1.000B'],
    [9_999_600_000, 'USD', '$10.00B'],
    [-3_588_000, 'USD', '−$3.588M'],
    [133_000, 'USD', '$133.0K'],
    [850, 'USD', '$850.0'],
    [0, 'USD', '$0'],
    [20_450_000_000, 'CHF', 'CHF 20.45B'],
  ] as const)('%d %s → %s', (value, currency, text) => {
    expect(tooltipMoney(value, currency)).toBe(text)
  })
})

describe('a period’s end date reads without a time zone', () => {
  it.each([
    ['2025-12-31', 'Dec 31, 2025'],
    ['2024-02-03', 'Feb 3, 2024'],
    ['2026-06-30T00:00:00Z', 'Jun 30, 2026'],
    ['', null],
    ['2025-13-01', null],
    [undefined, null],
  ] as const)('%s → %s', (input, text) => {
    expect(periodEndText(input)).toBe(text)
  })
})

describe.each(DATASETS)('%s: every chart’s readout', (name) => {
  it.each(CHART_IDS)('%s', (chart) => {
    const ds = dataset(name)
    const { model, notes, readouts: all } = readouts(ds, chart)
    if (model.unavailable) {
      expect(all, 'a chart that does not apply has nothing to read out').toEqual([])
      return
    }
    expect(all.map((readout) => readout.period)).toEqual(model.periods.map((period) => period.key))
    const marks = model.panels.flatMap((panel) => panel.marks.map((mark) => ({ mark, panel })))
    // §3.5: legend order, colour, shape and tooltip rows are one list; an absent series has no row.
    const legend = model.legend.filter((item) => !item.absent)
    if (legend.length) expect(marks.map(({ mark }) => [mark.label, mark.color, mark.marker ?? null])).toEqual(legend.map((item) => [item.label, item.color, item.marker ?? null]))
    const ends = new Map(ds.periods.map((period) => [period.key, period.period_end]))
    for (const readout of all) {
      const period = formatAnalysisPeriod(readout.period)
      const end = periodEndText(ends.get(readout.period))
      const endSpoken = periodEndText(ends.get(readout.period), true)
      const span = ds.mode === 'annual' ? 'year' : 'quarter'
      expect(readout.header).toBe(end ? `${period} · ${span} ended ${end}` : period)
      expect(readout.announcement.startsWith(end ? `${period}, ${span} ended ${endSpoken}. ` : `${period}. `)).toBe(true)
      // Nothing a screen reader garbles: no middle dot, dash, n/m, unit letter, YoY, month abbreviation or U+2212.
      expect(readout.announcement).not.toMatch(/[·—−]|n\/m|\d[KMBT]\b|YoY|\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/)
      expect(readout.rows.map((row) => [row.seriesKey, row.label, row.color, row.swatch, row.marker ?? null]))
        .toEqual(marks.map(({ mark }) => [mark.seriesKey, mark.label, mark.color, mark.kind === 'line' ? 'line' : 'bar', mark.marker ?? null]))
      readout.rows.forEach((row, i) => {
        const { mark, panel } = marks[i]
        const growth = mark.kind === 'growth'
        const point = mark.points.find((candidate) => candidate.period === readout.period)!
        const source = ds.series.find((series) => series.concept === mark.seriesKey.split(':')[0])!.points.find((candidate) => candidate.period === readout.period)
        // The value at tooltip precision, in the panel's own format; the true value even when it is off scale.
        expect(row.value).toBe(point.value == null ? null
          : panel.axis.format.kind === 'money' ? tooltipMoney(point.value, panel.currency) : panel.axis.format.value(point.value, 1))
        expect(row.state).toBe(point.value != null ? (point.offscale ? 'off-scale' : null)
          : point.nm ? 'not-meaningful' : point.structural ? 'no-prior-year' : 'unavailable')
        expect(row.calculated, '"Calculated" marks a calculated value, never a growth rate').toBe(!growth && isCalculated(source))
        const note = growth ? source && notes.noteForComparison(source, 'yoy') : notes.noteFor(source ?? { value: null })
        expect(row.note).toBe(note?.letter ?? null)
        expect(row.noteTone, 'a review note takes the review ink, as in the band').toBe(note?.kind === 'review' ? 'review' : 'neutral')
        expect(row.text).toBe([row.figure, row.calculated ? '· Calculated' : null, row.note ? `(${row.note})` : null].filter(Boolean).join(' '))
        expect(row.text, 'never the † glyph: the word Calculated stands for it').not.toContain('†')
        if (row.note) expect(readout.announcement).toContain(`data note ${row.note}`)
      })
      // §3.13: the announcement carries the period's band notes, each in the row it belongs to.
      const band = (model.notesBand?.[readout.period] ?? []).map((glyph) => glyph.text)
      expect(new Set(readout.rows.flatMap((row) => (row.note ? [row.note] : [])))).toEqual(new Set(band.filter((glyph) => glyph !== '†')))
      if (band.includes('†')) expect(readout.rows.some((row) => row.calculated), '† in the band: a row says Calculated').toBe(true)
    }
  })
})

describe('the rows’ text, as the tooltip prints it and the status says it', () => {
  it('a missing value, a structural and an n/m growth slot, and a zero', () => {
    const { readouts: all } = readouts(dataset('RIVN_annual'), 'topline')
    const at = (period: string) => all.find((readout) => readout.period === period)!
    expect(at('FY2018').rows.map((row) => row.text)).toEqual(['Unavailable (a)', 'Unavailable'])
    expect(at('FY2018').announcement).toBe('FY2018, year ended December 31, 2018. Revenue: unavailable, data note a. Year-over-year growth: unavailable.')
    expect(at('FY2020').rows.map((row) => row.text)).toEqual(['$0', 'n/m · not meaningful'])
    expect(at('FY2020').announcement).toBe('FY2020, year ended December 31, 2020. Revenue: $0. Year-over-year growth: not meaningful.')
    const lcid = readouts(dataset('LCID_annual'), 'topline').readouts
    expect(lcid[0].rows[1].text).toBe('No prior-year period in this window')
    expect(lcid[0].announcement).toBe('FY2019, year ended December 31, 2019. Revenue: $4.590 million. Year-over-year growth: not available, no prior-year period in this window.')
  })

  it('an off-scale value prints its true value, and a calculated one says so', () => {
    const { readouts: all } = readouts(dataset('LCID_annual'), 'margins')
    expect(all[0].rows.map((row) => row.text)).toEqual(['14.5% · Calculated', '−5,619% (off scale) · Calculated', '−6,043% (off scale) · Calculated'])
    expect(all[0].announcement).toBe('FY2019, year ended December 31, 2019. Gross margin: 14.5%, calculated. Operating margin: minus 5,619%, off scale, calculated. Net margin: minus 6,043%, off scale, calculated.')
    const growth = readouts(dataset('LCID_annual'), 'topline').readouts.find((readout) => readout.period === 'FY2021')!
    expect(growth.rows[1].text).toBe('+581.9% (off scale)')
  })

  it('a quarter reads as the app prints it, with its quarter end', () => {
    const { readouts: all } = readouts(dataset('PGR_quarterly'), 'topline')
    expect(all.find((readout) => readout.period === '2024Q1')!.header).toBe('Q1 2024 · quarter ended Mar 31, 2024')
  })

  it('a value note and its YoY note are independent: each row carries its own letter', () => {
    const ds = dataset('REGN_annual')
    delete (ds as { data_notes?: unknown }).data_notes
    const review = (reason: string) => ({ version: 1 as const, method: 'reported' as const, validation: 'needs_review' as const, reasons: [reason], formula: null, inputs: [] })
    const revenue = ds.series.find((series) => series.concept === 'revenue')!
    const point = (period: string) => revenue.points.find((candidate) => candidate.period === period)!
    point('FY2023').provenance = review('value_reason')
    Object.assign(point('FY2024'), { yoy_provenance: { ...review('yoy_reason'), method: 'calculated' as const } })
    const { readouts: all } = readouts(ds, 'topline')
    const row = (period: string) => all.find((readout) => readout.period === period)!.rows
    const [value2023, growth2023] = row('FY2023')
    const [value2024, growth2024] = row('FY2024')
    expect(value2023.note, 'the value’s note').not.toBeNull()
    expect(growth2023.note, 'a clean comparison carries no letter').toBeNull()
    expect(value2024.note, 'a clean value carries no letter').toBeNull()
    expect(growth2024.note, 'the comparison’s own note').not.toBeNull()
    expect(growth2024.note).not.toBe(value2023.note)
    expect(all.find((readout) => readout.period === 'FY2024')!.announcement).toMatch(new RegExp(`Year-over-year growth: plus \\S+, data note ${growth2024.note}\\.$`))
  })

  it('a dataset without an end date prints the period alone', () => {
    const ds = dataset('REGN_annual')
    for (const period of ds.periods) period.period_end = ''
    const { readouts: all } = readouts(ds, 'cash')
    expect(all[0].header).toBe('FY2016')
    expect(all[0].announcement.startsWith('FY2016. Operating cash flow: $')).toBe(true)
  })
})

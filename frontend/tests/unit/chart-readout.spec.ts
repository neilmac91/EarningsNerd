/* =============================================================================
   chart-readout.spec.ts — the trend charts' per-period readout (features/analysis/lib/charts/readout.ts)
   -----------------------------------------------------------------------------
   What the spec renderer's tooltip prints and its values stop says for each period (docs/design/analysis-trend-
   charts-spec-2026-10.md §3.9, §3.13; DESIGN_SYSTEM.md §10): the period and its end date, one row per drawn series in
   legend order, each value at tooltip precision (§3.1), its state text, "Calculated" for a calculated point, and its
   own note letter where that note questions the number (D-061), value and YoY notes independent. Every fixture dataset
   and chart, plus synthetic notes. The golden
   plans (chart-engine.spec.ts) carry the six golden datasets' announcements. The core under them, `readouts`, reads any
   model through a describer: every bar chart case (barChart.ts, E195 (D)) with Financial trends' own, and every ranked
   company chart (E251) with the Sector peers panel's, whose context bars' rows say so, for their swatches.
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { buildBarChart } from '@/features/analysis/lib/charts/barChart'
import { buildChartModel, CHART_IDS, isCalculated } from '@/features/analysis/lib/charts/model'
import { chartReadouts, periodEndText, periodHeader, readouts as coreReadouts, type ReadoutDescriber } from '@/features/analysis/lib/charts/readout'
import { tooltipMoney } from '@/features/analysis/lib/charts/scale'
import { markedNote, resolveDataNotes } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { slotsOf, trendDescriber } from '@/features/fundamentals/lib/trendChart'
import { drawn } from '@/features/peers/lib/cohort'
import { peerChart } from '@/features/peers/lib/peerChart'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { barCases, barSeries, peerBarCases, withMixedNotes, type BarFixture, type PeerFixture } from './chartPlan'

// The fixture's datasets and MIXED_NOTES, which meets every kind of note a band can (chartPlan.ts).
const FIXTURE = withMixedNotes(JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
})
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
        // D-061: a letter only where the note questions the number; a gap and a record-only note give none.
        expect(row.note).toBe(markedNote(note)?.letter ?? null)
        expect(row.text).toBe([row.figure, row.calculated ? '· Calculated' : null, row.note ? `(${row.note})` : null].filter(Boolean).join(' '))
        expect(row.text, 'never the † glyph: the word Calculated stands for it').not.toContain('†')
        if (row.note) expect(readout.announcement).toContain(`data note ${row.note}`)
      })
      expect(readout.announcement.match(/data note/g)?.length ?? 0, 'a note is spoken only where a letter shows').toBe(readout.rows.filter((row) => row.note).length)
      // §3.13: the announcement carries the period's band letters, each in the row it belongs to.
      const band = (model.notesBand?.[readout.period] ?? []).map((glyph) => glyph.text)
      expect(new Set(readout.rows.flatMap((row) => (row.note ? [row.note] : [])))).toEqual(new Set(band))
    }
  })
})

describe('the rows’ text, as the tooltip prints it and the status says it', () => {
  it('a missing value, a structural and an n/m growth slot, and a zero', () => {
    const { readouts: all } = readouts(dataset('RIVN_annual'), 'topline')
    const at = (period: string) => all.find((readout) => readout.period === period)!
    // A gap's note marks nothing (D-061): the footnote line says why the value is missing.
    expect(at('FY2018').rows.map((row) => row.text)).toEqual(['Unavailable', 'Unavailable'])
    expect(at('FY2018').announcement).toBe('FY2018, year ended December 31, 2018. Revenue: unavailable. Year-over-year growth: unavailable.')
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

describe('the core reads any model through a describer: every bar chart case (barChart.ts, E195 (D))', () => {
  const BAR_FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/fundamentals-datasets.json', 'utf8')) as BarFixture
  const BARS = barCases(BAR_FIXTURE)
  const model = (name: string) => buildBarChart(structuredClone(BARS.find(([caseName]) => caseName === name)![1]))
  /** Financial trends' own describer over its own slots (features/fundamentals/lib/trendChart.ts), as its card builds
   *  them: a fiscal year and its end date, and calculated from its point's provenance. It has no data notes. */
  const financialTrends = (name: string): ReadoutDescriber => {
    const points = barSeries(BAR_FIXTURE, name).points
    return trendDescriber(slotsOf(points), points)
  }

  it.each(BARS.map(([name]) => name))('%s', (name) => {
    const m = model(name)
    const all = coreReadouts(m, financialTrends(name))
    const points = barSeries(BAR_FIXTURE, name).points
    expect(all.map((readout) => readout.period)).toEqual(m.periods.map((period) => period.key))
    const [panel] = m.panels
    const [mark] = panel.marks
    all.forEach((readout, i) => {
      const point = points[i]
      const end = periodEndText(point.period_end)
      expect(readout.header).toBe(end ? `FY${point.fiscal_year} · year ended ${end}` : `FY${point.fiscal_year}`)
      expect(readout.announcement.startsWith(`FY${point.fiscal_year}, year ended ${periodEndText(point.period_end, true)}. ${mark.label}: `)).toBe(true)
      expect(readout.announcement).not.toMatch(/[·—−×]|n\/m|\d[KMBT]\b|\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/)
      const [row] = readout.rows
      expect([readout.rows.length, row.seriesKey, row.label, row.color, row.swatch]).toEqual([1, mark.seriesKey, mark.label, 0, 'bar'])
      const modelPoint = mark.points[i]
      expect(row.value).toBe(modelPoint.value == null ? null : panel.axis.format.tip(modelPoint.value))
      expect(row.state).toBe(modelPoint.value == null ? 'unavailable' : modelPoint.offscale ? 'off-scale' : null)
      expect(row.calculated, 'calculated read from provenance, and only for a value that is there').toBe(point.value != null && point.provenance?.method === 'calculated')
      expect(row.note, 'no data notes, so no letter').toBeNull()
      expect(row.text).toBe([row.figure, row.calculated ? '· Calculated' : null].filter(Boolean).join(' '))
    })
  })

  it('a category’s header is its long name when the describer names none, shown and spoken', () => {
    const all = coreReadouts(model('AAPL revenue'))
    expect(all.map((readout) => readout.header)).toEqual(['FY2023', 'FY2024', 'FY2025'])
    expect(all[2].announcement).toBe('FY2025. Revenue: $416.2 billion.')
  })

  it('with no notes, no row carries a letter and none is spoken; a calculated value says so in both', () => {
    const all = coreReadouts(model('AAPL net margin'), financialTrends('AAPL net margin'))
    expect(all.flatMap((readout) => readout.rows.map((row) => row.note))).toEqual([null, null, null])
    expect(all[2].header).toBe('FY2025 · year ended Sep 27, 2025')
    expect(all[2].rows[0].text).toBe('26.9% · Calculated')
    expect(all[2].announcement).toBe('FY2025, year ended September 27, 2025. Net margin: 26.9%, calculated.')
    expect(all.some((readout) => /data note/.test(readout.announcement))).toBe(false)
    // A withheld value is never calculated, whatever its provenance's method.
    const withheld = coreReadouts(model('Withheld diluted EPS'), financialTrends('Withheld diluted EPS'))
    expect(withheld.map((readout) => readout.rows[0].text)).toEqual(['Unavailable', 'Unavailable', 'Unavailable'])
  })

  it('a ratio is spoken as times, a per-share amount in cents, and a clipped bar’s true value off scale', () => {
    expect(coreReadouts(model('AAPL current ratio'), financialTrends('AAPL current ratio'))[1].announcement)
      .toBe('FY2025, year ended September 27, 2025. Current ratio: 0.89 times, calculated.')
    const eps = coreReadouts(model('Penny diluted EPS'), financialTrends('Penny diluted EPS'))
    expect(eps.map((readout) => readout.rows[0].text)).toEqual(['$0.31', 'Unavailable', '−$0.12'])
    expect(eps[2].announcement).toBe('FY2025, year ended December 31, 2025. Diluted EPS: minus $0.12.')
    expect(coreReadouts(model('Extreme net margin'), financialTrends('Extreme net margin'))[0].rows[0].text).toBe('−18,093% (off scale) · Calculated')
  })

  it('periodHeader: a period and its end, as the tooltip prints them and a screen reader says them, or the name alone', () => {
    expect(periodHeader('FY2025', 'year', '2025-09-27')).toEqual({ shown: 'FY2025 · year ended Sep 27, 2025', spoken: 'FY2025, year ended September 27, 2025' })
    expect(periodHeader('Q2 2026', 'quarter', '2026-06-30').shown).toBe('Q2 2026 · quarter ended Jun 30, 2026')
    expect([periodHeader('FY2025', 'year', null), periodHeader('FY2025', 'year', 'unknown')]).toEqual([{ shown: 'FY2025', spoken: 'FY2025' }, { shown: 'FY2025', spoken: 'FY2025' }])
  })
})

describe('a ranked company chart’s readouts (E251): a company a readout, through the Sector peers panel’s describer', () => {
  const FIXTURE_PEERS = JSON.parse(readFileSync('tests/unit/fixtures/peers-cohorts.json', 'utf8')) as PeerFixture
  // Every cohort the panel shows, as its own builder draws it (features/peers/lib/peerChart.ts).
  const PEERS = peerBarCases(FIXTURE_PEERS)

  it.each(PEERS.map(([name]) => name))('%s', (name) => {
    const answer = FIXTURE_PEERS.cases[name].response
    const { model: m, reads: all } = peerChart(answer)
    const entries = drawn(answer)
    const ranked = answer.peers.filter((entry) => entry.value != null).length
    const [panel] = m.panels
    const [mark] = panel.marks
    expect(all.map((readout) => readout.period)).toEqual(m.periods.map((period) => period.key))
    all.forEach((readout, i) => {
      const point = mark.points[i]
      const entry = entries[i]
      // The tooltip heads a company with its ticker, its name (two companies can answer one ticker), its rank over the
      // companies with a value and its own fiscal year, which can differ by company; the values stop says its name, its
      // ticker, "this company" for the one the page is about, its rank and its year (no "·", "#" or unit letter).
      expect(readout.header).toBe(`${entry.ticker} · ${formatCompanyName(entry.company_name)} · #${entry.rank} of ${ranked} · FY${entry.fiscal_year} · year ended ${periodEndText(entry.period_end)}`)
      const spoken = `${formatCompanyName(entry.company_name)}, ${entry.ticker}, ${entry.is_subject ? 'this company, ' : ''}rank ${entry.rank} of ${ranked}, FY${entry.fiscal_year}, year ended ${periodEndText(entry.period_end, true)}. ${mark.label}: `
      expect(readout.announcement.startsWith(spoken), `${point.period}: "${readout.announcement}"`).toBe(true)
      expect(readout.announcement).not.toMatch(/[·#]/)
      const [row] = readout.rows
      expect([readout.rows.length, row.seriesKey, row.label, row.color, row.swatch]).toEqual([1, mark.seriesKey, mark.label, 0, 'bar'])
      // A context bar's row carries the flag its swatch paints by (LegendSwatch, E236), and only that row.
      expect(row.context, `${point.period}: the row is its bar’s`).toBe(point.context)
      expect(row.value).toBe(point.value == null ? null : panel.axis.format.tip(point.value))
      // A figure the backend derived (a margin) reads "Calculated", from its own provenance.
      expect(row.calculated, `${point.period}: calculated as its provenance says`).toBe(entry.provenance?.method === 'calculated')
    })
    expect(all.some((readout) => readout.rows[0].context) && all.some((readout) => !readout.rows[0].context), 'a subject and a context company').toBe(true)
  })
})

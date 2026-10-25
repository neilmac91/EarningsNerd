/**
 * The trend charts' model: dataset → panels, scales, marks, legend, notes band and footnotes (§3 and §4 of
 * docs/design/analysis-trend-charts-spec-2026-10.md, whose §0.5 says where this engine departs from it). A
 * renderer draws only what this module, layout.ts and readout.ts return; it never computes a domain, a tick, a label,
 * a position or a colour. Pure and SSR-safe.
 */
import type { AnalysisDataset, AnalysisPoint, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { resolveDataNotes, type DataNote, type DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { annualTickLabel, formatAnalysisPeriod, formatAnalysisWindow, quarterlyTickLines } from '@/features/analysis/lib/periodLabels'
import { currencySymbol } from '@/lib/format'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { outlierCut, valueAxis, type AxisFormat } from './scale'

export type ChartId = 'topline' | 'margins' | 'cash' | 'balance'
export type ChartView = 'card' | 'expanded'
export type Marker = 'circle' | 'square' | 'triangle'

export interface ChartPeriod {
  key: string
  tick: [string] | [string, string]
  long: string
}

export interface ModelPoint {
  period: string
  value: number | null
  /** Set on a percent panel's clipped value (A3); the value stays the true one. */
  offscale?: 'above' | 'below'
  /** A growth slot that is not meaningful: a zero base or a sign change. */
  nm?: boolean
  /** A growth slot whose year-earlier period comes before the window (A11's structural state). */
  structural?: boolean
}

export interface ModelMark {
  kind: 'bar' | 'line' | 'growth' | 'signedBar'
  seriesKey: string
  label: string
  /** Index into the chart palette (chart-1..6), in order over the series present (A8). */
  color: number
  marker?: Marker
  points: ModelPoint[]
  /** Values printed on the marks (Revenue & growth). */
  labelled: boolean
}

export interface ModelPanel {
  id: string
  caption: string | null
  /** Share of the chart's flexible height. */
  weight: number
  axis: { domain: [number, number]; ticks: number[]; step: number; format: AxisFormat }
  marks: ModelMark[]
  /** The A1 cap on intervals, kept on the panel so the checks can hold it. */
  nmax: number
  /** The amounts' ISO 4217 currency, or null for a percent panel or an amount with no currency. */
  currency: string | null
}

export interface NoteGlyph {
  text: string
  /** Review-kind letters take warning ink; every other glyph the chart's label ink. */
  tone: 'review' | 'neutral'
}

export interface LegendItem {
  /** The name; an absent series' item reads "Long-term debt · not in dataset", all of it the name. */
  label: string
  /** The palette slot; null for an absent series, which claims none. */
  color: number | null
  swatch: 'bar' | 'line'
  marker?: Marker
  /** The latest available value, with its period when that is not the window's last. */
  value?: string
  /** A series with no value in the window: neutral dashed swatch, no value, never drawn as zero. */
  absent: boolean
}

export interface Footnote {
  /** The glyph the line explains ("a", "†", "—", "n/m", "↓↑"), or '' for a plain sentence. */
  mark: string
  text: string
}

export interface StripRow {
  label: string
  /** The row label the strip prints: the legend name's first 6 characters (spec §0.4 row 22). */
  short: string
  color: number
  /** The legend's swatch: a line series' marker, or equity's bar. */
  swatch: 'bar' | 'line'
  marker?: Marker
  cells: Record<string, string>
}

export interface ChartModel {
  id: ChartId
  title: string
  subtitle: string
  mode: AnalysisDataset['mode']
  periods: ChartPeriod[]
  panels: ModelPanel[]
  legend: LegendItem[]
  /** Glyphs per period: the union of the plotted series' note letters, plus † where a partly calculated
   *  series was calculated. Null when no period has one. */
  notesBand: Record<string, NoteGlyph[]> | null
  footnotes: Footnote[]
  /** Set when the chart does not apply to this dataset: one sentence, at the card's full height. */
  unavailable: string | null
  /** The expanded view's value strip: every value of every plotted series not labelled in the plot. */
  strip: StripRow[]
}

const MARKERS: Marker[] = ['circle', 'square', 'triangle']

/** A1's interval cap for each panel's axis, fixed so every view shows the same ticks. */
export const AXIS_CAPS = { topline: 5, growth: 4, margins: 8, cash: 8, debtcash: 6, equity: 4 } as const
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The top line the first chart plots: revenue, else a bank's net interest income, else an insurer's
 *  premiums earned. */
export const TOP_LINE_CONCEPTS = ['revenue', 'net_interest_income', 'premiums_earned'] as const

/** The year's apostrophe is the typographic one (spec §0.4 row 27), as the subtitle and footnotes print
 *  periods ("Q1 ’25"). Today's Recharts ticks keep periodAxis's ASCII form until this renderer replaces them. */
const typographic = (tick: string) => tick.replace("'", '’')

function periodsOf(ds: AnalysisDataset): ChartPeriod[] {
  return ds.periods.map((period) => {
    const lines = quarterlyTickLines(period.key)
    const tick: ChartPeriod['tick'] = lines ? [lines[0], typographic(lines[1])] : [typographic(annualTickLabel(period.key))]
    return { key: period.key, tick, long: formatAnalysisPeriod(period.key) }
  })
}

/** A9: the fiscal-year end from the latest FY or fiscal-Q4 row; a 52/53-week year ending in the first
 *  week of a month belongs to the month before (LOVE's year ending 2 February reads "Jan"). */
function fiscalYearEnd(ds: AnalysisDataset): string | null {
  const rows = ds.periods.filter((period) => (period.fiscal_period === 'FY' || period.fiscal_period === 'Q4') && period.period_end)
  const month = (periodEnd: string) => {
    const [year, mon, day] = periodEnd.split('-').map(Number)
    const index = day <= 7 ? (mon + 10) % 12 : mon - 1
    return Number.isFinite(year) && Number.isFinite(index) ? MONTHS[index] : null
  }
  const last = rows.at(-1)
  const end = last ? month(last.period_end) : null
  if (!end) return null
  const changed = rows.findIndex((row, i) => i > 0 && month(row.period_end) !== month(rows[i - 1].period_end))
  const fyLabel = ds.mode === 'annual' ? 'fiscal years end' : 'fiscal year ends'
  return changed > 0 ? `${fyLabel} ${end} · fiscal year end changed in FY${rows[changed].fiscal_year}` : `${fyLabel} ${end}`
}

function subtitleOf(ds: AnalysisDataset, unit: string | null): string {
  const first = ds.periods[0]?.key
  const last = ds.periods.at(-1)?.key
  const parts = [first && last ? formatAnalysisWindow(first, last, 'short') : null, fiscalYearEnd(ds), unit]
  return parts.filter((part): part is string => !!part).join(' · ')
}

const byConcept = (ds: AnalysisDataset) => Object.fromEntries(ds.series.map((s) => [s.concept, s])) as Record<string, AnalysisSeries>

export const isCalculated = (point: AnalysisPoint | undefined) =>
  !!point && point.value != null && (point.provenance ? point.provenance.method === 'calculated' : Boolean(point.derived))

/** A series counts as present when it has a value in the window. */
const present = (series: AnalysisSeries | undefined, ds: AnalysisDataset): series is AnalysisSeries => {
  if (!series) return false
  const keys = new Set(ds.periods.map((period) => period.key))
  return series.points.some((point) => keys.has(point.period) && point.value != null)
}

/**
 * The currency every plotted amount is in. Amounts on one scale must share a currency (one label covers
 * two amounts only when both are in it), so more than one is `mixed` and the chart does not draw. A
 * point's own unit wins over its series' (E102: a series takes its first point's unit).
 */
function currencyOf(ds: AnalysisDataset, series: AnalysisSeries[]): { currency: string | null; mixed: boolean } {
  const keys = new Set(ds.periods.map((period) => period.key))
  const units = new Set<string>()
  for (const s of series) for (const point of s.points) {
    if (keys.has(point.period) && point.value != null) units.add(point.unit || s.unit)
  }
  if (units.size > 1) return { currency: null, mixed: true }
  const [unit] = [...units]
  return { currency: unit && currencySymbol(unit) ? unit : null, mixed: false }
}

/** The currency the given concepts' amounts share in the window, for a renderer outside the engine (today's charts);
 *  `mixed` when they share none, and then the chart says MIXED_CURRENCY instead of drawing. */
export function chartCurrency(ds: AnalysisDataset, concepts: string[]): { currency: string | null; mixed: boolean } {
  return currencyOf(ds, ds.series.filter((series) => concepts.includes(series.concept)))
}

function valuesOf(ds: AnalysisDataset, series: AnalysisSeries | undefined): ModelPoint[] {
  const byPeriod = new Map((series?.points ?? []).map((point) => [point.period, point]))
  return ds.periods.map(({ key }) => ({ period: key, value: byPeriod.get(key)?.value ?? null }))
}

type GrowthState = 'value' | 'structural' | 'nm-zero' | 'nm-sign' | 'unavailable'

/** The same period a year earlier, keyed as the backend's comparisons key it (FY2023 → FY2022, 2024Q2 → 2023Q2). */
const yearEarlier = (key: string) => key.replace(/^FY(\d{4})$/, (_, year) => `FY${Number(year) - 1}`).replace(/^(\d{4})(Q[1-4])$/, (_, year, quarter) => `${Number(year) - 1}${quarter}`)

/** YoY growth as percent, with the state of every slot (spec §3.4, A11). A valued slot whose year-earlier period comes
 *  before the window is structural; any other slot without a comparison (no value of its own, a gap in the window, a
 *  missing prior value) is unavailable, as D17 counts them. FY and quarter keys each sort as their periods do. */
function growthOf(ds: AnalysisDataset, series: AnalysisSeries): { points: ModelPoint[]; states: GrowthState[] } {
  const byPeriod = new Map(series.points.map((point) => [point.period, point]))
  const first = ds.periods[0]?.key ?? ''
  const states: GrowthState[] = []
  const points = ds.periods.map(({ key }): ModelPoint => {
    const point = byPeriod.get(key)
    if (typeof point?.yoy === 'number') {
      states.push('value')
      return { period: key, value: point.yoy * 100 }
    }
    const priorKey = yearEarlier(key)
    const prior = byPeriod.get(priorKey)
    const state: GrowthState = point?.yoy === 'nm' ? 'nm-sign'
      : point?.value != null && prior?.value === 0 ? 'nm-zero'
        : point?.value != null && priorKey < first ? 'structural' : 'unavailable'
    states.push(state)
    return { period: key, value: null, nm: state === 'nm-sign' || state === 'nm-zero', structural: state === 'structural' }
  })
  return { points, states }
}

const valuesIn = (marks: ModelMark[]) => marks.flatMap((mark) => mark.points.map((point) => point.value).filter((value): value is number => value != null))

function moneyPanel(id: string, caption: string | null, weight: number, nmax: number, marks: ModelMark[], currency: string | null): ModelPanel {
  return { id, caption, weight, nmax, marks, currency, axis: valueAxis(valuesIn(marks), nmax, 'money', currency) }
}

function percentPanel(id: string, caption: string | null, weight: number, nmax: number, marks: ModelMark[], signed: boolean): ModelPanel {
  const cut = outlierCut(marks.map((mark) => mark.points.map((point) => point.value).filter((value): value is number => value != null)))
  const inRange = marks.flatMap((mark, i) => mark.points.map((point) => point.value).filter((value): value is number => value != null && cut.inRange(value, i)))
  const axis = valueAxis(inRange, nmax, signed ? 'growth' : 'percent')
  for (const mark of marks) for (const point of mark.points) {
    if (point.value == null) continue
    if (point.value > axis.domain[1]) point.offscale = 'above'
    if (point.value < axis.domain[0]) point.offscale = 'below'
  }
  return { id, caption, weight, nmax, marks, currency: null, axis }
}

/** Note letters run a, b, …, z, aa, ab, …: shorter first, then alphabetical. */
const letterOrder = (a: string, b: string) => (a.length - b.length) || a.localeCompare(b)

/** A5: the notes band's glyphs and the letters the chart's footnotes explain. Value notes come from every
 *  plotted series; comparison notes only from the series whose YoY the chart draws. */
function notesBandOf(ds: AnalysisDataset, notes: DataNotesModel, series: AnalysisSeries[], yoyOf?: AnalysisSeries) {
  const keys = new Set(ds.periods.map((period) => period.key))
  const cells = new Map<string, Set<string>>()
  const dagger = new Set<string>()
  const letters = new Map<string, DataNote>()
  const add = (period: string, note: DataNote | null) => {
    if (!note || !keys.has(period)) return
    const cell = cells.get(period) ?? new Set<string>()
    cell.add(note.letter)
    cells.set(period, cell)
    letters.set(note.key, note)
  }
  const inWindow = (s: AnalysisSeries) => s.points.filter((point) => keys.has(point.period) && point.value != null)
  const partly = series.filter((s) => {
    const calculated = inWindow(s).filter(isCalculated).length
    return calculated > 0 && calculated < inWindow(s).length
  })
  for (const s of series) {
    const byPeriod = new Map(s.points.map((point) => [point.period, point]))
    for (const { key } of ds.periods) {
      // A period the series has no point for is unavailable too; it carries that note like any gap.
      add(key, notes.noteFor(byPeriod.get(key) ?? { value: null }))
      if (partly.includes(s) && isCalculated(byPeriod.get(key))) dagger.add(key)
    }
  }
  // A comparison the chart prints, as a bar or as "n/m" on the 0% rule, carries its note in the band, as the
  // footnote names it.
  if (yoyOf) for (const point of yoyOf.points) {
    if (point.yoy != null) add(point.period, notes.noteForComparison(point, 'yoy'))
  }
  const tone = new Map([...letters.values()].map((note) => [note.letter, note.kind === 'review' ? 'review' as const : 'neutral' as const]))
  const band: Record<string, NoteGlyph[]> = {}
  for (const { key } of ds.periods) {
    const glyphs: NoteGlyph[] = [...(cells.get(key) ?? [])].sort(letterOrder).map((letter) => ({ text: letter, tone: tone.get(letter) ?? 'neutral' }))
    if (dagger.has(key)) glyphs.push({ text: '†', tone: 'neutral' })
    if (glyphs.length) band[key] = glyphs
  }
  const ordered = [...letters.values()].sort((a, b) => letterOrder(a.letter, b.letter))
  return { band: Object.keys(band).length ? band : null, letters: ordered, partly }
}

/** The fiscal period after `key` (FY2023 → FY2024, 2023Q4 → 2024Q1). */
const nextPeriod = (key: string) => key
  .replace(/^FY(\d{4})$/, (_, year) => `FY${Number(year) + 1}`)
  .replace(/^(\d{4})Q([1-4])$/, (_, year, quarter) => (quarter === '4' ? `${Number(year) + 1}Q1` : `${year}Q${Number(quarter) + 1}`))

/** "FY2023–FY2025" for fiscally consecutive periods, otherwise a comma list: a run never spans a period the
 *  window skips (MCD's quarterly window has no Q4 ’23), which would name a period the chart does not draw. */
function periodRuns(ds: AnalysisDataset, periods: string[]): string {
  const order = ds.periods.map((period) => period.key)
  const indices = [...new Set(periods)].map((period) => order.indexOf(period)).filter((i) => i >= 0).sort((a, b) => a - b)
  const runs: [number, number][] = []
  for (const i of indices) {
    const last = runs.at(-1)
    if (last && i === last[1] + 1 && order[i] === nextPeriod(order[last[1]])) last[1] = i
    else runs.push([i, i])
  }
  return runs.map(([a, b]) => formatAnalysisWindow(order[a], order[b], 'short')).join(', ')
}

const joinNames = (names: string[]) => (names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`)

/** Footnotes name only this chart's series and periods for each letter; series sharing the same period
 *  runs are named together, and YoY comparisons only where the chart draws YoY. */
function letterFootnotes(ds: AnalysisDataset, letters: DataNote[], concepts: string[], withYoY: boolean): Footnote[] {
  const keys = new Set(ds.periods.map((period) => period.key))
  return letters.map((note) => {
    const refs = [
      ...note.values,
      ...(withYoY ? note.comparisons.filter((ref) => ref.basis === 'yoy').map((ref) => ({ ...ref, label: `${ref.label} YoY` })) : []),
    ].filter((ref) => concepts.includes(ref.concept) && keys.has(ref.period))
    const byLabel = new Map<string, string[]>()
    for (const ref of refs) byLabel.set(ref.label, [...(byLabel.get(ref.label) ?? []), ref.period])
    const byRun = new Map<string, string[]>()
    for (const [label, periods] of byLabel) {
      const run = periodRuns(ds, periods)
      byRun.set(run, [...(byRun.get(run) ?? []), label])
    }
    const where = [...byRun].map(([run, labels]) => `${joinNames(labels)} ${run}`).join('; ')
    return { mark: note.letter, text: where ? `${where}: ${note.message}` : note.message }
  })
}

/** †: a fully calculated series carries no symbol (every value is calculated, so there is nothing to
 *  mark) and gets a sentence instead; † marks only the band cells of a partly calculated series. */
function calculatedFootnotes(partly: AnalysisSeries[], fully: string[]): Footnote[] {
  return [
    ...(partly.length ? [{ mark: '†', text: `Calculated by EarningsNerd from reported figures in the marked periods (${joinNames(partly.map((s) => s.label))}).` }] : []),
    ...(fully.length ? [{ mark: '', text: `${joinNames(fully)} ${fully.length > 1 ? 'are' : 'is'} calculated by EarningsNerd from reported figures.` }] : []),
  ]
}

/** Every value the series has in the window is calculated (the sentence above the metrics table names these). */
export const fullyCalculated = (series: AnalysisSeries, ds: AnalysisDataset) => {
  const keys = new Set(ds.periods.map((period) => period.key))
  const valued = series.points.filter((point) => keys.has(point.period) && point.value != null)
  return valued.length > 0 && valued.every(isCalculated)
}

function latestValue(ds: AnalysisDataset, mark: ModelMark, format: AxisFormat): string | undefined {
  const last = [...mark.points].reverse().find((point) => point.value != null)
  if (!last) return undefined
  const text = format.value(last.value!, format.kind === 'money' ? format.d0 : 1)
  return last.period === ds.periods.at(-1)?.key ? text : `${text} (${formatAnalysisPeriod(last.period, 'short')})`
}

function stripOf(marks: ModelMark[], formatOf: (mark: ModelMark) => AxisFormat): StripRow[] {
  return marks.map((mark) => {
    const format = formatOf(mark)
    const digits = (value: number) => (format.kind === 'money' ? format.d0 : Math.abs(value) >= 1000 ? 0 : 1)
    return {
      label: mark.label, short: [...mark.label].slice(0, 6).join(''), color: mark.color, swatch: mark.kind === 'line' ? 'line' as const : 'bar' as const, marker: mark.marker,
      cells: Object.fromEntries(mark.points.map((point) => [point.period, point.value == null ? '—' : format.value(point.value, digits(point.value))])),
    }
  })
}

/** A chart's canonical series: concept and legend label. */
type SeriesSpec = readonly [concept: string, label: string]

/** Line marks for the canonical series present, coloured and shaped in order over those (A8). */
function lineMarks(ds: AnalysisDataset, specs: readonly SeriesSpec[], by: Record<string, AnalysisSeries>): ModelMark[] {
  return specs.filter(([concept]) => present(by[concept], ds)).map(([concept, label], i) => ({
    kind: 'line' as const, seriesKey: concept, label, color: i, marker: MARKERS[i], points: valuesOf(ds, by[concept]), labelled: false,
  }))
}

/** An absent long-term debt keeps its legend item, first as in canonical order, and a footnote, so missing debt never
 *  reads as no debt (spec §3.4, §3.6). An absent gross margin or free cash flow is not listed. */
const ABSENT_DEBT: LegendItem = { label: 'Long-term debt · not in dataset', color: null, swatch: 'line', absent: true }
const ABSENT_DEBT_NOTE: Footnote = { mark: '', text: 'Long-term debt isn’t in this dataset for this window (not shown as zero).' }

function unavailableModel(ds: AnalysisDataset, id: ChartId, title: string, unit: string | null, sentence: string): ChartModel {
  return { id, title, subtitle: subtitleOf(ds, unit), mode: ds.mode, periods: periodsOf(ds), panels: [], legend: [], notesBand: null, footnotes: [], unavailable: sentence, strip: [] }
}

export const MIXED_CURRENCY = 'These figures are filed in more than one currency, so one scale can’t show them. The table lists each in its own currency.'

/** The top-line series the first chart plots, or undefined when the dataset has none (A12). */
export function chartTopLine(ds: AnalysisDataset): AnalysisSeries | undefined {
  const by = byConcept(ds)
  return TOP_LINE_CONCEPTS.map((concept) => by[concept]).find((series) => present(series, ds))
}

export function buildToplineModel(ds: AnalysisDataset, notes: DataNotesModel = resolveDataNotes(ds)): ChartModel {
  const top = chartTopLine(ds)
  if (!top) {
    return unavailableModel(ds, 'topline', 'Top line & growth', null,
      'No top-line figure in this company’s filed data (revenue, net interest income or premiums earned).')
  }
  const title = `${top.label} & growth`
  const { currency, mixed } = currencyOf(ds, [top])
  if (mixed) return unavailableModel(ds, 'topline', title, null, MIXED_CURRENCY)
  const bars: ModelMark = { kind: 'bar', seriesKey: top.concept, label: top.label, color: 0, points: valuesOf(ds, top), labelled: true }
  const growth = growthOf(ds, top)
  const growthMark: ModelMark = { kind: 'growth', seriesKey: `${top.concept}:yoy`, label: 'YoY growth', color: 1, points: growth.points, labelled: true }
  const growthPanel = percentPanel('growth', 'YoY growth', 0.4, AXIS_CAPS.growth, [growthMark], true)
  const { band, letters, partly } = notesBandOf(ds, notes, [top], top)
  const statePeriods = (...states: GrowthState[]) => ds.periods.filter((_, i) => states.includes(growth.states[i])).map((period) => period.key)
  // One line for every growth slot printed "—", structural or unavailable, and one for every "n/m" (spec §3.3).
  const dashed = statePeriods('structural', 'unavailable')
  const notMeaningful = statePeriods('nm-zero', 'nm-sign')
  const growthNotes: Footnote[] = [
    ...(dashed.length ? [{ mark: '—', text: `YoY growth needs the same period a year earlier; none for ${periodRuns(ds, dashed)}.` }] : []),
    ...(notMeaningful.length ? [{ mark: 'n/m', text: `Not meaningful: the prior-year figure was zero or of the opposite sign (${periodRuns(ds, notMeaningful)}).` }] : []),
    ...(growthMark.points.some((point) => point.offscale) ? [{ mark: '', text: 'Growth bars beyond the axis are broken; their printed value is the true value.' }] : []),
  ]
  return {
    id: 'topline', title, subtitle: subtitleOf(ds, currency), mode: ds.mode, periods: periodsOf(ds),
    panels: [moneyPanel('value', top.label, 0.6, AXIS_CAPS.topline, [bars], currency), growthPanel],
    legend: [], notesBand: band, unavailable: null, strip: [],
    footnotes: [
      ...letterFootnotes(ds, letters, [top.concept], true),
      ...calculatedFootnotes(partly, [...(fullyCalculated(top, ds) ? [top.label] : []), 'YoY growth']),
      ...growthNotes,
    ],
  }
}

const MARGIN_SERIES = [['gross_margin', 'Gross'], ['operating_margin', 'Operating'], ['net_margin', 'Net']] as const

export function buildMarginsModel(ds: AnalysisDataset, notes: DataNotesModel = resolveDataNotes(ds)): ChartModel {
  const by = byConcept(ds)
  const marks = lineMarks(ds, MARGIN_SERIES, by)
  if (!marks.length) {
    const company = formatCompanyName(ds.company_name)
    // The top line's own order (D16): a company with revenue has margins missing, not revenue.
    const sentence = present(by.revenue, ds)
      ? 'Margin figures aren’t in this company’s filed data.'
      : present(by.net_interest_income, ds)
        ? `Margins need revenue. ${company} reports net interest income instead; see Net interest income & growth.`
        : present(by.premiums_earned, ds)
          ? `Margins need revenue. ${company} reports premiums earned instead; see Premiums earned & growth.`
          : 'Margins need revenue, which is not in this company’s filed data.'
    return unavailableModel(ds, 'margins', 'Margins', '% of revenue', sentence)
  }
  const panel = percentPanel('margins', null, 1, AXIS_CAPS.margins, marks, false)
  const series = marks.map((mark) => by[mark.seriesKey])
  const { band, letters, partly } = notesBandOf(ds, notes, series)
  const format = panel.axis.format
  const fully = marks.filter((mark) => fullyCalculated(by[mark.seriesKey], ds)).map((mark) => mark.label)
  return {
    id: 'margins', title: 'Margins', subtitle: subtitleOf(ds, '% of revenue'), mode: ds.mode, periods: periodsOf(ds), panels: [panel],
    legend: [
      ...marks.map((mark) => ({ label: mark.label, color: mark.color, swatch: 'line' as const, marker: mark.marker, value: latestValue(ds, mark, format), absent: false })),
    ],
    notesBand: band, unavailable: null, strip: stripOf(marks, () => format),
    footnotes: [
      ...letterFootnotes(ds, letters, marks.map((mark) => mark.seriesKey), false),
      // "Gross, Operating and Net margin", not "Gross margin, Operating margin and Net margin".
      ...calculatedFootnotes(partly, fully.length ? [...fully.slice(0, -1), `${fully.at(-1)} margin`] : []),
      ...(marks.some((mark) => mark.points.some((point) => point.offscale)) ? [{ mark: '↓↑', text: 'Values beyond the axis range are printed in the band at the plot edge.' }] : []),
    ],
  }
}

const CASH_SERIES = [['operating_cash_flow', 'Operating CF'], ['free_cash_flow', 'Free cash flow'], ['net_income', 'Net income']] as const

export function buildCashModel(ds: AnalysisDataset, notes: DataNotesModel = resolveDataNotes(ds)): ChartModel {
  const by = byConcept(ds)
  const marks = lineMarks(ds, CASH_SERIES, by)
  if (!marks.length) return unavailableModel(ds, 'cash', 'Cash generation', null, 'Cash-flow figures aren’t in this company’s filed data.')
  const series = marks.map((mark) => by[mark.seriesKey])
  const { currency, mixed } = currencyOf(ds, series)
  if (mixed) return unavailableModel(ds, 'cash', 'Cash generation', null, MIXED_CURRENCY)
  const panel = moneyPanel('cash', null, 1, AXIS_CAPS.cash, marks, currency)
  const { band, letters, partly } = notesBandOf(ds, notes, series)
  const format = panel.axis.format
  return {
    id: 'cash', title: 'Cash generation', subtitle: subtitleOf(ds, currency), mode: ds.mode, periods: periodsOf(ds), panels: [panel],
    legend: [
      ...marks.map((mark) => ({ label: mark.label, color: mark.color, swatch: 'line' as const, marker: mark.marker, value: latestValue(ds, mark, format), absent: false })),
    ],
    notesBand: band, unavailable: null, strip: stripOf(marks, () => format),
    footnotes: [
      ...letterFootnotes(ds, letters, marks.map((mark) => mark.seriesKey), false),
      ...calculatedFootnotes(partly, marks.filter((mark) => fullyCalculated(by[mark.seriesKey], ds)).map((mark) => mark.label)),
    ],
  }
}

const DEBT_CASH_SERIES = [['long_term_debt', 'Long-term debt'], ['cash_and_equivalents', 'Cash']] as const

export function buildBalanceModel(ds: AnalysisDataset, notes: DataNotesModel = resolveDataNotes(ds)): ChartModel {
  const by = byConcept(ds)
  const lines = lineMarks(ds, DEBT_CASH_SERIES, by)
  const equitySeries = present(by.shareholders_equity, ds) ? by.shareholders_equity : undefined
  if (!lines.length && !equitySeries) return unavailableModel(ds, 'balance', 'Balance sheet', null, 'Balance-sheet figures aren’t in this company’s filed data.')
  const series = [...lines.map((mark) => by[mark.seriesKey]), ...(equitySeries ? [equitySeries] : [])]
  const { currency, mixed } = currencyOf(ds, series)
  if (mixed) return unavailableModel(ds, 'balance', 'Balance sheet', null, MIXED_CURRENCY)
  // In order over the series present (chart-1.. never skipped): debt, cash, then equity.
  const equity: ModelMark = { kind: 'signedBar', seriesKey: 'shareholders_equity', label: 'Equity', color: lines.length, points: valuesOf(ds, equitySeries), labelled: false }
  const panelA = moneyPanel('debtcash', lines.length ? `${joinNames(lines.map((mark) => mark.label))}` : null, 0.6, AXIS_CAPS.debtcash, lines, currency)
  const panelB = moneyPanel('equity', 'Shareholders’ equity', 0.4, AXIS_CAPS.equity, equitySeries ? [equity] : [], currency)
  const panels = [...(lines.length ? [panelA] : []), ...(equitySeries ? [panelB] : [])]
  const { band, letters, partly } = notesBandOf(ds, notes, series)
  const drawn = [...lines, ...(equitySeries ? [equity] : [])]
  const debtAbsent = !present(by.long_term_debt, ds)
  return {
    id: 'balance', title: 'Balance sheet', subtitle: subtitleOf(ds, currency), mode: ds.mode, periods: periodsOf(ds), panels,
    legend: [
      ...(debtAbsent ? [ABSENT_DEBT] : []),
      ...lines.map((mark) => ({ label: mark.label, color: mark.color, swatch: 'line' as const, marker: mark.marker, value: latestValue(ds, mark, panelA.axis.format), absent: false })),
      ...(equitySeries ? [{ label: 'Equity', color: equity.color, swatch: 'bar' as const, value: latestValue(ds, equity, panelB.axis.format), absent: false }] : []),
    ],
    notesBand: band, unavailable: null,
    strip: stripOf(drawn, (mark) => (mark.kind === 'signedBar' ? panelB.axis.format : panelA.axis.format)),
    footnotes: [
      ...letterFootnotes(ds, letters, series.map((s) => s.concept), false),
      ...calculatedFootnotes(partly, drawn.filter((mark) => fullyCalculated(by[mark.seriesKey], ds)).map((mark) => mark.label)),
      ...(debtAbsent ? [ABSENT_DEBT_NOTE] : []),
    ],
  }
}

export const CHART_IDS: readonly ChartId[] = ['topline', 'margins', 'cash', 'balance']

export function buildChartModel(chart: ChartId, ds: AnalysisDataset, notes: DataNotesModel = resolveDataNotes(ds)): ChartModel {
  switch (chart) {
    case 'topline': return buildToplineModel(ds, notes)
    case 'margins': return buildMarginsModel(ds, notes)
    case 'cash': return buildCashModel(ds, notes)
    case 'balance': return buildBalanceModel(ds, notes)
  }
}

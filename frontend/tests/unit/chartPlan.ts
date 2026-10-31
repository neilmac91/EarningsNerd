/**
 * What a trend chart's plan prints, by the role the renderer's data-text attribute names (TrendChartSvg's TextRole), as
 * `string|ink`: the ink is the one docs/design/analysis-trend-charts-spec-2026-10.md §3.8 gives the role, whose floor
 * chart-apca.spec.ts holds. Shared by the renderer's unit spec and the gallery (tests/e2e/charts-v2-gallery.spec.ts),
 * so the page and the plan are held to one list. Also the engine specs' shared cases: the analysis datasets' synthetic
 * notes, the bar chart cases (barCases) that chart-engine.spec.ts and chart-readout.spec.ts both sweep, and the ranked
 * company charts (peerBarCases, E251: the Sector peers panel's, built by its own peerChart.ts) those two and
 * trend-charts-v2.spec.tsx sweep.
 */
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { TextRole } from '@/features/analysis/components/TrendChartSvg'
import type { BarChartDef } from '@/features/analysis/lib/charts/barChart'
import { noteGlyphs, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import type { ChartModel } from '@/features/analysis/lib/charts/model'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'
import type { FundamentalSeries, FundamentalsResponse } from '@/features/fundamentals/api/fundamentals-api'
import { slotsOf } from '@/features/fundamentals/lib/trendChart'
import type { PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { shows } from '@/features/peers/lib/cohort'
import { peerChartDef } from '@/features/peers/lib/peerChart'

/** tests/unit/fixtures/fundamentals-datasets.json: filing-scoped fundamentals as their endpoint serves them, and the bar
 *  charts the cases draw from them, each a series and its axis. */
export interface BarFixture {
  filings: Record<string, { case: string; response: FundamentalsResponse }>
  charts: Record<string, { case: string; filing: string; concept: string; label: string; axis: 'money' | 'percent' | 'ratio' }>
}

/** A chart case's series, as its filing's response holds it. */
export const barSeries = (fixture: BarFixture, name: string): FundamentalSeries => {
  const chart = fixture.charts[name]
  return fixture.filings[chart.filing].response.concepts.find((series) => series.concept === chart.concept)!
}

/** Every chart case as the definition buildBarChart takes: a slot per point the series holds, withheld years included,
 *  as Financial trends keys them (slotsOf: key "FY2025", tick "2025"), and its axis, a money axis in the series' own
 *  unit. */
export function barCases(fixture: BarFixture): [string, BarChartDef][] {
  return Object.entries(fixture.charts).map(([name, chart]) => {
    const series = barSeries(fixture, name)
    return [name, {
      id: name,
      title: chart.label,
      categories: slotsOf(series.points),
      series: { key: chart.concept, label: chart.label, values: series.points.map((point) => point.value) },
      axis: chart.axis === 'money' ? { kind: 'money', unit: series.unit } : { kind: chart.axis },
    }]
  })
}

/** tests/unit/fixtures/peers-cohorts.json: the peers endpoint's answers, each case labelled with the metric its request
 *  named (backend/tests/unit/test_peers_fixture_contract.py holds the service to each). An answer carries `sic` too,
 *  which the client leaves unread. */
export interface PeerFixture {
  source: string
  cases: Record<string, { case: string; metric: string; response: PeerComparisonResponse & { sic: string | null } }>
}

/** The peers cases the Sector peers panel shows, by name, in the fixture's order: pinned here rather than read from
 *  `shows`, the code under test, so a change to it that drops a cohort the sweeps read, or one that starts drawing a case
 *  it should not, fails every sweep instead of shrinking or growing it unseen. The cases it does not show (a company
 *  ranked alone, a subject with no figure or a withheld one, a withheld peer in a pair, a concept FEATURED does not
 *  name) draw no chart; its own spec holds that (sector-peers.spec.tsx). */
export const PEER_SHOWING = [
  'pair', 'spread', 'near-equal', 'six-glyph', 'net margin', 'diluted EPS', 'CNY revenue', 'duplicate ticker',
  'pair plus withheld', 'cap', 'cap, subject fifth', 'cap, subject eleventh', 'cap, subject twelfth',
  'cap, tie at the tenth', 'cap, tie at the eleventh', 'cap, all tied', 'bank',
]

/** Every case of PEER_SHOWING as the bar chart the panel draws: the panel's own builder (features/peers/lib/peerChart.ts),
 *  so the sweeps read the charts the page draws. Throws where `shows` picks out any other list from the fixture. */
export function peerBarCases(fixture: PeerFixture): [string, BarChartDef][] {
  const showing = Object.entries(fixture.cases).filter(([, { response }]) => shows(response)).map(([name]) => name)
  if (showing.join('\n') !== PEER_SHOWING.join('\n')) {
    throw new Error(`peerBarCases: the panel shows ${JSON.stringify(showing)}, not the pinned ${JSON.stringify(PEER_SHOWING)}`)
  }
  return PEER_SHOWING.map((name) => [name, peerChartDef(fixture.cases[name].response)])
}

/** A dataset whose record-only review notes (legacy_calculation, such as REGNPN's nine simulated flags) question the
 *  number instead, so the band letters them (D-061): as stored they letter nothing. */
export function questioned(dataset: AnalysisDataset): AnalysisDataset {
  delete (dataset as { data_notes?: unknown }).data_notes
  for (const series of dataset.series) for (const point of series.points) {
    if (point.provenance?.reasons.includes('legacy_calculation')) point.provenance = { ...point.provenance, reasons: ['source_conflict'] }
  }
  return dataset
}

/** The synthetic dataset `withMixedNotes` adds to the fixture. */
export const MIXED_NOTES = 'REGNPN_annual, mixed notes'

/** The fixture with one more dataset, MIXED_NOTES, so the sweeps over every dataset meet each kind of note a band can:
 *  no stored fixture has a note that questions the number, nor one with no check recorded. It is REGNPN_annual with
 *  operating margin's flags questioning the number (letters), net margin's left record-only, free cash flow's checks
 *  unrecorded (unknown notes), its gaps as they are, and two questioned revenue comparisons: FY2024's on a number and
 *  FY2025's on an n/m, for a reason of its own, so its letter appears nowhere else (D-061). */
export function withMixedNotes<F extends { datasets: Record<string, { dataset: AnalysisDataset }> }>(fixture: F): F {
  const base = fixture.datasets.REGNPN_annual
  const ds = structuredClone(base.dataset)
  delete (ds as { data_notes?: unknown }).data_notes
  const series = (concept: string) => ds.series.find((candidate) => candidate.concept === concept)!
  const reflag = (concept: string, change: { validation?: 'unavailable'; reasons: string[] }) => {
    for (const point of series(concept).points) {
      if (point.provenance?.reasons.includes('legacy_calculation')) point.provenance = { ...point.provenance, ...change }
    }
  }
  reflag('operating_margin', { reasons: ['source_conflict'] })
  reflag('free_cash_flow', { validation: 'unavailable', reasons: [] })
  const questionedYoY = (reason: string) => ({ version: 1 as const, method: 'calculated' as const, validation: 'needs_review' as const, reasons: [reason], formula: null, inputs: [] })
  const revenue = (period: string) => series('revenue').points.find((point) => point.period === period)!
  Object.assign(revenue('FY2024'), { yoy_provenance: questionedYoY('source_conflict') })
  Object.assign(revenue('FY2025'), { yoy: 'nm', yoy_provenance: questionedYoY('period_mismatch') })
  return { ...fixture, datasets: { ...fixture.datasets, [MIXED_NOTES]: { ...base, dataset: ds } } }
}

export function plannedByRole(model: ChartModel, layout: ChartLayout, tokens: ChartTokens): Partial<Record<TextRole, string[]>> {
  const planned: Partial<Record<TextRole, string[]>> = {}
  const add = (role: TextRole, text: string, ink: string) => (planned[role] ??= []).push(`${text}|${ink}`)
  for (const box of layout.panels) {
    const { panel } = box
    if (box.captionY != null && panel.caption) add('caption', panel.caption, tokens.tick)
    for (const tick of panel.axis.ticks) add('tick', panel.axis.format.tick(tick), tokens.tick)
    for (const bar of box.bars) if (bar.label) add('label', bar.label.text, tokens.value)
    for (const gap of box.gaps) add('gap', gap.text, tokens.tick)
    for (const label of box.nearZero) add('near-zero', label.text, tokens.value)
    for (const [band, arrow] of [[box.offAbove, '↑'], [box.offBelow, '↓']] as const) for (const item of band?.items ?? []) {
      add('off-arrow', arrow, tokens.series[item.color])
      add('off-value', item.text, tokens.value)
    }
  }
  for (const period of model.periods) add('x', period.tick.join(''), tokens.tick)
  if (layout.stripTop != null) for (const row of model.strip) {
    add('strip-name', row.short, tokens.tick)
    for (const period of model.periods) add('strip', row.cells[period.key], tokens.value)
  }
  if (model.notesBand) add('notes', 'Notes', tokens.tick)
  for (const glyph of noteGlyphs(model, layout)) add('note', glyph.text, tokens.note)
  for (const list of Object.values(planned)) list.sort()
  return planned
}

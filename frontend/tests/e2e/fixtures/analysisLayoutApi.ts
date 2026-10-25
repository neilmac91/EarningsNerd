import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { expect, type Page } from '@playwright/test'
import type { AnalysisCompletion, AnalysisCoverage, AnalysisDataset } from '../../../features/analysis/api/analysis-api'
import type { DataNotesDataset, DataNoteQuality } from '../../../features/analysis/lib/dataNotes'
import type { FactProvenance } from '../../../features/analysis/lib/provenance'

/**
 * Approved redesign VISUAL fixtures (reference commit and source hashes in the JSON).
 * Their quality states are simulated and some provenance fields are pruned. They test
 * the real React page, never backend correctness or repaired-production data. Values,
 * source URLs, retained operands, comparisons and citations are preserved losslessly.
 * Variants are exact field replacements, not recalculation using the code under test.
 * CI boots next start only: all API paths are answered here, with no backend or AI.
 */
export type AnalysisState = 'clean' | 'legacy' | 'discrepancy'
export type AnalysisGeometryState = 'captured' | 'edge' | 'annual'
export type AnalysisTheme = 'light' | 'dark'
type Fixture = { dataset: AnalysisDataset; completion: AnalysisCompletion & { type: 'complete' } }
type Replacement = { path: Array<string | number>; value?: unknown; remove?: boolean }
const archive = JSON.parse(readFileSync(path.join(__dirname, 'analysis-layout.json'), 'utf8')) as {
  coverage: AnalysisCoverage
  legacy: Fixture
  variants: Record<'clean' | 'discrepancy', Replacement[]>
}

function fixtureFor(state: AnalysisState): Fixture {
  const fixture = structuredClone(archive.legacy)
  for (const replacement of state === 'legacy' ? [] : archive.variants[state]) {
    let parent = fixture as unknown as Record<string | number, unknown>
    for (const key of replacement.path.slice(0, -1)) parent = parent[key] as Record<string | number, unknown>
    const key = replacement.path.at(-1)!
    if (replacement.remove) delete parent[key]
    else parent[key] = structuredClone(replacement.value)
  }
  return fixture
}

// The captured projection remains separate from the historical prototype fixtures above.
// Display metadata (unit, tone and period fields) comes from the archived map.
// The quality-only projection omits lineage: complete the API envelope with
// synthetic structural defaults, never archived or invented source operands.
const captureBytes = readFileSync(path.join(__dirname, '../../unit/fixtures/meta-data-notes.json'))
const capture = JSON.parse(captureBytes.toString()) as {
  source: { snapshot_id: string; dataset_version: string }
  dataset: DataNotesDataset
}
const projectedProvenance = (value: DataNoteQuality['provenance']): FactProvenance | null | undefined => value
  ? { version: 1, formula: null, inputs: [], ...structuredClone(value) }
  : value

function geometryFixture(state: AnalysisGeometryState): Fixture {
  expect(createHash('sha256').update(captureBytes).digest('hex')).toBe('67c83050dfd78bab0dd379f3e98806e429dbde024f412574091d595b85e33cad')
  const fixture = fixtureFor('legacy')
  fixture.dataset = {
    ...fixture.dataset, ...structuredClone(capture.dataset),
    series: capture.dataset.series.map(series => ({
      ...structuredClone(archive.legacy.dataset.series.find(item => item.concept === series.concept)!),
      ...structuredClone(series),
      cagr_provenance: projectedProvenance(series.cagr_provenance),
      window_pp_provenance: projectedProvenance(series.window_pp_provenance),
      points: series.points.map(point => ({
        ...structuredClone(point),
        provenance: projectedProvenance(point.provenance),
        qoq_provenance: projectedProvenance(point.qoq_provenance),
        yoy_provenance: projectedProvenance(point.yoy_provenance),
      })),
    })),
    periods: structuredClone(archive.legacy.dataset.periods),
    inflections: [],
    snapshot_id: state === 'captured' ? capture.source.snapshot_id : `geometry-${state}`,
    dataset_version: state === 'captured' ? capture.source.dataset_version : `geometry-${state}`,
    data_as_of: null,
  }
  // These cases test presentation only; no prose from another state claims these values.
  fixture.completion = { ...fixture.completion, narrative: '## The trajectory\nSynthetic geometry fixture.', citations: [], grounded: 0 }
  const dataset = fixture.dataset
  const review = (reasons: string[]) => ({ version: 1, method: 'calculated' as const, validation: 'needs_review' as const, reasons, formula: null, inputs: [] })
  if (state === 'edge') {
    // More than 26 reason groups force actual multi-letter affixes through table formatting.
    dataset.series.slice(0, 3).forEach((series, row) => series.points.forEach((point, column) => {
      point.provenance = review([`layout_reason_${row * 12 + column}`])
    }))
    const revenue = dataset.series.find(series => series.concept === 'revenue')!
    Object.assign(revenue.points.at(-1)!, { value: 0, qoq: 0, yoy: 0 })
    const cash = dataset.series.find(series => series.concept === 'free_cash_flow')!
    Object.assign(cash.points.at(-1)!, { value: null, qoq: null, yoy: null })
    const margin = dataset.series.find(series => series.concept === 'operating_margin')!
    Object.assign(margin.points[0], { value: -12345.678, qoq: 12345.678 })
    const eps = dataset.series.find(series => series.concept === 'eps_diluted')!
    eps.unit = 'CAD/shares'
    Object.assign(eps.points[0], { value: -15154, qoq: null, yoy: 1234.567, yoy_provenance: review(['source_check_needed']) })
    Object.assign(eps.points[2], { value: 0, qoq: 'nm' })
    Object.assign(eps.points[3], { provenance: review(['unit_mismatch', 'source_check_needed']) })
    Object.assign(eps.points[4], { provenance: review(['source_check_needed', 'unit_mismatch']) })
    delete eps.points[5].provenance
    delete eps.points[5].reconciled
    delete eps.points[6].provenance
    eps.points[6].reconciled = false
    // The shipped phone bug: at 390px a figure that fills its column's nine-glyph budget with its marks ("$922.0M†a")
    // wrapped them onto a line of their own below it. This state's notes run past z, so the full budget here is six
    // glyphs, a dagger and a two-letter note: "$92.2M" and "-$922M", each with both. Both signs are planted.
    const tight = (concept: string, index: number, value: number) =>
      Object.assign(dataset.series.find(series => series.concept === concept)!.points[index], { value, provenance: review(['source_check_needed']) })
    tight('working_capital', 1, 92_200_000)
    tight('financing_cash_flow', 9, -922_000_000)
  }
  if (state === 'annual') {
    dataset.mode = 'annual'
    dataset.periods = Array.from({ length: 10 }, (_, index) => ({ key: `FY${2016 + index}`, fiscal_year: 2016 + index, fiscal_period: 'FY', period_end: `${2016 + index}-12-31` }))
    dataset.period_key = 'FY2016..FY2025'
    for (const series of dataset.series) {
      series.points = series.points.slice(0, 10).map((point, index) => ({ ...point, period: dataset.periods[index].key, qoq: null, qoq_provenance: null }))
      if (series.percent) Object.assign(series, { cagr: null, window_pp: -12.345, window_pp_range: dataset.period_key, window_pp_provenance: review(['source_check_needed']) })
      else Object.assign(series, { cagr: 0.1234, cagr_window: dataset.period_key, cagr_provenance: review(['source_check_needed']) })
    }
  }
  fixture.completion.n_periods = dataset.periods.length
  fixture.completion.snapshot_id = dataset.snapshot_id!
  return fixture
}

export const EXPECTED_NOTES = {
  clean: { passed: 230, reviewValues: 0, reviewComparisons: 0, unavailable: 10, calculated: 101 },
  legacy: { passed: 220, reviewValues: 10, reviewComparisons: 24, unavailable: 10, calculated: 101 },
  discrepancy: { passed: 227, reviewValues: 3, reviewComparisons: 6, unavailable: 10, calculated: 101 },
} as const
export const PERIODS = ['2023Q3', '2023Q4', '2024Q1', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4', '2026Q1', '2026Q2']
export const METRICS = 20
// Independently counted fixture slots, not derived using the presentation code under test.
// All three visual states retain these unavailable values; the table must not turn
// them into zero, omit their cells, or move their notes to a neighbouring period.
export const UNAVAILABLE_CELLS = [
  { row: 5, periods: ['2023Q4', '2024Q4', '2025Q4'] }, // Basic EPS
  { row: 6, periods: ['2023Q4', '2024Q4', '2025Q4'] }, // Diluted EPS
  { row: 8, periods: ['2023Q3', '2023Q4'] }, // Capital expenditure
  { row: 9, periods: ['2023Q3', '2023Q4'] }, // Free cash flow
] as const
export const EXPECTED_TABLE_REVIEWS = { clean: 0, legacy: 10, discrepancy: 3 } as const

type TableNoteSlots = { rows: number[]; periods: string[]; letter: string; kind: 'review' }
// Literal cell associations from the archived visual fixture, independently of noteFor
// and noteForComparison. Unlisted cells have no mark; gaps use UNAVAILABLE_CELLS above.
export const EXPECTED_TABLE_CELL_NOTES: Record<AnalysisState, {
  value: TableNoteSlots[]; comparison: TableNoteSlots[]; unavailableLetter: string
}> = {
  clean: { value: [], comparison: [], unavailableLetter: 'a' },
  legacy: {
    value: [
      { rows: [2, 4], periods: ['2025Q2', '2026Q2'], letter: 'a', kind: 'review' },
      { rows: [16, 17], periods: ['2023Q4', '2024Q1', '2026Q2'], letter: 'a', kind: 'review' },
    ],
    comparison: [
      { rows: [2, 4], periods: ['2025Q2', '2025Q3', '2026Q2'], letter: 'a', kind: 'review' },
      { rows: [16, 17], periods: ['2023Q4', '2024Q1', '2024Q2', '2026Q2'], letter: 'a', kind: 'review' },
    ],
    unavailableLetter: 'b',
  },
  discrepancy: {
    value: [{ rows: [0, 2, 4], periods: ['2026Q2'], letter: 'a', kind: 'review' }],
    comparison: [{ rows: [0, 2, 4], periods: ['2026Q2'], letter: 'a', kind: 'review' }],
    unavailableLetter: 'b',
  },
}

// Independently counted from the archived fixture, not the production grouping code.
// KPI order is Revenue, Net income, Free cash flow, Net margin. Only the last two
// values are calculated; a reviewed latest value and its YoY each need their own mark.
export const EXPECTED_KPI_VALUES = [
  { label: 'Revenue', daggers: 0 },
  { label: 'Net income', daggers: 0 },
  { label: 'Free cash flow', daggers: 1 },
  { label: 'Net margin', daggers: 1 },
] as const
// Each nonclean fixture has one review-reason group, ordered before unavailable
// figures, so its affected value and YoY both carry a. Keep their expectations separate.
export const EXPECTED_KPI_LETTERS = {
  clean: [
    { value: [], growth: [] }, { value: [], growth: [] },
    { value: [], growth: [] }, { value: [], growth: [] },
  ],
  legacy: [
    { value: [], growth: [] }, { value: [], growth: [] },
    { value: [], growth: [] }, { value: ['a'], growth: ['a'] },
  ],
  discrepancy: [
    { value: ['a'], growth: ['a'] }, { value: [], growth: [] },
    { value: [], growth: [] }, { value: ['a'], growth: ['a'] },
  ],
} as const
export const EXPECTED_TABLE_VALUE_DAGGERS = 101
// Only the displayed comparison counts here (QoQ, or YoY when QoQ is absent),
// unlike the Data notes summary which counts both comparison populations.
export const EXPECTED_TABLE_COMPARISON_REVIEWS = { clean: 0, legacy: 14, discrepancy: 3 } as const

/**
 * The analysis page's API for a signed-in Pro reader, answered in the browser: META's company, coverage, dataset
 * and narrative stream from `fixture` (the legacy state by default). Only the target frontend's own GET and HEAD
 * reads reach the network; anything else is aborted, and an API path the page should not call is answered 404 and
 * recorded in the returned traffic. Shared by openAnalysis and text-floors.spec.ts's /analysis entry.
 */
export async function answerAnalysisApi(page: Page, baseURL: string, fixture: Fixture = fixtureFor('legacy')) {
  const origin = new URL(baseURL).origin
  const traffic = { dataset: 0, stream: 0, unexpectedApi: [] as string[], submittedRanges: [] as unknown[] }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route('**/*', route => {
    const request = route.request()
    const url = new URL(request.url())
    const endpoint = url.pathname
    const headers = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS' }
    const json = (body: unknown, status = 200) => route.fulfill({ status, headers, json: body })
    // Sentry's ingestion URLs also begin /api, but are telemetry, not this app's API.
    if (url.hostname.endsWith('.sentry.io')) return route.abort()
    if (endpoint.startsWith('/api/') || endpoint.startsWith('/internal/')) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
      switch (endpoint) {
        case '/api/auth/me': return json({ id: 1, email: 'layout@example.com', full_name: 'Layout fixture', is_pro: true, is_beta: false, is_admin: false, email_verified: true })
        case '/api/subscriptions/subscription': return json({ is_pro: true, stripe_customer_id: 'cus_fixture', stripe_subscription_id: 'sub_fixture', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false })
        case '/api/subscriptions/usage': return json({ summaries_used: 0, summaries_limit: 100, is_pro: true, month: '2026-10', qa_used: 0, qa_limit: 300, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50 })
        case '/api/users/me/notifications': return json({ items: [], unread_count: 0 })
        case '/api/companies/META': return json({ id: 1, cik: '1326801', ticker: 'META', name: 'Meta Platforms, Inc.', exchange: 'NASDAQ' })
        case '/api/analysis/META/coverage': return json(archive.coverage)
        case '/api/analysis/META/dataset':
          traffic.dataset++
          traffic.submittedRanges.push(request.postDataJSON())
          return json(fixture.dataset)
        case '/api/analysis/META/stream':
          traffic.stream++
          return route.fulfill({ status: 200, headers, contentType: 'text/event-stream', body: `data: ${JSON.stringify(fixture.completion)}\n\n` })
        default:
          traffic.unexpectedApi.push(`${request.method()} ${endpoint}`)
          return json({ detail: 'No backend is available: unexpected API request in layout fixture' }, 404)
      }
    }
    // Only the target frontend's static reads can reach the network. In particular an
    // API configured at a different host is still mocked above, never sent to production.
    if (url.origin === origin && ['GET', 'HEAD'].includes(request.method())) return route.continue()
    return route.abort()
  })
  return traffic
}

/** Runs the analysis in `mode` on /analysis?ticker=META, then waits for what only a finished run shows: the four KPI
    cards, the metrics table's heading and the refresh control. */
export async function runAnalysis(page: Page, mode: AnalysisDataset['mode']) {
  await page.getByRole('button', { name: mode === 'annual' ? 'Annual' : 'Quarterly', exact: true }).click()
  await page.getByRole('button', { name: 'Run analysis', exact: true }).click()
  await expect(page.locator('[data-analysis-kpi]')).toHaveCount(4)
  await expect(page.getByRole('heading', { name: 'Metrics by period', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh analysis', exact: true })).toBeVisible()
}

export async function openAnalysis(page: Page, baseURL: string, state: AnalysisState | AnalysisGeometryState, theme: AnalysisTheme, textScale = 1, legacyEvidenceNote = false,
  editDataset?: (dataset: AnalysisDataset) => void) {
  const fixture = state === 'captured' || state === 'edge' || state === 'annual' ? geometryFixture(state) : fixtureFor(state)
  editDataset?.(fixture.dataset)
  if (legacyEvidenceNote) {
    expect(state).toBe('legacy')
    // The archived long FCF/net-income group has only passed citations. Give one
    // operand the existing legacy concern for the folded-letter browser case;
    // retain its financial value, calculation and source fields unchanged.
    const operand = fixture.completion.citations.find(citation => citation.n === 23)!
    operand.reconciled = false
    operand.provenance = { ...operand.provenance!, validation: 'needs_review', reasons: ['legacy_calculation'] }
  }
  await page.addInitScript(({ theme, textScale }) => {
    localStorage.setItem('theme', theme)
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z' }))
    // Root text-size emulation, not a claim about native browser zoom. Apply before render.
    if (textScale !== 1) document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.fontSize = `${100 * textScale}%` }, { once: true })
  }, { theme, textScale })
  const traffic = await answerAnalysisApi(page, baseURL, fixture)
  await page.goto('/analysis?ticker=META')
  await runAnalysis(page, fixture.dataset.mode)
  await page.evaluate(() => document.fonts.ready)
  await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
  expect(traffic.dataset).toBe(1)
  expect(traffic.stream).toBe(1)
  expect(traffic.submittedRanges).toEqual([{ mode: fixture.dataset.mode, start_period: fixture.dataset.periods[0].key, end_period: fixture.dataset.periods.at(-1)!.key }])
  expect(traffic.unexpectedApi).toEqual([])
  return traffic
}

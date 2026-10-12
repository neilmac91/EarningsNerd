import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, type Page } from '@playwright/test'
import type { AnalysisCompletion, AnalysisCoverage, AnalysisDataset } from '../../../features/analysis/api/analysis-api'

/**
 * Approved redesign VISUAL fixtures (reference commit and source hashes in the JSON).
 * Their quality states are simulated and some provenance fields are pruned. They test
 * the real React page, never backend correctness or repaired-production data. Values,
 * source URLs, retained operands, comparisons and citations are preserved losslessly.
 * Variants are exact field replacements, not recalculation using the code under test.
 * CI boots next start only: all API paths are answered here, with no backend or AI.
 */
export type AnalysisState = 'clean' | 'legacy' | 'discrepancy'
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

export const EXPECTED_NOTES = {
  clean: { passed: 230, reviewValues: 0, reviewComparisons: 0, unavailable: 10, calculated: 101 },
  legacy: { passed: 220, reviewValues: 10, reviewComparisons: 24, unavailable: 10, calculated: 101 },
  discrepancy: { passed: 227, reviewValues: 3, reviewComparisons: 6, unavailable: 10, calculated: 101 },
} as const
export const PERIODS = ['2023Q3', '2023Q4', '2024Q1', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4', '2026Q1', '2026Q2']
export const METRICS = 20
// Independently counted fixture slots, not derived using the presentation code under test.
// All three visual states retain these unavailable values; a table window must not turn
// them into zero, omit their cells, or move their notes to a neighbouring period.
export const UNAVAILABLE_CELLS = [
  { row: 5, periods: ['2023Q4', '2024Q4', '2025Q4'] }, // Basic EPS
  { row: 6, periods: ['2023Q4', '2024Q4', '2025Q4'] }, // Diluted EPS
  { row: 8, periods: ['2023Q3', '2023Q4'] }, // Capital expenditure
  { row: 9, periods: ['2023Q3', '2023Q4'] }, // Free cash flow
] as const
export const EXPECTED_TABLE_REVIEWS = {
  clean: { all: 0, newest: 0, earliest: 0 },
  legacy: { all: 10, newest: 6, earliest: 4 },
  discrepancy: { all: 3, newest: 3, earliest: 0 },
} as const

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
export const EXPECTED_TABLE_VALUE_DAGGERS = { all: 101, earliest: 52, newest: 49 } as const
// Only the displayed comparison counts here (QoQ, or YoY when QoQ is absent),
// unlike the Data notes summary which counts both comparison populations.
export const EXPECTED_TABLE_COMPARISON_REVIEWS = {
  clean: { all: 0, earliest: 0, newest: 0 },
  legacy: { all: 14, earliest: 6, newest: 8 },
  discrepancy: { all: 3, earliest: 0, newest: 3 },
} as const

export async function openAnalysis(page: Page, baseURL: string, state: AnalysisState, theme: AnalysisTheme, textScale = 1, legacyEvidenceNote = false) {
  const origin = new URL(baseURL).origin
  const fixture = fixtureFor(state)
  if (legacyEvidenceNote) {
    expect(state).toBe('legacy')
    // The archived long FCF/net-income group has only passed citations. Give one
    // operand the existing legacy concern for the folded-letter browser case;
    // retain its financial value, calculation and source fields unchanged.
    const operand = fixture.completion.citations.find(citation => citation.n === 23)!
    operand.reconciled = false
    operand.provenance = { ...operand.provenance!, validation: 'needs_review', reasons: ['legacy_calculation'] }
  }
  const traffic = { dataset: 0, stream: 0, unexpectedApi: [] as string[], submittedRanges: [] as unknown[] }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.addInitScript(({ theme, textScale }) => {
    localStorage.setItem('theme', theme)
    localStorage.setItem('cookie_consent', JSON.stringify({ necessary: true, analytics: false, marketing: false, timestamp: '2026-10-10T00:00:00Z' }))
    // Root text-size emulation, not a claim about native browser zoom. Apply before render.
    if (textScale !== 1) document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.fontSize = `${100 * textScale}%` }, { once: true })
  }, { theme, textScale })
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
  await page.goto('/analysis?ticker=META')
  await page.getByRole('button', { name: 'Quarterly', exact: true }).click()
  await page.getByRole('button', { name: 'Run analysis', exact: true }).click()
  await expect(page.locator('[data-analysis-kpi]')).toHaveCount(4)
  await expect(page.getByRole('heading', { name: 'Metrics by period', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh analysis', exact: true })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
  expect(traffic.dataset).toBe(1)
  expect(traffic.stream).toBe(1)
  expect(traffic.submittedRanges).toEqual([{ mode: 'quarterly', start_period: PERIODS[0], end_period: PERIODS.at(-1) }])
  expect(traffic.unexpectedApi).toEqual([])
  return traffic
}

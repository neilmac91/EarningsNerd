import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { EXAMPLE_FILING_ID } from '@/lib/featureFlags'
import type { Company, TrendingTickerResponse } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { Summary } from '@/features/summaries/api/summaries-api'

/**
 * Server-side data for the public pages (ISR). The homepage helpers return null on any
 * failure — the page renders a static fallback instead, so the homepage never
 * breaks (or slows the build) when the backend is unreachable. The company/filing-page
 * helpers below return a status-aware result instead, because those pages must
 * distinguish "the backend said 404" (render a real 404) from "the backend is
 * unreachable" (fall back to the client-fetching shell).
 */

const getBackendUrl = (): string => {
  const url =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    (process.env.NODE_ENV === 'development'
      ? 'http://localhost:8000'
      : 'https://api.earningsnerd.io')
  // Tolerate a configured trailing slash (avoids `//api/...` request paths).
  return url.replace(/\/$/, '')
}

const fetchJson = async <T>(path: string, revalidateSeconds: number): Promise<T | null> => {
  try {
    const res = await fetch(`${getBackendUrl()}${path}`, {
      headers: { accept: 'application/json' },
      next: { revalidate: revalidateSeconds },
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export interface ExampleMetric {
  label: string
  value: string
  deltaPercent?: number | null
}

export interface ExampleData {
  filingId: number
  ticker: string
  companyName: string
  filingType: string
  filingDate: string
  secUrl: string
  excerpt: string
  qualityTier: string | null
  metrics: ExampleMetric[]
}

interface FilingPayload {
  id: number
  filing_type: string
  filing_date: string
  sec_url: string
  company?: { ticker: string; name: string }
}

interface SummaryPayload {
  business_overview?: string | null
  financial_highlights?: {
    normalized?: {
      metrics?: Array<{
        metric?: string | null
        currentPeriod?: string | null
        deltaPercent?: number | null
      }> | null
    } | null
  } | null
  raw_summary?: { quality?: { tier?: string } } | null
}

/** First ~2 sentences of the summary, markdown stripped, for the hero excerpt. */
// Exported for the hero-shape pin: the homepage hero is coupled to the leading shape of the derived
// business_overview, so a test asserts the excerpt still leads with the headline sentence.
export const toExcerpt = (markdown: string): string => {
  const plain = stripInternalNotices(markdown)
    .replace(/^#{1,6}\s+.*$/gm, '') // headings
    .replace(/^\s*-\s+/gm, '') // list markers (exec key points render as bullets since P0-2)
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/[*_`>|#]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (plain.length <= 240) return plain
  const cut = plain.slice(0, 240)
  const sentenceEnd = cut.lastIndexOf('. ')
  return sentenceEnd > 120 ? cut.slice(0, sentenceEnd + 1) : `${cut.trimEnd()}…`
}

const METRIC_MATCHERS: Array<{ label: string; pattern: RegExp }> = [
  { label: 'Revenue', pattern: /revenue|net sales/i },
  { label: 'Net Income', pattern: /net income/i },
  { label: 'Diluted EPS', pattern: /eps|earnings per share/i },
]

const pickMetrics = (summary: SummaryPayload): ExampleMetric[] => {
  const facts = summary.financial_highlights?.normalized?.metrics ?? []
  const picked: ExampleMetric[] = []
  for (const { label, pattern } of METRIC_MATCHERS) {
    // Defensive: the payload is external — tolerate null entries in the array.
    const fact = facts.find((f) => f?.metric && pattern.test(f.metric) && f.currentPeriod)
    if (fact?.currentPeriod) {
      picked.push({ label, value: fact.currentPeriod, deltaPercent: fact.deltaPercent })
    }
  }
  return picked.length >= 2 ? picked : []
}

/**
 * The real pre-generated example summary, rendered live in the hero so the
 * preview can never drift from what a click delivers. Revalidates hourly.
 */
export const fetchExampleData = async (): Promise<ExampleData | null> => {
  if (!EXAMPLE_FILING_ID) return null
  const id = EXAMPLE_FILING_ID
  const [filing, summary] = await Promise.all([
    fetchJson<FilingPayload>(`/api/filings/${id}`, 3600),
    fetchJson<SummaryPayload>(`/api/summaries/filing/${id}`, 3600),
  ])
  if (!filing?.company?.ticker || !summary?.business_overview) return null

  const excerpt = toExcerpt(summary.business_overview)
  if (!excerpt) return null

  return {
    filingId: filing.id,
    ticker: filing.company.ticker,
    companyName: filing.company.name,
    filingType: filing.filing_type,
    filingDate: filing.filing_date,
    secUrl: filing.sec_url,
    excerpt,
    qualityTier: summary.raw_summary?.quality?.tier ?? null,
    metrics: pickMetrics(summary),
  }
}

export interface NotableFiling {
  ticker: string
  company_name: string
  form: string
  reason: string
  reason_label: string
  filed_date: string
  sec_url: string
}

export interface NotableFilingsResponse {
  filings: NotableFiling[]
  status: string
  timestamp: string
}

/** Market-wide notable filings (EDGAR-native). Server-rendered only — the section self-omits
 * when the list is empty, so there is no client query. ISR 15 min, matching the backend's own
 * serve-cache TTL. */
export const fetchNotableFilings = (): Promise<NotableFilingsResponse | null> =>
  fetchJson<NotableFilingsResponse>('/api/notable_filings?limit=8', 900)

/** Initial trending-tickers payload so the first paint shows real data, not skeletons. */
export const fetchTrendingInitial = (): Promise<TrendingTickerResponse | null> =>
  fetchJson<TrendingTickerResponse>('/api/trending_tickers', 300)

export interface ReportingCompany {
  ticker: string
  name: string
  earnings_date: string
  // 'dmh' = during market hours; the earnings engine can emit it alongside bmo/amc. The
  // ReportingThisWeek renderer only labels bmo/amc and shows no chip for dmh/null.
  time: 'bmo' | 'amc' | 'dmh' | null
}

export interface ReportingThisWeekResponse {
  companies: ReportingCompany[]
  week_start: string
  week_end: string
  status: string
  timestamp: string
}

/** Curated large-caps reporting earnings this week, for the homepage section below
 * the hero. Revalidates every 6h, matching the backend's own cache TTL — no point
 * refreshing more often than the backend actually recomputes. */
export const fetchReportingThisWeek = (): Promise<ReportingThisWeekResponse | null> =>
  fetchJson<ReportingThisWeekResponse>('/api/reporting_this_week', 21600)

// --- Server-side fetchers for the programmatic-SEO pages (company + filing) --------------------
// These build the HTML crawlers receive on /company/[ticker] and /filing/[id] (on-demand ISR);
// the client page then takes over with React Query, seeded with the same payloads as
// `initialData`. They call the same READ-ONLY endpoints the client uses; the summary read can
// never trigger AI generation (generation is an auth-gated POST). Next dedupes identical
// fetch() calls within a render, so generateMetadata and the page share one backend request.
// NOTE: no em-dashes in comments in this section. The no-em-dash-copy voice guard parses this
// .ts file as TSX, and the explicit generic call sites below misparse just enough that nearby
// comments get swallowed into literal text and flagged.

export type ServerFetchResult<T> =
  | { status: 'ok'; data: T }
  | { status: 'not-found' }
  | { status: 'unavailable' }

const fetchJsonResult = async <T>(
  path: string,
  revalidateSeconds: number,
): Promise<ServerFetchResult<T>> => {
  try {
    const res = await fetch(`${getBackendUrl()}${path}`, {
      headers: { accept: 'application/json' },
      next: { revalidate: revalidateSeconds },
      signal: AbortSignal.timeout(5000),
    })
    if (res.status === 404) return { status: 'not-found' }
    if (!res.ok) return { status: 'unavailable' }
    return { status: 'ok', data: (await res.json()) as T }
  } catch {
    return { status: 'unavailable' }
  }
}

export const fetchCompanyServer = (ticker: string): Promise<ServerFetchResult<Company>> =>
  fetchJsonResult<Company>(`/api/companies/${encodeURIComponent(ticker)}`, 1800)

export const fetchCompanyFilingsServer = (ticker: string): Promise<ServerFetchResult<Filing[]>> =>
  fetchJsonResult<Filing[]>(`/api/filings/company/${encodeURIComponent(ticker)}`, 1800)

// Filing metadata is immutable once filed: revalidate daily.
export const fetchFilingServer = (filingId: number): Promise<ServerFetchResult<Filing>> =>
  fetchJsonResult<Filing>(`/api/filings/${filingId}`, 86400)

/**
 * Read-only summary fetch. Mirrors the client fetcher's normalization (`getSummary`):
 * a 404 or an empty stub (no business_overview) becomes `data: null`, i.e. "confirmed no
 * summary yet", which is distinct from `unavailable`, where we know nothing.
 */
export const fetchFilingSummaryServer = async (
  filingId: number,
): Promise<ServerFetchResult<Summary | null>> => {
  const result = await fetchJsonResult<Summary>(`/api/summaries/filing/${filingId}`, 3600)
  if (result.status === 'not-found') return { status: 'ok', data: null }
  if (result.status === 'ok' && !result.data?.business_overview) return { status: 'ok', data: null }
  return result
}

/**
 * Whether a summary carries real, displayable content (vs the legacy "Generating summary"
 * placeholder). Keep in sync with `hasSummaryContent` in
 * features/summaries/hooks/useSummaryGeneration.ts: this server-side twin drives the
 * noindex decision on filing pages, so index/noindex must match what visitors actually see.
 */
export const summaryHasDisplayableContent = (summary: Summary | null | undefined): boolean =>
  !!(summary?.business_overview && !summary.business_overview.includes('Generating summary'))

import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { EXAMPLE_FILING_ID } from '@/lib/featureFlags'
import type { HotFilingsResponse } from '@/components/HotFilings'
import type { TrendingTickerResponse } from '@/features/companies/api/companies-api'

/**
 * Server-side data for the homepage (ISR). Every helper returns null on any
 * failure — the page renders a static fallback instead, so the homepage never
 * breaks (or slows the build) when the backend is unreachable.
 */

const getBackendUrl = (): string =>
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NODE_ENV === 'development'
    ? 'http://localhost:8000'
    : 'https://api.earningsnerd.io')

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
const toExcerpt = (markdown: string): string => {
  const plain = stripInternalNotices(markdown)
    .replace(/^#{1,6}\s+.*$/gm, '') // headings
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
    const fact = facts.find((f) => f.metric && pattern.test(f.metric) && f.currentPeriod)
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

/** Initial hot-filings payload so the first paint shows real data, not skeletons. */
export const fetchHotFilingsInitial = (limit: number): Promise<HotFilingsResponse | null> =>
  fetchJson<HotFilingsResponse>(`/api/hot_filings?limit=${limit}`, 300)

/** Initial trending-tickers payload for the same reason. */
export const fetchTrendingInitial = (): Promise<TrendingTickerResponse | null> =>
  fetchJson<TrendingTickerResponse>('/api/trending_tickers', 300)

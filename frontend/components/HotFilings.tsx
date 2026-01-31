'use client'

import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNowStrict } from 'date-fns'
import { Flame, ArrowUpRight, AlertTriangle, Calendar } from 'lucide-react'
import clsx from 'clsx'
import Link from 'next/link'
import posthog from 'posthog-js'

import { getApiUrl } from '@/lib/api/client'

const API_BASE_URL = getApiUrl().replace(/\/$/, '')

// Human-readable labels for buzz sources
const SOURCE_LABELS: Record<string, string> = {
  recency: 'Recent',
  search_activity: 'Searched',
  filing_velocity: 'Active Filer',
  earnings_calendar: 'Earnings Soon',
  finnhub_news_buzz: 'In the News',
  finnhub_sentiment: 'Sentiment',
}

// Human-readable labels for buzz components
const COMPONENT_LABELS: Record<string, string> = {
  recency: 'Recency',
  search_activity: 'Search Activity',
  filing_velocity: 'Filing Velocity',
  filing_type_bonus: 'Filing Type',
  earnings_calendar: 'Earnings Calendar',
  news_buzz: 'News Buzz',
  news_headlines: 'Headlines',
  news_sentiment: 'Sentiment',
}

function formatSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source.replace(/_/g, ' ')
}

function formatComponentLabel(key: string): string {
  return COMPONENT_LABELS[key] ?? key.replace(/_/g, ' ')
}

export type HotFiling = {
  filing_id: number | null
  symbol: string | null
  company_name: string | null
  filing_type: string
  filing_date: string
  buzz_score: number
  sources: string[]
  buzz_components?: Record<string, number>
}

export type HotFilingsResponse = {
  filings: HotFiling[]
  last_updated: string
}

async function fetchHotFilings(limit: number): Promise<HotFilingsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/hot_filings?limit=${limit}`, {
    headers: { accept: 'application/json' },
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch hot filings (${response.status})`)
  }

  return response.json() as Promise<HotFilingsResponse>
}

function getBuzzColor(score: number): string {
  if (score >= 8) return 'bg-gradient-to-r from-orange-500 to-red-500'
  if (score >= 5) return 'bg-gradient-to-r from-amber-400 to-orange-500'
  if (score >= 3) return 'bg-gradient-to-r from-yellow-400 to-amber-500'
  return 'bg-gradient-to-r from-slate-500 to-slate-600'
}

function getBuzzLabel(score: number): string {
  if (score >= 8) return 'On Fire'
  if (score >= 5) return 'Heating Up'
  if (score >= 3) return 'Warming'
  return 'Cooling'
}

const skeletonCards = new Array(6).fill(null)

export default function HotFilings({ limit = 8 }: { limit?: number }) {
  const { data, error, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['hot-filings', limit],
    queryFn: () => fetchHotFilings(limit),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {skeletonCards.map((_, index) => (
          <div
            key={index}
            className="flex animate-pulse items-center justify-between rounded-lg border border-white/10 bg-white/5 px-4 py-4"
          >
            <div className="flex flex-col space-y-2">
              <div className="h-4 w-40 rounded bg-white/10" />
              <div className="h-3 w-24 rounded bg-white/10" />
            </div>
            <div className="h-6 w-16 rounded bg-white/10" />
          </div>
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-4 w-4" />
          <p>Unable to load hot filings. Please try again soon.</p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-3 inline-flex items-center rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!data.filings || data.filings.length === 0) {
    return (
      <p className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
        No major filings in the last 24 hours.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {data.filings.map((filing) => {
        const filingDate = new Date(filing.filing_date)
        const relative = formatDistanceToNowStrict(filingDate, { addSuffix: true })
        const isFresh = Date.now() - filingDate.getTime() < 1000 * 60 * 60 // 1 hour
        const buzzColor = getBuzzColor(filing.buzz_score)
        const buzzLabel = getBuzzLabel(filing.buzz_score)

        return (
          <div
            key={`${filing.filing_id}-${filing.filing_date}`}
            className="group rounded-xl border border-white/10 bg-white/5 p-4 transition hover:border-orange-400/50 hover:bg-white/10"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <div
                    className={clsx(
                      'flex h-8 w-8 items-center justify-center rounded-full bg-orange-500/20 text-orange-300',
                      isFresh && 'animate-pulse'
                    )}
                    aria-hidden
                  >
                    <Flame className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-100">
                      {filing.company_name ?? 'Unknown Company'}
                    </div>
                    <div className="text-xs uppercase tracking-wide text-slate-400">
                      {filing.symbol ?? 'N/A'} • {filing.filing_type}
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-slate-400">Filed {relative}</p>

                {filing.sources?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide text-slate-300">
                    {filing.sources.map((source) => (
                      <span
                        key={source}
                        className={clsx(
                          'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
                          source === 'earnings_calendar'
                            ? 'border-amber-400/30 bg-amber-500/10 text-amber-200'
                            : 'border-white/10 bg-white/5'
                        )}
                      >
                        {source === 'earnings_calendar' && <Calendar className="h-3 w-3" />}
                        {formatSourceLabel(source)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex flex-col items-end">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Buzz
                  </span>
                  <span className="text-lg font-bold text-orange-300">{filing.buzz_score.toFixed(1)}</span>
                </div>
                <div className="mt-2 flex w-36 items-center space-x-2">
                  <div className="h-2 w-full rounded-full bg-slate-700">
                    <div
                      className={clsx('h-2 rounded-full', buzzColor)}
                      style={{ width: `${Math.min(filing.buzz_score, 10) * 10}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-medium uppercase text-slate-300">{buzzLabel}</span>
                </div>
                {filing.buzz_components ? (
                  <div className="mt-3 text-[10px] text-slate-400">
                    {Object.entries(filing.buzz_components)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 2)
                      .map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between gap-3">
                          <span>{formatComponentLabel(key)}</span>
                          <span className="font-semibold text-slate-200">{value.toFixed(1)}</span>
                        </div>
                      ))}
                  </div>
                ) : null}
                <Link
                  href={filing.filing_id ? `/filing/${filing.filing_id}` : '#'}
                  onClick={() => posthog.capture('hot_filing_summary_clicked', {
                    filing_id: filing.filing_id,
                    symbol: filing.symbol,
                    buzz_score: filing.buzz_score
                  })}
                  className="mt-4 inline-flex items-center rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-orange-400 hover:text-orange-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                >
                  View AI Summary
                  <ArrowUpRight className="ml-1 h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        )
      })}

      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-slate-400">
        <span>Updated {formatDistanceToNowStrict(new Date(data.last_updated), { addSuffix: true })}</span>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isRefetching}
          className="inline-flex items-center rounded-md border border-white/10 px-2 py-1 text-[10px] font-semibold text-slate-200 transition hover:border-orange-400 hover:text-orange-200 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          {isRefetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
    </div>
  )
}

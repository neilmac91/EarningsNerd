'use client'

import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNowStrict } from 'date-fns'
import { ArrowUpRightIcon, CalendarBlankIcon, PulseIcon, WarningIcon } from '@/lib/icons'
import clsx from 'clsx'
import Link from 'next/link'
import posthog from 'posthog-js'

import { getApiUrl } from '@/lib/api/client'
import { FilingPulse, type Pulse } from '@/components/FilingPulse'
import CompanyLogo from '@/components/CompanyLogo'

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

function formatSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source.replace(/_/g, ' ')
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
  pulse?: Pulse
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

const skeletonCards = new Array(6).fill(null)

export default function HotFilings({
  limit = 8,
  initialData,
}: {
  limit?: number
  // Server-fetched payload (ISR) so the first paint shows real filings
  // instead of skeletons; the client query keeps refreshing as before.
  initialData?: HotFilingsResponse
}) {
  const { data, error, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['hot-filings', limit],
    queryFn: () => fetchHotFilings(limit),
    initialData,
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
            className="flex animate-pulse items-center justify-between rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none px-4 py-4"
          >
            <div className="flex flex-col space-y-2">
              <div className="h-4 w-40 rounded bg-brand-weak dark:bg-white/10" />
              <div className="h-3 w-24 rounded bg-brand-weak dark:bg-white/10" />
            </div>
            <div className="h-6 w-16 rounded bg-brand-weak dark:bg-white/10" />
          </div>
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-error-light/40 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/10 p-4 text-sm text-error-light dark:text-error-dark">
        <div className="flex items-center space-x-2">
          <WarningIcon className="h-4 w-4" />
          <p>Unable to load hot filings. Please try again soon.</p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-3 inline-flex items-center rounded-md border border-border-light dark:border-white/20 px-3 py-1 text-xs font-medium text-text-primary-light dark:text-text-primary-dark transition hover:bg-brand-weak dark:hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-light focus-visible:ring-offset-2 focus-visible:ring-offset-background-light dark:focus-visible:ring-offset-slate-900"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!data.filings || data.filings.length === 0) {
    return (
      <p className="rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none p-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        No major filings in the last 24 hours.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {data.filings.map((filing) => {
        const filingDate = new Date(filing.filing_date)
        const relative = formatDistanceToNowStrict(filingDate, { addSuffix: true })

        return (
          <div
            key={`${filing.filing_id}-${filing.filing_date}`}
            className="glass-card group rounded-xl p-4 transition-all duration-300"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  {filing.symbol ? (
                    <CompanyLogo ticker={filing.symbol} name={filing.company_name} size={32} />
                  ) : (
                    <div
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-strong/10 dark:bg-brand-dark/15 text-brand-strong dark:text-brand-strong-dark"
                      aria-hidden
                    >
                      <PulseIcon className="h-4 w-4" />
                    </div>
                  )}
                  <div>
                    <div className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                      {filing.company_name ?? 'Unknown Company'}
                    </div>
                    <div className="text-xs uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
                      {filing.symbol ?? 'N/A'} • {filing.filing_type}
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">Filed {relative}</p>

                {filing.sources?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
                    {filing.sources.map((source) => (
                      <span
                        key={source}
                        className={clsx(
                          'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
                          source === 'earnings_calendar'
                            ? 'border-warning-light/30 dark:border-warning-dark/30 bg-warning-light/10 dark:bg-warning-dark/10 text-warning-light dark:text-warning-dark'
                            : 'border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5'
                        )}
                      >
                        {source === 'earnings_calendar' && <CalendarBlankIcon className="h-3 w-3" />}
                        {formatSourceLabel(source)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex flex-col items-end">
                <FilingPulse pulse={filing.pulse} score={filing.buzz_score} />
                <Link
                  href={filing.filing_id ? `/filing/${filing.filing_id}` : '#'}
                  onClick={() => posthog.capture('hot_filing_summary_clicked', {
                    filing_id: filing.filing_id,
                    symbol: filing.symbol,
                    buzz_score: filing.buzz_score
                  })}
                  className="mt-4 inline-flex items-center rounded-lg border border-border-light dark:border-white/10 px-3 py-1.5 text-xs font-semibold text-text-primary-light dark:text-text-primary-dark transition hover:border-brand-strong dark:hover:border-brand-dark hover:text-brand-strong dark:hover:text-brand-strong-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-light focus-visible:ring-offset-2 focus-visible:ring-offset-background-light dark:focus-visible:ring-offset-slate-900"
                >
                  View AI Summary
                  <ArrowUpRightIcon className="ml-1 h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        )
      })}

      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
        <span>Updated {formatDistanceToNowStrict(new Date(data.last_updated), { addSuffix: true })}</span>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isRefetching}
          className="inline-flex items-center rounded-md border border-border-light dark:border-white/10 px-2 py-1 text-[10px] font-semibold text-text-secondary-light dark:text-text-secondary-dark transition hover:border-brand-strong dark:hover:border-brand-dark hover:text-brand-strong dark:hover:text-brand-strong-dark disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-light focus-visible:ring-offset-2 focus-visible:ring-offset-background-light dark:focus-visible:ring-offset-slate-900"
        >
          {isRefetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
    </div>
  )
}

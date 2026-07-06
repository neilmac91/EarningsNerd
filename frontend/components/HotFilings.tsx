'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNowStrict } from 'date-fns'
import { ArrowUpRightIcon, CalendarBlankIcon, PulseIcon } from '@/lib/icons'
import Link from 'next/link'
import posthog from 'posthog-js'

import { getApiUrl } from '@/lib/api/client'
import { FilingPulse, type Pulse } from '@/components/FilingPulse'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, Button, buttonVariants, GuidanceCard, Skeleton } from '@/components/ui'

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
    queryKey: queryKeys.hotFilings(limit),
    queryFn: () => fetchHotFilings(limit),
    initialData,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (isLoading) {
    return (
      <div role="status" aria-label="Loading hot filings" className="space-y-2">
        {skeletonCards.map((_, index) => (
          <Skeleton key={index} className="h-20 rounded-xl" />
        ))}
        <span className="sr-only">Loading hot filings…</span>
      </div>
    )
  }

  if (error || !data) {
    return (
      <GuidanceCard
        variant="error"
        title="Unable to load hot filings"
        description="Please try again soon."
        action={
          <Button variant="secondary" onClick={() => refetch()} loading={isRefetching} loadingText="Retrying…">
            Retry
          </Button>
        }
      />
    )
  }

  if (!data.filings || data.filings.length === 0) {
    return (
      <GuidanceCard variant="empty" title="No major filings" description="No major filings in the last 24 hours." />
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
            className="glass-card group rounded-xl p-4 transition duration-base"
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
                  <div className="mt-3 flex flex-wrap gap-2">
                    {filing.sources.map((source) => (
                      // `new` = the warning-tinted chip; icon overrides its pulse dot.
                      <Badge
                        key={source}
                        variant={source === 'earnings_calendar' ? 'new' : 'neutral'}
                        icon={source === 'earnings_calendar' ? <CalendarBlankIcon className="h-3 w-3" /> : null}
                      >
                        {formatSourceLabel(source)}
                      </Badge>
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
                  className={buttonVariants({ variant: 'secondary', size: 'sm', className: 'mt-4' })}
                >
                  View AI Summary
                  <ArrowUpRightIcon className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        )
      })}

      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
        <span>Updated {formatDistanceToNowStrict(new Date(data.last_updated), { addSuffix: true })}</span>
        <Button variant="ghost" size="sm" onClick={() => refetch()} loading={isRefetching} loadingText="Refreshing…">
          Refresh
        </Button>
      </div>
    </div>
  )
}

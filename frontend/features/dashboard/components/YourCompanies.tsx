'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import Link from 'next/link'
import { useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowRightIcon, XIcon } from '@/lib/icons'
import { removeFromWatchlist, WatchlistInsight } from '@/features/watchlist/api/watchlist-api'
import { queryKeys } from '@/lib/queryKeys'
import analytics from '@/lib/analytics'
import { formatLocalDate } from '@/lib/format'
import CompanyLogo from '@/components/CompanyLogo'
import { Button, Card, GuidanceCard, Skeleton } from '@/components/ui'
import WatchlistAddSearch from '@/features/watchlist/components/WatchlistAddSearch'
import SummaryStatusBadge from '@/features/watchlist/components/SummaryStatusBadge'

interface YourCompaniesProps {
  insights: WatchlistInsight[] | undefined
  isLoading: boolean
  isError: boolean
  refetch: () => void
  isFetching: boolean
}

/**
 * The "Your companies" status section (§3.2): one compact row per watched company, built from the
 * existing watchlist-insights response, with an inline add-search and a link to the full insights
 * page. The row's "Last filed" chip is deliberately labelled differently from the feed card's
 * "Latest report": insights has no form filter, so "last filed" may be a recent 8-K while the feed
 * shows an older 10-Q for the same company.
 */
export default function YourCompanies({ insights, isLoading, isError, refetch, isFetching }: YourCompaniesProps) {
  const queryClient = useQueryClient()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const removedTicker = useRef<string | null>(null)

  // A successful removal drops its row, and the focused remove button with it, once insights
  // refetch. Focus would fall to <body>; land it on the section heading instead.
  useEffect(() => {
    const ticker = removedTicker.current
    if (ticker === null || insights?.some((insight) => insight.company.ticker === ticker)) return
    removedTicker.current = null
    if (document.activeElement === document.body) headingRef.current?.focus({ preventScroll: true })
  }, [insights])

  // A successful Retry swaps the error card, and the focused Retry in it, for the list. The press is
  // tracked through its own fetch: on success focus lands on the heading (only when it fell to
  // <body>); a retry that fails again leaves the card and its Retry in place and disarms.
  const retry = useRef<'pressed' | 'fetching' | null>(null)
  useEffect(() => {
    if (retry.current === 'pressed' && isFetching) retry.current = 'fetching'
    else if (retry.current === 'fetching' && !isFetching) {
      retry.current = null
      if (!isError && document.activeElement === document.body) headingRef.current?.focus({ preventScroll: true })
    }
  }, [isFetching, isError])

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: (_data, ticker) => {
      removedTicker.current = ticker
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist() })
      const rowGone = queryClient.invalidateQueries({ queryKey: queryKeys.watchlistInsights() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardFeed() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardCalendar() })
      analytics.watchlistRemoved(ticker)
      toast.success(`${ticker} removed from your watchlist`)
      // Returned, so the removal stays pending until the insights refetch drops the row: the remove
      // button keeps focus, and released any sooner a second Enter would DELETE the ticker again.
      return rowGone
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Couldn't update your watchlist. Please try again.")
    },
  })
  const pendingTicker = removeMutation.isPending ? removeMutation.variables : null

  return (
    <section>
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mb-4 text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
      >
        Your companies
      </h2>

      {/* Inline add-from-search: track a company without leaving the dashboard. */}
      <div className="mb-4">
        <WatchlistAddSearch />
      </div>

      {isLoading ? (
        <div role="status" aria-label="Loading your companies" className="space-y-2">
          <Skeleton className="h-14 rounded-xl" />
          <Skeleton className="h-14 rounded-xl" />
          <Skeleton className="h-14 rounded-xl" />
          <span className="sr-only">Loading your companies…</span>
        </div>
      ) : isError ? (
        <GuidanceCard
          variant="error"
          title="Unable to load your companies"
          description="Please retry in a moment."
          action={
            <Button
              variant="secondary"
              onClick={() => {
                retry.current = 'pressed'
                refetch()
              }}
              loading={isFetching}
              loadingText="Retrying…"
            >
              Retry
            </Button>
          }
        />
      ) : !insights || insights.length === 0 ? (
        <GuidanceCard
          variant="empty"
          title="No companies yet"
          description="Track a company with the search above, or from any company page."
        />
      ) : (
        <>
          <Card className="divide-y divide-border-light dark:divide-border-dark">
            {insights.map((insight: WatchlistInsight) => {
              const latest = insight.latest_filing
              return (
                // The status cluster drops to a second line only when the name column would fall below
                // basis-16 (a long "Generating (<stage>)" badge at ~320–360px); max-w-fit keeps the
                // link hugging its content otherwise, so wider rows lay out exactly as before.
                <div key={insight.company.id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3">
                  <Link
                    href={`/company/${insight.company.ticker}`}
                    className="flex min-w-0 max-w-fit grow basis-16 items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                  >
                    <CompanyLogo decorative ticker={insight.company.ticker} name={formatCompanyName(insight.company.name)} size={28} />
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-text-primary-light hover:text-brand-strong dark:text-text-primary-dark dark:hover:text-brand-strong-dark">
                        {formatCompanyName(insight.company.name)}
                      </div>
                      <div className="truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
                        {insight.company.ticker}
                      </div>
                    </div>
                  </Link>
                  <div className="ml-auto flex flex-shrink-0 items-center gap-3">
                    <span className="hidden text-xs text-text-tertiary-light sm:inline dark:text-text-secondary-dark">
                      {latest
                        ? `Last filed ${latest.filing_type} · ${formatLocalDate(latest.filing_date, 'MMM d, yyyy')}`
                        : 'No filings synced yet'}
                    </span>
                    {latest && (
                      <SummaryStatusBadge
                        status={latest.summary_status}
                        needsRegeneration={latest.needs_regeneration}
                      />
                    )}
                    {/* aria-disabled + aria-busy + an early return while a removal is in flight, not
                        native `disabled`: Chromium blurs a focused button that turns disabled. */}
                    <button
                      onClick={() => {
                        if (removeMutation.isPending) return
                        removeMutation.mutate(insight.company.ticker)
                      }}
                      aria-disabled={removeMutation.isPending || undefined}
                      aria-busy={pendingTicker === insight.company.ticker || undefined}
                      className="rounded-lg p-2 text-error-light hover:bg-error-light/10 focus-visible:outline-none focus-visible:shadow-ring-error aria-disabled:opacity-50 dark:text-error-dark dark:hover:bg-error-dark/15"
                      title="Remove from watchlist"
                      aria-label={`Remove ${formatCompanyName(insight.company.name)} from watchlist`}
                    >
                      <XIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              )
            })}
          </Card>
          <div className="mt-4 text-right">
            <Link
              href="/dashboard/watchlist"
              className="inline-flex items-center gap-1 rounded-lg text-sm font-medium text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              Open watchlist insights
              <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </div>
        </>
      )}
    </section>
  )
}

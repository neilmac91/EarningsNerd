'use client'

import Link from 'next/link'
import { queryKeys } from '@/lib/queryKeys'
import { useQuery } from '@tanstack/react-query'
import { ArrowRightIcon, NewspaperIcon } from '@/lib/icons'
import { getDashboardFeed } from '@/features/dashboard/api/dashboard-api'
import { Button, GuidanceCard, Skeleton } from '@/components/ui'
import WhatChangedCard from './WhatChangedCard'
import FeedOnboarding from './FeedOnboarding'

// Three rows of the two-column grid. The feed now shows one card per company, so this caps the page
// at the six most recently-active companies; the rest are one click away via the overflow link.
const MAX_CARDS = 6

export default function FilingFeed({
  enabled = true,
  watchlistCount,
}: {
  enabled?: boolean
  /** Number of companies the user follows — the true overflow count and the empty-state switch. */
  watchlistCount?: number
}) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: queryKeys.dashboardFeed(),
    queryFn: () => getDashboardFeed(20),
    retry: false,
    enabled,
  })

  const visible = data ? data.slice(0, MAX_CARDS) : []
  // Overflow count comes from the watchlist (companies followed), never data.length — the feed array
  // is capped at the fetch limit, so data.length would misreport "See all 20 companies" for a user
  // following 30. When the true count isn't known, drop the number rather than show a wrong one.
  const hasMore =
    watchlistCount != null ? watchlistCount > visible.length : (data?.length ?? 0) > MAX_CARDS
  const overflowLabel =
    watchlistCount != null ? `See all ${watchlistCount} companies` : 'See all companies'

  return (
    <section>
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <NewspaperIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
          <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            What&apos;s new
          </h2>
        </div>
        <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          The latest filing from each company you follow.
        </p>
      </div>

      {isLoading ? (
        <div role="status" aria-label="Loading feed" className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
          <span className="sr-only">Loading feed…</span>
        </div>
      ) : isError ? (
        <GuidanceCard
          variant="error"
          title="Couldn't load your feed"
          description="Please retry in a moment."
          action={
            <Button variant="secondary" onClick={() => refetch()} loading={isFetching} loadingText="Retrying…">
              Retry
            </Button>
          }
        />
      ) : !data || data.length === 0 ? (
        watchlistCount === 0 ? (
          // Empty watchlist (the common beta case): an actionable onboarding state. Shown ONLY when
          // the watchlist is known-empty. While the count is unknown (insights still loading, or the
          // insights query errored) we fall through to the quiet state rather than the loud "follow
          // your first company" panel, which would otherwise flash for a returning user and could
          // contradict the Your-companies error card.
          <FeedOnboarding />
        ) : (
          // Watchlist populated (or count not yet known): companies exist but no eligible filings
          // yet (just added, sync pending).
          <GuidanceCard
            variant="empty"
            title="Nothing new yet"
            description="We're syncing filings for your companies. Check back in a few minutes."
          />
        )
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {visible.map((item) => (
              <WhatChangedCard key={item.filing_id} item={item} />
            ))}
          </div>
          {hasMore && (
            <div className="mt-4 text-right">
              <Link
                href="/dashboard/watchlist"
                className="inline-flex items-center gap-1 rounded-lg text-sm font-medium text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
              >
                {overflowLabel}
                <ArrowRightIcon className="h-4 w-4" />
              </Link>
            </div>
          )}
        </>
      )}
    </section>
  )
}

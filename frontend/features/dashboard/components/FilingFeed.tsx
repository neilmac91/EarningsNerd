'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useQuery } from '@tanstack/react-query'
import { NewspaperIcon } from '@/lib/icons'
import { getDashboardFeed } from '@/features/dashboard/api/dashboard-api'
import { Button, GuidanceCard, Skeleton } from '@/components/ui'
import WhatChangedCard from './WhatChangedCard'

export default function FilingFeed({ enabled = true }: { enabled?: boolean }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: queryKeys.dashboardFeed(),
    queryFn: () => getDashboardFeed(20),
    retry: false,
    enabled,
  })

  return (
    <section>
      <div className="mb-4 flex items-center gap-2">
        <NewspaperIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          What&apos;s new
        </h2>
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
        <GuidanceCard
          variant="empty"
          title="No new filings yet"
          description="Add companies to your watchlist. When they file a 10-K or 10-Q, you'll see what changed here first."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {data.map((item) => (
            <WhatChangedCard key={item.filing_id} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

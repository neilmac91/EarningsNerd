'use client'

import { useQuery } from '@tanstack/react-query'
import { NewspaperIcon } from '@/lib/icons'
import { getDashboardFeed } from '@/features/dashboard/api/dashboard-api'
import StateCard from '@/components/StateCard'
import WhatChangedCard from './WhatChangedCard'

export default function FilingFeed({ enabled = true }: { enabled?: boolean }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['dashboard-feed'],
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
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-xl border border-border-light bg-panel-light dark:border-border-dark dark:bg-panel-dark"
            />
          ))}
        </div>
      ) : isError ? (
        <StateCard
          variant="error"
          title="Couldn't load your feed"
          message="Please retry in a moment."
          action={
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="mt-2 inline-flex items-center rounded-lg bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-2 text-sm font-medium transition disabled:opacity-60"
            >
              {isFetching ? 'Retrying…' : 'Retry'}
            </button>
          }
        />
      ) : !data || data.length === 0 ? (
        <StateCard
          variant="info"
          title="No new filings yet"
          message="Add companies to your watchlist — when they file a 10-K or 10-Q, you'll see what changed here first."
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

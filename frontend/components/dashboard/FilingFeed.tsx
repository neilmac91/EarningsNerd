'use client'

import { useQuery } from '@tanstack/react-query'
import { Newspaper } from 'lucide-react'
import { getDashboardFeed } from '@/features/dashboard/api/dashboard-api'
import StateCard from '@/components/StateCard'
import WhatChangedCard from './WhatChangedCard'

export default function FilingFeed() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['dashboard-feed'],
    queryFn: () => getDashboardFeed(20),
    retry: false,
  })

  return (
    <section>
      <div className="mb-4 flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-mint-600 dark:text-mint-400" />
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
              className="mt-2 inline-flex items-center rounded-lg bg-mint-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-mint-400 disabled:opacity-60"
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

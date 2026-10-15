'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inputClasses } from '@/components/ui/Input'
import { Notice, Skeleton } from '@/components/ui'
import SecondaryHeader from '@/components/SecondaryHeader'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import {
  listFeedback,
  type FeedbackRecord,
  type FeedbackStatus,
  type FeedbackType,
} from '@/features/admin/api/admin-api'
import FeedbackRow from '@/features/admin/components/FeedbackRow'

const LIST_LIMIT = 200

export default function AdminFeedbackPage() {
  const [statusFilter, setStatusFilter] = useState<'all' | FeedbackStatus>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | FeedbackType>('all')

  const filters = { status: statusFilter, type: typeFilter }

  const feedbackQuery = useQuery({
    // Filtering is server-side, so the active filters are part of the cache key.
    queryKey: queryKeys.adminFeedback.list(filters),
    queryFn: () => listFeedback(filters),
    retry: false,
  })
  const { data: feedback } = feedbackQuery
  // Holds the error card, and its focused Retry, through the refetch a Retry starts.
  const feedbackFailure = useRetainedFailure(feedbackQuery, queryKeys.adminFeedback.list(filters))
  const feedbackHeadingRef = useRef<HTMLHeadingElement>(null)

  const hasFilters = statusFilter !== 'all' || typeFilter !== 'all'

  return (
    <>
      <SecondaryHeader
        title="Feedback"
        subtitle="Triage bug reports, feature requests, and general feedback"
        backHref="/dashboard"
        backLabel="Back to dashboard"
      />

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-light px-6 py-4 dark:border-white/10">
            {/* tabIndex -1: where focus goes if the Retry unmounts while it holds focus. */}
            <h2
              ref={feedbackHeadingRef}
              tabIndex={-1}
              className="text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
            >
              Feedback
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="filter-status" className="sr-only">
                Filter by status
              </label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | FeedbackStatus)}
                className={inputClasses({ select: true, autoWidth: true })}
              >
                <option value="all">All statuses</option>
                <option value="new">New</option>
                <option value="triaged">Triaged</option>
                <option value="resolved">Resolved</option>
              </select>

              <label htmlFor="filter-type" className="sr-only">
                Filter by type
              </label>
              <select
                id="filter-type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as 'all' | FeedbackType)}
                className={inputClasses({ select: true, autoWidth: true })}
              >
                <option value="all">All types</option>
                <option value="bug">Bug</option>
                <option value="feature">Feature</option>
                <option value="general">General</option>
              </select>
            </div>
          </div>

          {feedbackQuery.isLoading && !feedbackFailure.failed ? (
            <div role="status" aria-label="Loading feedback" className="space-y-3 p-6">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
              <span className="sr-only">Loading feedback…</span>
            </div>
          ) : feedbackFailure.failed ? (
            <div className="p-6">
              <Notice
                variant="error"
                title="Could not load the feedback."
                description={isApiError(feedbackFailure.error) ? getErrorMessage(feedbackFailure.error) : undefined}
                action={
                  <RetryButton size="sm" failures={[feedbackFailure]} focusTarget={feedbackHeadingRef}>
                    Retry
                  </RetryButton>
                }
              />
            </div>
          ) : (feedback?.length ?? 0) === 0 ? (
            <p
              role="status"
              className="px-6 py-10 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark"
            >
              {hasFilters ? 'No feedback matches these filters.' : 'No feedback yet. Reports appear here as people send them.'}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border-light dark:divide-white/10">
                <thead className="bg-background-light dark:bg-white/5">
                  <tr>
                    {['Type', 'Message', 'Page', 'From', 'Date', 'Status'].map((col) => (
                      <th
                        key={col}
                        scope="col"
                        className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-light bg-panel-light dark:divide-white/10 dark:bg-panel-dark">
                  {(feedback ?? []).map((item: FeedbackRecord) => (
                    <FeedbackRow key={item.id} feedback={item} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="border-t border-border-light px-6 py-3 text-xs text-text-tertiary-light dark:border-white/10 dark:text-text-secondary-dark">
            Showing the most recent {LIST_LIMIT} feedback items.
          </p>
        </section>
      </main>
    </>
  )
}

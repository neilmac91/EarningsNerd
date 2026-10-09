'use client'

import Link from 'next/link'
import { useId, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRightIcon } from '@/lib/icons'
import { Card, Notice, Skeleton, cx } from '@/components/ui'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import type { Filing } from '@/features/filings/api/filings-api'
import { getWhatChanged } from '@/features/summaries/api/summaries-api'
import { Change, READ_AS } from '@/features/filings/components/WhatChanged'
import { formatLocalDate } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

/** Rows the card shows; the change report on the filing page holds the rest. */
const MAX_ROWS = 3

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
const day = (iso: string | null | undefined) => formatLocalDate(iso, 'MMM d, yyyy')

/**
 * Compare periods (2026-10 critique, 1b and P-07): the company page's entry to the change report of
 * its newest annual report (selectComparisonFiling). The same GET and query key as the filing
 * page's "What changed" section, so following the link renders that section from cache. Each row
 * is a metric, its change in the change report's own vocabulary (the server's display string in its
 * tone's ink after a ▲/▼ glyph) and its "Read as" word, so direction and valence never share one
 * signal. The risk diff stays out until the backend serves one again (change_report_service
 * withholds it). States in place: bones while it loads, Notice + RetryButton on failure, a plain line
 * when the two periods share no comparable figures.
 */
export function ComparePeriodsCard({ filing }: { filing: Filing }) {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const key = queryKeys.whatChanged(filing.id)
  const query = useQuery({
    queryKey: key,
    queryFn: () => getWhatChanged(filing.id),
    staleTime: 10 * 60 * 1000,
  })
  const failure = useRetainedFailure(query, key)
  const report = query.data
  const items = report?.has_changes ? (report.metrics?.items ?? []) : []
  const priorEnded = day(report?.prior_filing?.period_end_date)

  return (
    <Card as="aside" aria-labelledby={headingId} className="p-5">
      <h2 id={headingId} ref={headingRef} tabIndex={-1} className={cx('text-lg font-semibold outline-none', INK)}>
        Compare periods
      </h2>
      {/* Two short lines, so a narrow card never breaks a date across them. */}
      <p className={cx('mt-1 font-data text-xs tabular-nums', MUTED)}>
        {filing.filing_type} · year ended {day(filing.report_date)}
      </p>
      {priorEnded && <p className={cx('font-data text-xs tabular-nums', MUTED)}>vs year ended {priorEnded}</p>}

      {failure.failed ? (
        <div className="mt-4">
          <Notice
            variant="error"
            title="Couldn’t load the comparison"
            description="The rest of this page is unaffected."
            action={
              <RetryButton size="sm" failures={[failure]} focusTarget={headingRef}>
                Retry
              </RetryButton>
            }
          />
        </div>
      ) : query.isLoading ? (
        <div role="status" aria-label="Loading the comparison" className="mt-4">
          <div aria-hidden="true" className={cx('border-t', HAIRLINE)}>
            {[0, 1, 2].map((i) => (
              <div key={i} className={cx('flex items-center justify-between gap-3 border-b py-3', HAIRLINE)}>
                <Skeleton className="h-3.5 w-28" />
                <Skeleton className="h-3.5 w-20" />
              </div>
            ))}
          </div>
          <span className="sr-only">Loading the comparison…</span>
        </div>
      ) : items.length === 0 ? (
        <p className={cx('mt-4 text-sm', MUTED)}>
          {report?.has_prior === false
            ? 'No earlier annual report to compare with yet.'
            : 'These two annual reports share no comparable figures yet.'}
        </p>
      ) : (
        <>
          <ul role="list" className={cx('mt-4 border-t text-sm', HAIRLINE)}>
            {items.slice(0, MAX_ROWS).map((item) => (
              <li key={item.metric} className={cx('flex items-baseline justify-between gap-3 border-b py-2.5', HAIRLINE)}>
                <span className={cx('min-w-0', INK)}>{item.label}</span>
                <span className="flex shrink-0 items-baseline gap-2">
                  <span className="font-data font-semibold tabular-nums">
                    <Change item={item} />
                  </span>
                  <span className={cx('text-xs', MUTED)}>{READ_AS[item.tone] ?? READ_AS.flat}</span>
                </span>
              </li>
            ))}
          </ul>
          {items.length > MAX_ROWS && (
            <p className={cx('mt-2 text-xs', MUTED)}>
              {items.length - MAX_ROWS} more in the change report.
            </p>
          )}
          <Link
            href={`/filing/${filing.id}#what-changed`}
            className={cx(
              '-ml-2 mt-3 inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-sm font-semibold',
              'text-brand-strong transition-colors duration-fast hover:bg-brand-weak',
              'focus-visible:outline-none focus-visible:shadow-ring-brand',
              'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark',
            )}
          >
            Open change report
            <ArrowRightIcon aria-hidden="true" className="h-4 w-4" />
          </Link>
        </>
      )}
    </Card>
  )
}

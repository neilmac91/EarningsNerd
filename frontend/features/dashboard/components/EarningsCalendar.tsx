'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useQuery } from '@tanstack/react-query'
import { CalendarDotsIcon } from '@/lib/icons'
import { getUpcomingCalendar } from '@/features/dashboard/api/dashboard-api'
import { formatLocalDate, fmtCurrency } from '@/lib/format'
import { Card, Skeleton } from '@/components/ui'

const TIME_LABEL: Record<string, string> = { bmo: 'Before open', amc: 'After close' }

export default function EarningsCalendar({ enabled = true }: { enabled?: boolean }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.dashboardCalendar(),
    queryFn: () => getUpcomingCalendar(14),
    retry: false,
    enabled,
  })

  // Always render the section (it self-hid on empty before, which made it appear and vanish as the
  // watchlist changed). When the owned `earnings_events` table has no upcoming rows for the user's
  // tickers, show a quiet one-liner instead of nothing.
  return (
    <Card as="section" className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <CalendarDotsIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
          Upcoming earnings
        </h2>
      </div>

      {isLoading ? (
        <div role="status" aria-label="Loading upcoming earnings" className="space-y-2.5">
          <Skeleton className="h-6 rounded-lg" />
          <Skeleton className="h-6 rounded-lg" />
          <Skeleton className="h-6 rounded-lg" />
          <span className="sr-only">Loading upcoming earnings…</span>
        </div>
      ) : isError ? (
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Couldn&apos;t load upcoming earnings.
        </p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          No earnings dates in the next two weeks.
        </p>
      ) : (
        <ul className="divide-y divide-border-light dark:divide-border-dark">
          {data.map((ev) => (
            <li key={`${ev.ticker}-${ev.earnings_date}`} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <div>
                  <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{ev.ticker}</span>
                  <span className="ml-2 truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    {ev.company_name}
                  </span>
                </div>
                {ev.eps_estimated != null && (
                  <div className="mt-0.5 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                    Est. EPS {fmtCurrency(ev.eps_estimated, { digits: 2 })}
                  </div>
                )}
              </div>
              <div className="flex-shrink-0 text-right text-sm">
                <div className="text-text-primary-light dark:text-text-primary-dark">{formatLocalDate(ev.earnings_date, 'EEE, MMM d', 'TBD')}</div>
                {ev.time && TIME_LABEL[ev.time] && (
                  <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
                    {TIME_LABEL[ev.time]}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

'use client'

import { useQuery } from '@tanstack/react-query'
import { CalendarDays } from 'lucide-react'
import { getUpcomingCalendar } from '@/features/dashboard/api/dashboard-api'
import { formatLocalDate } from '@/lib/format'

const TIME_LABEL: Record<string, string> = { bmo: 'Before open', amc: 'After close' }

export default function EarningsCalendar({ enabled = true }: { enabled?: boolean }) {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-calendar'],
    queryFn: () => getUpcomingCalendar(14),
    retry: false,
    enabled,
  })

  // Stay invisible when there's nothing to show (e.g. FMP not yet configured) — no empty clutter.
  if (isLoading || !data || data.length === 0) return null

  return (
    <section className="rounded-xl border border-border-light bg-background-light p-5 dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-3 flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-mint-600 dark:text-mint-400" />
        <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
          Upcoming earnings
        </h2>
      </div>
      <ul className="divide-y divide-border-light dark:divide-border-dark">
        {data.map((ev) => (
          <li key={`${ev.ticker}-${ev.earnings_date}`} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{ev.ticker}</span>
              <span className="ml-2 truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {ev.company_name}
              </span>
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
    </section>
  )
}

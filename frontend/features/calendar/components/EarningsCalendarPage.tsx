'use client'

/* =============================================================================
   EarningsCalendarPage (features/calendar/components/EarningsCalendarPage.tsx)
   -----------------------------------------------------------------------------
   The /calendar route body. Owns: view (week default | month), the anchor
   date, range fetching, and every system state — skeleton, error (retry),
   empty range, loaded. Dates are America/New_York calendar days end to end:
   the anchor/ranges are plain ISO strings, "today" is asked once via
   Intl(America/New_York), and labels render through formatLocalDate.
============================================================================= */

import { useMemo, useState } from 'react'
import { Button, GuidanceCard, Skeleton } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import { BellIcon, CaretLeftIcon, CaretRightIcon, ClockIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { addDaysIso, addMonths, firstOfMonth, marketHolidayName, mondayOf, todayEasternIso } from '../lib/dates'
import { indexByDate } from '../lib/lanes'
import { useCalendarRange, useEarningsAlerts, useViewer, FREE_ALERT_LIMIT } from '../hooks/useCalendar'
import { WeekView, type DayBucket } from './WeekView'
import { MonthView } from './MonthView'
import { DayDetailDialog } from './DayDetailDialog'
import { BellPopover } from './AlertBell'

type CalendarView = 'week' | 'month'

export default function EarningsCalendarPage() {
  const todayIso = useMemo(() => todayEasternIso(), [])
  const [view, setView] = useState<CalendarView>('week')
  const [anchor, setAnchor] = useState(todayIso)
  const [openDay, setOpenDay] = useState<string | null>(null)

  const range = useMemo(() => {
    if (view === 'week') {
      const from = mondayOf(anchor)
      return { from, to: addDaysIso(from, 6) }
    }
    const from = mondayOf(firstOfMonth(anchor))
    return { from, to: addDaysIso(from, 41) }
  }, [view, anchor])

  const query = useCalendarRange(range.from, range.to)
  const viewer = useViewer()
  const alerts = useEarningsAlerts(viewer)

  const eventsByDate = useMemo(() => indexByDate(query.data?.events ?? []), [query.data])

  const days: DayBucket[] = useMemo(() => {
    const monday = mondayOf(anchor)
    return Array.from({ length: 5 }, (_, i) => {
      const iso = addDaysIso(monday, i)
      return { iso, isToday: iso === todayIso, holidayName: marketHolidayName(iso), events: eventsByDate.get(iso) ?? [] }
    })
  }, [anchor, eventsByDate, todayIso])

  const rangeLabel =
    view === 'month'
      ? formatLocalDate(firstOfMonth(anchor), 'MMMM yyyy')
      : `${formatLocalDate(range.from, 'MMM d')} – ${formatLocalDate(addDaysIso(range.from, 4), 'MMM d, yyyy')}`

  const navigate = (dir: 1 | -1) => {
    setOpenDay(null)
    setAnchor((a) => (view === 'week' ? addDaysIso(mondayOf(a), dir * 7) : addMonths(a, dir)))
  }

  const isEmpty = query.isSuccess && (query.data?.events?.length ?? 0) === 0

  return (
    <main className="mx-auto max-w-[1180px] px-4 pb-14 pt-7 sm:px-6">
      {/* Title row */}
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-3xl">Earnings calendar</h1>
          <p className="mt-1 max-w-[64ch] text-sm text-text-tertiary-light dark:text-text-secondary-dark">
            The most-anticipated U.S. reports, day by day. Dates are U.S. Eastern calendar days.
          </p>
          {/* Coverage caption — shown only when the backend confirms the index filter is active, so
              it never claims a curated universe while serving everything (accurate across flag states). */}
          {query.data?.universe === 'sp500_nasdaq100' && (
            <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-weak px-2.5 py-1 text-xs font-semibold text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark">
              Covering the S&amp;P 500 &amp; Nasdaq 100
            </span>
          )}
        </div>
        {/* FREE cap usage — a deliberate conversion surface (§3.7). Pro users get NOTHING here by design. */}
        {viewer.signedIn && !viewer.isPro && (
          <div
            title={`Free includes earnings alerts for ${FREE_ALERT_LIMIT} companies`}
            className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-border-light bg-panel-light px-3 py-1.5 text-xs font-semibold text-text-secondary-light shadow-e1 dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:shadow-none"
          >
            <BellIcon aria-hidden="true" className="h-3.5 w-3.5 text-brand-strong dark:text-brand-strong-dark" />
            Alerts
            <span className="font-data tabular-nums text-text-primary-light dark:text-text-primary-dark">
              {viewer.alertCount} of {FREE_ALERT_LIMIT}
            </span>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => { setOpenDay(null); setAnchor(todayIso) }}>
            Today
          </Button>
          <div className="flex items-center">
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label={view === 'week' ? 'Previous week' : 'Previous month'}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary-light transition-colors duration-fast hover:bg-brand-weak hover:text-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              <CaretLeftIcon className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => navigate(1)}
              aria-label={view === 'week' ? 'Next week' : 'Next month'}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary-light transition-colors duration-fast hover:bg-brand-weak hover:text-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              <CaretRightIcon className="h-4 w-4" />
            </button>
          </div>
          <h2 aria-live="polite" className="truncate text-base font-semibold sm:text-lg">
            {rangeLabel}
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden items-center gap-1.5 text-xs text-text-tertiary-light dark:text-text-secondary-dark sm:inline-flex">
            <ClockIcon aria-hidden="true" className="h-3.5 w-3.5" />
            U.S. Eastern
          </span>
          <div
            role="group"
            aria-label="Calendar view"
            className="inline-flex rounded-lg border border-border-light bg-panel-light p-[3px] shadow-e1 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
          >
            {(['week', 'month'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => { setOpenDay(null); setView(v) }}
                className={cx(
                  'h-[26px] rounded-[9px] px-3.5 text-xs font-semibold capitalize transition-colors duration-fast',
                  'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                  view === v
                    ? 'bg-brand text-white shadow-e1 dark:bg-brand-dark dark:text-background-dark'
                    : 'text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark',
                )}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* System states */}
      {query.isPending && <CalendarSkeleton />}
      {query.isError && (
        <GuidanceCard
          variant="error"
          title="Couldn't load the calendar"
          description="The calendar service did not respond. Your alert subscriptions are unaffected."
          action={
            <Button variant="secondary" size="sm" onClick={() => query.refetch()}>
              Try again
            </Button>
          }
        />
      )}
      {isEmpty && (
        <GuidanceCard
          title={view === 'week' ? 'A quiet week' : 'A quiet month'}
          description="No earnings are scheduled in this range yet. Estimated dates appear as companies' reporting patterns firm up."
          action={
            <Button variant="secondary" size="sm" onClick={() => navigate(1)}>
              {view === 'week' ? 'Jump to next week' : 'Jump to next month'}
            </Button>
          }
        />
      )}
      {query.isSuccess && !isEmpty && view === 'week' && (
        <WeekView days={days} alerts={alerts} signedIn={viewer.signedIn} onShowMore={setOpenDay} />
      )}
      {query.isSuccess && !isEmpty && view === 'month' && (
        <MonthView anchorIso={anchor} todayIso={todayIso} eventsByDate={eventsByDate} alerts={alerts} onOpenDay={setOpenDay} />
      )}

      <p className="mt-4 px-1 text-xs leading-relaxed text-text-tertiary-light dark:text-text-secondary-dark">
        Reported dates come from SEC EDGAR 8-K filings. Estimated dates come from each company&rsquo;s own reporting pattern and
        provider data; &ldquo;usually&rdquo; marks a habitual, unconfirmed slot. Not investment advice.
      </p>

      {openDay && (
        <DayDetailDialog
          iso={openDay}
          events={eventsByDate.get(openDay) ?? []}
          alerts={alerts}
          signedIn={viewer.signedIn}
          onClose={() => setOpenDay(null)}
        />
      )}
      {alerts.blocked && <BellPopover blocked={alerts.blocked} onClose={alerts.clearBlocked} />}
    </main>
  )
}

/** Five-column bone sheet mirroring the week layout (single-column on mobile).
    Raw bones are aria-hidden, so the wrapper carries role="status" + sr-only
    label per the skeleton a11y rule (DESIGN_SYSTEM §4). */
function CalendarSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading calendar"
      className="overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <div className="grid grid-cols-1 md:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={cx('p-3.5', i > 0 && 'md:border-l md:border-border-light/60 dark:md:border-white/[0.06]', i > 0 && 'hidden md:block')}>
            <Skeleton className="h-3 w-14" />
            <div className="mt-4 flex flex-col gap-3.5">
              <Skeleton className="h-2.5 w-2/5" />
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-5 rounded-full" />
                <Skeleton className="h-3 flex-1" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-5 rounded-full" />
                <Skeleton className="h-3 flex-1" />
              </div>
              <Skeleton className="h-2.5 w-2/5" />
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-5 rounded-full" />
                <Skeleton className="h-3 flex-1" />
              </div>
            </div>
          </div>
        ))}
      </div>
      <span className="sr-only">Loading calendar…</span>
    </div>
  )
}

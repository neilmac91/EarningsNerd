'use client'

/* =============================================================================
   WeekView (features/calendar/components/WeekView.tsx)
   -----------------------------------------------------------------------------
   Desktop (md+): one calendar sheet — five weekday columns with BMO / AMC /
   During·unspecified lanes stacked inside each day, top 5 per day, "+N more"
   opening the day dialog. Mobile: a vertical day-by-day list with roomier
   44px-target rows and in-place expansion. Both are CSS-switched (hidden
   md:grid / md:hidden) so there is no resize listener to get wrong.
============================================================================= */

import { useState } from 'react'
import { cx } from '@/components/ui/cx'
import { formatLocalDate } from '@/lib/format'
import type { CalendarEvent } from '../api/calendar-api'
import { groupIntoLanes } from '../lib/lanes'
import type { EarningsAlertsApi } from '../hooks/useCalendar'
import { EventRow } from './EventRow'
import { WeekViewLaneHeader as LaneHeader } from './laneHeader'

export interface DayBucket {
  iso: string
  isToday: boolean
  holidayName: string | null
  events: CalendarEvent[]
}

function DayColumn({
  day,
  index,
  alerts,
  signedIn,
  onShowMore,
}: {
  day: DayBucket
  index: number
  alerts: EarningsAlertsApi
  signedIn: boolean
  onShowMore: (iso: string) => void
}) {
  const { lanes, hidden } = groupIntoLanes(day.events)
  const empty = day.events.length === 0
  return (
    <section
      aria-label={formatLocalDate(day.iso, 'EEEE, MMMM d') + (day.holidayName ? ', market holiday' : `, ${day.events.length} ${day.events.length === 1 ? 'company' : 'companies'} reporting`)}
      className={cx('flex min-w-0 flex-col', index > 0 && 'border-l border-border-light/60 dark:border-white/[0.06]')}
    >
      <header
        className={cx(
          'flex items-center justify-between gap-1.5 border-b border-border-light/60 px-3 py-2.5 dark:border-white/[0.06]',
          day.isToday && 'shadow-[inset_0_2px_0_theme(colors.brand.DEFAULT)] dark:shadow-[inset_0_2px_0_theme(colors.brand.dark)]',
        )}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark">
            {formatLocalDate(day.iso, 'EEE')}
          </span>
          <span
            className={cx(
              'font-data text-sm font-semibold tabular-nums',
              day.isToday
                ? 'grid h-6 min-w-6 place-items-center rounded-full bg-brand px-1 text-xs text-white dark:bg-brand-dark dark:text-background-dark'
                : 'text-text-primary-light dark:text-text-primary-dark',
            )}
          >
            {formatLocalDate(day.iso, 'd')}
          </span>
        </div>
        {!day.holidayName && (
          <span className="font-data text-data-xs tabular-nums text-text-tertiary-light dark:text-text-secondary-dark" title="Companies reporting">
            {day.events.length}
          </span>
        )}
      </header>
      <div className="flex min-h-[150px] flex-1 flex-col px-2 pb-3 pt-1">
        {day.holidayName ? (
          <p className="m-auto px-2 py-4 text-center text-xs text-text-secondary-light dark:text-text-secondary-dark">
            <span className="font-semibold">Market closed</span>
            <span className="mt-0.5 block text-text-tertiary-light dark:text-text-secondary-dark">{day.holidayName}</span>
          </p>
        ) : empty ? (
          <p className="m-auto px-2 py-4 text-center text-xs text-text-tertiary-light dark:text-text-secondary-dark">No reports</p>
        ) : (
          <>
            {lanes.map((lane) => (
              <div key={lane.key}>
                <LaneHeader laneKey={lane.key} label={lane.label} dense />
                <ul className="flex list-none flex-col">
                  {lane.rows.map((ev) => (
                    <EventRow key={`${ev.ticker}-${ev.event_date}`} ev={ev} alerts={alerts} signedIn={signedIn} />
                  ))}
                </ul>
              </div>
            ))}
            {hidden > 0 && (
              <button
                type="button"
                onClick={() => onShowMore(day.iso)}
                className="mt-1.5 h-7 w-full rounded-lg text-xs font-semibold text-brand-strong transition-colors duration-fast hover:bg-brand-weak focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark"
              >
                +{hidden} more
              </button>
            )}
          </>
        )}
      </div>
    </section>
  )
}

function MobileDay({
  day,
  alerts,
  signedIn,
}: {
  day: DayBucket
  alerts: EarningsAlertsApi
  signedIn: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const { lanes, hidden } = groupIntoLanes(day.events, expanded ? 0 : undefined)
  return (
    <section
      aria-label={formatLocalDate(day.iso, 'EEEE, MMMM d')}
      className="overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border-light/60 px-4 py-3 dark:border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <span
            className={cx(
              'font-data text-sm font-semibold tabular-nums',
              day.isToday &&
                'grid h-6 min-w-6 place-items-center rounded-full bg-brand px-1 text-xs text-white dark:bg-brand-dark dark:text-background-dark',
            )}
          >
            {formatLocalDate(day.iso, 'd')}
          </span>
          <div>
            <h3 className="text-sm font-semibold">{formatLocalDate(day.iso, 'EEEE, MMMM d')}</h3>
            {day.holidayName && (
              <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">Market closed · {day.holidayName}</p>
            )}
          </div>
        </div>
        {!day.holidayName && (
          <span className="font-data text-xs tabular-nums text-text-tertiary-light dark:text-text-secondary-dark">
            {day.events.length}
          </span>
        )}
      </header>
      {day.holidayName || day.events.length === 0 ? (
        <p className="px-4 py-4 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          {day.holidayName ? `Market closed for ${day.holidayName}. No earnings are scheduled.` : 'No reports scheduled.'}
        </p>
      ) : (
        <div className="px-2 pb-2.5 pt-0.5">
          {lanes.map((lane) => (
            <div key={lane.key}>
              <LaneHeader laneKey={lane.key} label={lane.label} />
              <ul className="flex list-none flex-col">
                {lane.rows.map((ev) => (
                  <EventRow key={`${ev.ticker}-${ev.event_date}`} ev={ev} alerts={alerts} signedIn={signedIn} roomy />
                ))}
              </ul>
            </div>
          ))}
          {(hidden > 0 || expanded) && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-2 h-9 w-full rounded-lg border border-dashed border-brand-border text-sm font-semibold text-brand-strong transition-colors duration-fast hover:bg-brand-weak focus-visible:outline-none focus-visible:shadow-ring-brand dark:border-brand-border-dark dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              {expanded ? 'Show top 5' : `+${hidden} more`}
            </button>
          )}
        </div>
      )}
    </section>
  )
}

export function WeekView({
  days,
  alerts,
  signedIn,
  onShowMore,
}: {
  days: DayBucket[]
  alerts: EarningsAlertsApi
  signedIn: boolean
  onShowMore: (iso: string) => void
}) {
  return (
    <>
      {/* Desktop: one sheet, five weekday columns */}
      <div className="hidden overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2 motion-safe:animate-content-in dark:border-white/10 dark:bg-panel-dark dark:shadow-none md:block">
        <div className="grid grid-cols-5">
          {days.map((day, i) => (
            <DayColumn key={day.iso} day={day} index={i} alerts={alerts} signedIn={signedIn} onShowMore={onShowMore} />
          ))}
        </div>
      </div>
      {/* Mobile: vertical day-by-day list */}
      <div className="flex flex-col gap-3.5 motion-safe:animate-content-in md:hidden">
        {days.map((day) => (
          <MobileDay key={day.iso} day={day} alerts={alerts} signedIn={signedIn} />
        ))}
      </div>
    </>
  )
}

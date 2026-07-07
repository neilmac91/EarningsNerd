'use client'

/* =============================================================================
   DayDetailDialog (features/calendar/components/DayDetailDialog.tsx)
   -----------------------------------------------------------------------------
   The full, uncapped day: every company grouped into lanes with roomy rows.
   Native <dialog> + showModal() supplies the focus trap, Esc handling, and
   top-layer stacking; we add backdrop-click dismissal and focus restoration.
============================================================================= */

import { useEffect, useRef } from 'react'
import { XIcon, InfoIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { cx } from '@/components/ui/cx'
import type { CalendarEvent } from '../api/calendar-api'
import { groupIntoLanes } from '../lib/lanes'
import { marketHolidayName } from '../lib/dates'
import type { EarningsAlertsApi } from '../hooks/useCalendar'
import { EventRow } from './EventRow'
import { WeekViewLaneHeader } from './laneHeader'

export function DayDetailDialog({
  iso,
  events,
  alerts,
  signedIn,
  onClose,
}: {
  iso: string
  events: CalendarEvent[]
  alerts: EarningsAlertsApi
  signedIn: boolean
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const { lanes } = groupIntoLanes(events, 0)
  const holiday = marketHolidayName(iso)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (!dialog.open) dialog.showModal()
    const onCancel = (e: Event) => {
      e.preventDefault()
      onClose()
    }
    dialog.addEventListener('cancel', onCancel)
    return () => dialog.removeEventListener('cancel', onCancel)
  }, [onClose])

  return (
    <dialog
      ref={ref}
      aria-label={`Earnings on ${formatLocalDate(iso, 'EEEE, MMMM d')}`}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx(
        'w-[min(560px,calc(100vw-32px))] rounded-xl border border-border-light bg-panel-light p-0 text-text-primary-light shadow-e5',
        'backdrop:bg-background-dark/45 dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark',
        'motion-safe:animate-content-in',
      )}
    >
      <header className="flex items-start justify-between gap-3 border-b border-border-light px-5 py-4 dark:border-white/10">
        <div>
          <h2 className="text-lg font-semibold">{formatLocalDate(iso, 'EEEE, MMMM d')}</h2>
          <p className="mt-0.5 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            {holiday ? 'Market holiday' : `${events.length} ${events.length === 1 ? 'company reports' : 'companies report'}`} ·
            ranked by anticipation · U.S. Eastern
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="inline-flex h-8 w-8 flex-none items-center justify-center rounded-lg text-text-tertiary-light transition-colors duration-fast hover:bg-brand-weak hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </header>
      <div className="max-h-[min(60vh,560px)] overflow-y-auto px-3 pb-3 pt-1">
        {holiday && (
          <div
            role="status"
            className="mx-2 mt-2.5 flex items-center gap-2.5 rounded-lg border border-info-light/25 bg-info-light/[0.06] px-3.5 py-2.5 dark:border-info-dark/25 dark:bg-info-dark/10"
          >
            <InfoIcon aria-hidden="true" className="h-4 w-4 flex-none text-info-light dark:text-info-dark" />
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">Market closed</span> for {holiday}.
              No earnings are scheduled.
            </p>
          </div>
        )}
        {lanes.map((lane) => (
          <div key={lane.key}>
            <WeekViewLaneHeader laneKey={lane.key} label={lane.label} />
            <ul className="flex list-none flex-col">
              {lane.rows.map((ev) => (
                <EventRow key={`${ev.ticker}-${ev.event_date}`} ev={ev} alerts={alerts} signedIn={signedIn} roomy />
              ))}
            </ul>
          </div>
        ))}
      </div>
      <footer className="border-t border-border-light px-5 py-2.5 text-xs text-text-tertiary-light dark:border-white/10 dark:text-text-secondary-dark">
        Alert emails arrive the morning a company reports, U.S. Eastern.
      </footer>
    </dialog>
  )
}

'use client'

/* =============================================================================
   MonthView (features/calendar/components/MonthView.tsx)
   -----------------------------------------------------------------------------
   Seven-column month grid (Mon-first; weekend columns stay, muted — honest
   calendar shape). Cells are discovery surfaces: up to three top-anticipated
   tickers with their session glyph, "+N more", and a bell glyph on companies
   the user already subscribed to. The full day — lanes, EPS, bells — lives in
   the day dialog, opened by the cell.
============================================================================= */

import { cx } from '@/components/ui/cx'
import { ClockIcon, MoonIcon, SunIcon, BellIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import type { CalendarEvent } from '../api/calendar-api'
import { rankEvents, laneOf } from '../lib/lanes'
import { addDaysIso, isoDayOfWeek, marketHolidayName, mondayOf, firstOfMonth } from '../lib/dates'
import type { EarningsAlertsApi } from '../hooks/useCalendar'

const DOWS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const GLYPH = { bmo: SunIcon, amc: MoonIcon, other: ClockIcon } as const

export function MonthView({
  anchorIso,
  todayIso,
  eventsByDate,
  alerts,
  onOpenDay,
}: {
  anchorIso: string
  todayIso: string
  eventsByDate: Map<string, CalendarEvent[]>
  alerts: EarningsAlertsApi
  onOpenDay: (iso: string) => void
}) {
  const monthOf = (iso: string) => iso.slice(0, 7)
  const month = monthOf(anchorIso)
  const start = mondayOf(firstOfMonth(anchorIso))

  return (
    <div className="overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2 motion-safe:animate-content-in dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
      <div className="grid grid-cols-7 border-b border-border-light dark:border-white/10" aria-hidden="true">
        {DOWS.map((d, i) => (
          <div
            key={d}
            className={cx(
              'px-2.5 py-2 text-xs font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark',
              i > 0 && 'border-l border-border-light/60 dark:border-white/[0.06]',
            )}
          >
            {d}
          </div>
        ))}
      </div>
      {Array.from({ length: 6 }, (_, w) => (
        <div key={w} className="grid grid-cols-7 border-b border-border-light/60 last:border-b-0 dark:border-white/[0.06]">
          {Array.from({ length: 7 }, (_, i) => {
            const iso = addDaysIso(start, w * 7 + i)
            const inMonth = monthOf(iso) === month
            const ranked = rankEvents(eventsByDate.get(iso) ?? [])
            const holiday = inMonth ? marketHolidayName(iso) : null
            const isToday = iso === todayIso
            const weekend = isoDayOfWeek(iso) === 0 || isoDayOfWeek(iso) === 6
            const top = ranked.slice(0, 3)
            const openable = inMonth && (ranked.length > 0 || !!holiday)
            const label =
              formatLocalDate(iso, 'EEEE, MMMM d') +
              (holiday
                ? ', market holiday'
                : `, ${ranked.length} ${ranked.length === 1 ? 'company reports' : 'companies report'}`) +
              (top.length ? `: ${top.map((e) => e.ticker).join(', ')}${ranked.length > 3 ? ` and ${ranked.length - 3} more` : ''}` : '')
            return (
              <button
                key={iso}
                type="button"
                disabled={!openable}
                aria-label={label}
                onClick={() => onOpenDay(iso)}
                className={cx(
                  'flex min-h-24 flex-col items-start gap-1 px-2.5 py-2 text-left transition-colors duration-fast',
                  i > 0 && 'border-l border-border-light/60 dark:border-white/[0.06]',
                  openable && 'cursor-pointer hover:bg-white dark:hover:bg-white/5',
                  // Inset ring (the outer shadow-ring-brand would clip inside the sheet's
                  // overflow-hidden); rgba values mirror the ring-brand tokens exactly.
                  'focus-visible:outline-none focus-visible:shadow-[inset_0_0_0_3px_rgba(79,122,99,0.5)] dark:focus-visible:shadow-[inset_0_0_0_3px_rgba(127,178,149,0.55)]',
                  !inMonth && 'opacity-40',
                )}
              >
                <span className="flex w-full items-center justify-between">
                  <span
                    className={cx(
                      'font-data text-xs font-semibold tabular-nums',
                      isToday
                        ? 'grid h-[22px] min-w-[22px] place-items-center rounded-full bg-brand px-1 text-white dark:bg-brand-dark dark:text-background-dark'
                        : weekend || !inMonth
                          ? 'text-text-tertiary-light dark:text-text-secondary-dark'
                          : 'text-text-primary-light dark:text-text-primary-dark',
                    )}
                  >
                    {formatLocalDate(iso, 'd')}
                  </span>
                  {holiday && <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">Closed</span>}
                </span>
                {inMonth &&
                  top.map((ev) => {
                    const Icon = GLYPH[laneOf(ev)]
                    return (
                      <span key={`${ev.ticker}-${ev.event_date}`} className="flex w-full min-w-0 items-center gap-1.5">
                        <Icon aria-hidden="true" className="h-3 w-3 flex-none text-text-tertiary-light dark:text-text-secondary-dark" />
                        <span className="truncate font-data text-xs font-semibold tabular-nums text-text-secondary-light dark:text-text-primary-dark">
                          {ev.ticker}
                        </span>
                        {alerts.isOn(ev.ticker) && (
                          <BellIcon
                            weight="fill"
                            aria-hidden="true"
                            className="h-2.5 w-2.5 flex-none text-brand-strong dark:text-brand-strong-dark"
                          />
                        )}
                      </span>
                    )
                  })}
                {inMonth && ranked.length > 3 && (
                  <span className="text-xs font-semibold text-brand-strong dark:text-brand-strong-dark">
                    +{ranked.length - 3} more
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}

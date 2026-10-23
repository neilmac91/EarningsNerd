'use client'

/* =============================================================================
   MonthView (features/calendar/components/MonthView.tsx)
   -----------------------------------------------------------------------------
   Seven-column month grid (Mon-first; weekend columns stay, muted — honest
   calendar shape). Cells are discovery surfaces: up to three top-anticipated
   tickers with their session glyph, "+N more", and a bell glyph on companies
   the user already subscribed to. The full day — lanes, EPS, bells — lives in
   the day dialog, opened by the cell.
   A cell shows only what fits whole, never a clipped glyph: the sheet is an
   inline-size container, and its width in em (its own text size) picks what a
   day shows. From 42em (six em a day), as above; from 21em, the tickers and
   "+N more" alone; below that (a phone at 200% text, or a 360px one), each
   trading day's count of companies reporting, 0 included, under one-letter
   weekday heads, which a caption at the foot of the sheet says.
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
    <div className="overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2 motion-safe:animate-content-in [container-type:inline-size] dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
      <div className="grid grid-cols-7 border-b border-border-light dark:border-white/10" aria-hidden="true">
        {DOWS.map((d, i) => (
          <div
            key={d}
            className={cx(
              'px-2.5 py-2 text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark',
              '[@container(width<42em)]:px-1 [@container(width<21em)]:text-center',
              i > 0 && 'border-l border-border-light/60 dark:border-white/[0.06]',
            )}
          >
            <span className="[@container(width<21em)]:hidden">{d}</span>
            <span className="hidden [@container(width<21em)]:inline">{d.charAt(0)}</span>
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
                  'flex min-h-24 flex-col items-start gap-1 py-2 text-left transition-colors duration-fast',
                  // The sheet's width sets the padding, so nothing resets it to zero (button-icon-size-gate bans that
                  // reset app-wide): as before from 42em, less from 21em, none at the count, so a two-digit day and
                  // today's marker (sized below) fit whole.
                  '[@container(width>=42em)]:px-2.5 [@container(21em<=width<42em)]:px-1 [@container(width<21em)]:items-center',
                  i > 0 && 'border-l border-border-light/60 dark:border-white/[0.06]',
                  openable && 'cursor-pointer hover:bg-white dark:hover:bg-white/5',
                  // Inset ring (the outer shadow-ring-brand would clip inside the sheet's
                  // overflow-hidden); rgba values mirror the ring-brand tokens exactly.
                  'focus-visible:outline-none focus-visible:shadow-ring-brand-inset dark:focus-visible:shadow-ring-brand-inset-dark',
                  !inMonth && 'opacity-40',
                )}
              >
                <span className="flex w-full flex-wrap items-center justify-between gap-x-1 [@container(width<21em)]:justify-center">
                  <span
                    className={cx(
                      'font-data text-xs font-semibold tabular-nums',
                      // Today's marker is sized in rem, as the week header's is, so it grows with the digits it holds
                      // (22px at the default size, 44px at 200% text, where a 22px pill cut their lower half). Its
                      // least width is capped at its day's, so in the narrowest days it shrinks to the cell, and it
                      // needs no padding: two digits are 0.9rem wide, 29px of the 35px a day has on a 320px phone at
                      // 200% text.
                      isToday
                        ? 'grid h-[1.375rem] min-w-[min(1.375rem,100%)] place-items-center rounded-full bg-brand text-white dark:bg-brand-dark dark:text-background-dark'
                        : weekend || !inMonth
                          ? 'text-text-tertiary-light dark:text-text-secondary-dark'
                          : 'text-text-primary-light dark:text-text-primary-dark',
                      // Below 21em a holiday drops its "Closed", so its date takes the weekend's ink: in the primary
                      // ink, with no count under it, it would read as a trading day with no reports.
                      holiday &&
                        !isToday &&
                        '[@container(width<21em)]:text-text-tertiary-light dark:[@container(width<21em)]:text-text-secondary-dark',
                    )}
                  >
                    {formatLocalDate(iso, 'd')}
                  </span>
                  {holiday && (
                    <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark [@container(width<21em)]:hidden">Closed</span>
                  )}
                </span>
                {inMonth &&
                  top.map((ev) => {
                    const Icon = GLYPH[laneOf(ev)]
                    return (
                      <span
                        key={`${ev.ticker}-${ev.event_date}`}
                        className="flex w-full min-w-0 items-center gap-1.5 [@container(width<21em)]:hidden"
                      >
                        <Icon
                          aria-hidden="true"
                          className="h-3 w-3 flex-none text-text-tertiary-light dark:text-text-secondary-dark [@container(width<42em)]:hidden"
                        />
                        <span className="truncate font-data text-xs font-semibold tabular-nums text-text-secondary-light dark:text-text-primary-dark">
                          {ev.ticker}
                        </span>
                        {alerts.isOn(ev.ticker) && (
                          <BellIcon
                            weight="fill"
                            aria-hidden="true"
                            className="h-2.5 w-2.5 flex-none text-brand-strong dark:text-brand-strong-dark [@container(width<42em)]:hidden"
                          />
                        )}
                      </span>
                    )
                  })}
                {inMonth && ranked.length > 3 && (
                  <span className="text-xs font-semibold text-text-secondary-light dark:text-text-secondary-dark [@container(width<21em)]:hidden">
                    +{ranked.length - 3} more
                  </span>
                )}
                {/* A trading day shows its count, 0 included, as the week sheet's day header does; a weekend or a
                    holiday keeps its date alone, so in this density a muted date always means the market is closed. */}
                {inMonth && (ranked.length > 0 || (!weekend && !holiday)) && (
                  <span className="hidden font-data text-xs tabular-nums text-text-tertiary-light dark:text-text-secondary-dark [@container(width<21em)]:block">
                    {ranked.length}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ))}
      <p className="hidden border-t border-border-light/60 px-3 py-2 text-xs text-text-tertiary-light dark:border-white/[0.06] dark:text-text-secondary-dark [@container(width<21em)]:block">
        Each trading day shows how many companies report. Open a day to see them.
      </p>
    </div>
  )
}

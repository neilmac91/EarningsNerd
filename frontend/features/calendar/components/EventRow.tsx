'use client'

/* =============================================================================
   EventRow + StatusChip + EpsFigure (features/calendar/components/EventRow.tsx)
   -----------------------------------------------------------------------------
   One company on one day. Anatomy per spec: CompanyLogo · ticker (mono +
   tabular) · company name · EPS estimate (or actual + direction once
   reported) · status chip · alert bell. The whole left region links to
   /company/[ticker]; the bell is a sibling so the link stays a link.
   Every line wraps and none truncates: the company name in full, and an
   estimated row's habitual-slot note ("usually before open") on a line of its
   own after the lane's glyph, in both row kinds, since the page's footer
   explains "usually" (a hover title alone showed it to nobody). A roomy row is
   an inline-size container: narrower than 16em of its own text (a phone at
   200% text), it drops the decorative logo and stacks, the bell beside the
   ticker alone and the chip, name, note and EPS full width under it, so no
   column squeezes another into it and no chip runs under the bell.
============================================================================= */

import Link from 'next/link'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, type BadgeStatusVariant } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import { fmtCurrency } from '@/lib/format'
import { formatCompanyName } from '@/lib/formatCompanyName'
import type { CalendarEvent } from '../api/calendar-api'
import { habitualSlotNote, laneOf } from '../lib/lanes'
import type { EarningsAlertsApi } from '../hooks/useCalendar'
import { AlertBell } from './AlertBell'
import { LANE_ICON } from './laneHeader'

/** The status ladder, on Badge's status set (DESIGN_SYSTEM.md §4, Status chip; E141): not yet settled, firm and
    upcoming, over. A status, so TypeScript refuses a tint here, as in the admin badges' configs. */
const LADDER: Record<CalendarEvent['status'], { label: string; variant: BadgeStatusVariant }> = {
  // Tentative by design: Badge's dashed hairline with no fill in either theme (E83).
  estimated: { label: 'Est.', variant: 'tentative' },
  // A firm, upcoming date, and the rung a reader scans for: not success, whose light ink is gain.text's hex, the
  // ink a reported row's beat prints in.
  confirmed: { label: 'Confirmed', variant: 'info-status' },
  // The event is over, and its EPS figure carries the news.
  reported: { label: 'Reported', variant: 'neutral-status' },
}

export function StatusChip({ status }: { status: CalendarEvent['status'] }) {
  // A status the ladder does not know reads "Est.", a name on Object.prototype included.
  const { label, variant } = Object.hasOwn(LADDER, status) ? LADDER[status] : LADDER.estimated
  return <Badge variant={variant}>{label}</Badge>
}

/** Mono/tabular EPS: estimate before the event, actual + calm direction after.
    Delta TEXT uses the 700-level gain/loss text tokens (DESIGN_SYSTEM §1). */
export function EpsFigure({ ev, roomy = false, className }: { ev: CalendarEvent; roomy?: boolean; className?: string }) {
  const mono = 'font-data tabular-nums whitespace-nowrap'
  if (ev.status === 'reported' && ev.eps_actual !== null && ev.eps_estimate !== null) {
    const beat = ev.eps_actual >= ev.eps_estimate
    return (
      <span className={cx('text-right', className)}>
        <span
          className={cx(
            mono,
            'font-semibold',
            roomy ? 'text-sm' : 'text-data-xs',
            beat ? 'text-gain-text dark:text-gain-dark' : 'text-loss-text dark:text-loss-dark',
          )}
        >
          {fmtCurrency(ev.eps_actual, { digits: 2, compact: false })} {beat ? '▲' : '▼'}
        </span>
        {roomy && (
          <span className={cx(mono, 'mt-0.5 block text-data-xs text-text-tertiary-light dark:text-text-secondary-dark')}>
            vs {fmtCurrency(ev.eps_estimate, { digits: 2, compact: false })} est
          </span>
        )}
      </span>
    )
  }
  if (ev.eps_estimate === null) return null
  return (
    <span className={cx(mono, roomy ? 'text-xs' : 'text-data-xs', 'text-text-tertiary-light dark:text-text-secondary-dark', className)}>
      Est {fmtCurrency(ev.eps_estimate, { digits: 2, compact: false })}
    </span>
  )
}

/** An estimated row's habitual-slot note: the lane's glyph, then the words, on a line of their own that
    wraps. Never an ellipsis and never only a hover title: the page's footer explains "usually". */
function SlotNote({ ev, note, className }: { ev: CalendarEvent; note: string; className?: string }) {
  const Icon = LANE_ICON[laneOf(ev)]
  return (
    <span className={cx('flex items-start gap-1 text-xs text-text-tertiary-light dark:text-text-secondary-dark', className)}>
      <Icon aria-hidden="true" className="mt-0.5 h-3 w-3 flex-none" />
      <span className="min-w-0 break-words">{note}</span>
    </span>
  )
}

export function EventRow({
  ev,
  alerts,
  signedIn,
  roomy = false,
}: {
  ev: CalendarEvent
  alerts: EarningsAlertsApi
  signedIn: boolean
  /** roomy = mobile list & day dialog; compact = desktop week cells. */
  roomy?: boolean
}) {
  const note = habitualSlotNote(ev)
  // The name in its display casing, as Reporting this week prints it (EDGAR serves the conformed name, often in
  // capitals), for the line and for the mark.
  const name = formatCompanyName(ev.company_name)
  return (
    <li
      className={cx(
        'group relative rounded-lg transition-colors duration-fast hover:bg-white dark:hover:bg-white/5',
        roomy && '[container-type:inline-size]',
      )}
    >
      <Link
        href={`/company/${ev.ticker}`}
        className={cx(
          'block rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
          roomy
            ? 'flex min-h-[52px] flex-wrap items-center justify-end gap-x-3 gap-y-1 py-2 pl-2 pr-14 [@container(width<16em)]:justify-start [@container(width<16em)]:pr-2'
            : 'py-1 pl-1 pr-8',
        )}
      >
        {roomy ? (
          <>
            <CompanyLogo decorative ticker={ev.ticker} name={name} size={30} className="[@container(width<16em)]:hidden" />
            {/* 8rem at least beside the EPS, which wraps under it (to the right) on a narrow phone. */}
            <span className="min-w-0 flex-[1_1_8rem] [@container(width<16em)]:basis-full">
              {/* Stacked, the ticker alone keeps the bell's column and height (a line of its own, centred on the
                  bell), so the chip and the lines under it run full width: a chip beside the ticker would run
                  under the bell once the row is narrower than the ticker, the chip and that column. */}
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="flex items-center font-data text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark [@container(width<16em)]:min-h-11 [@container(width<16em)]:basis-full [@container(width<16em)]:pr-12">
                  {ev.ticker}
                </span>
                <StatusChip status={ev.status} />
              </span>
              <span className="mt-0.5 block break-words text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                {name}
              </span>
              {note && <SlotNote ev={ev} note={note} className="mt-0.5" />}
            </span>
            <EpsFigure ev={ev} roomy className="[@container(width<16em)]:text-left" />
          </>
        ) : (
          <>
            <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
              <CompanyLogo decorative ticker={ev.ticker} name={name} size={20} />
              <span className="font-data text-xs font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                {ev.ticker}
              </span>
              <StatusChip status={ev.status} />
            </span>
            {/* Indented to the ticker (the 20px logo and its gap); the EPS wraps under a name that needs the line. */}
            <span className="mt-px flex flex-wrap items-baseline justify-end gap-x-1.5 pl-[calc(20px_+_0.375rem)]">
              {/* No narrower than its longest word unless the line is (max-w-full caps that floor): the EPS
                  wraps first, and a word breaks only when it is wider than the whole line. */}
              <span className="max-w-full flex-[1_1_5rem] break-words text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                {name}
              </span>
              <EpsFigure ev={ev} />
            </span>
            {note && <SlotNote ev={ev} note={note} className="mt-px pl-[calc(20px_+_0.375rem)]" />}
          </>
        )}
      </Link>
      <AlertBell
        ticker={ev.ticker}
        alerts={alerts}
        signedIn={signedIn}
        size={roomy ? 'lg' : 'sm'}
        className={cx(
          'absolute top-1/2 -translate-y-1/2',
          roomy ? 'right-2 [@container(width<16em)]:top-2 [@container(width<16em)]:translate-y-0' : 'right-0.5',
        )}
      />
    </li>
  )
}

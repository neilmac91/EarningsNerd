'use client'

/* =============================================================================
   EventRow + StatusChip + EpsFigure (features/calendar/components/EventRow.tsx)
   -----------------------------------------------------------------------------
   One company on one day. Anatomy per spec: CompanyLogo · ticker (mono +
   tabular) · company name · EPS estimate (or actual + direction once
   reported) · status chip · alert bell. The whole left region links to
   /company/[ticker]; the bell is a sibling so the link stays a link.
============================================================================= */

import Link from 'next/link'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import { FlameIcon } from '@/lib/icons'
import { fmtCurrency } from '@/lib/format'
import type { CalendarEvent } from '../api/calendar-api'
import { habitualSlotNote } from '../lib/lanes'
import type { EarningsAlertsApi } from '../hooks/useCalendar'
import { AlertBell } from './AlertBell'

export function StatusChip({ status }: { status: CalendarEvent['status'] }) {
  if (status === 'reported') return <Badge variant="neutral">Reported</Badge>
  if (status === 'confirmed') return <Badge variant="brand">Confirmed</Badge>
  return (
    <Badge
      variant="neutral"
      className="border-dashed bg-transparent text-text-tertiary-light dark:bg-transparent dark:text-text-secondary-dark"
    >
      Est.
    </Badge>
  )
}

/** Mono/tabular EPS: estimate before the event, actual + calm direction after.
    Delta TEXT uses the 700-level gain/loss text tokens (DESIGN_SYSTEM §1). */
export function EpsFigure({ ev, roomy = false }: { ev: CalendarEvent; roomy?: boolean }) {
  const mono = 'font-data tabular-nums whitespace-nowrap'
  if (ev.status === 'reported' && ev.eps_actual !== null && ev.eps_estimate !== null) {
    const beat = ev.eps_actual >= ev.eps_estimate
    return (
      <span className="text-right">
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
    <span className={cx(mono, roomy ? 'text-xs' : 'text-data-xs', 'text-text-tertiary-light dark:text-text-secondary-dark')}>
      Est {fmtCurrency(ev.eps_estimate, { digits: 2, compact: false })}
    </span>
  )
}

const ANTICIPATION_FLAME_THRESHOLD = 93

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
  return (
    <li className="group relative rounded-lg transition-colors duration-fast hover:bg-white dark:hover:bg-white/5">
      <Link
        href={`/company/${ev.ticker}`}
        className={cx(
          'block rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
          roomy ? 'flex min-h-[52px] items-center gap-3 py-2 pl-2 pr-14' : 'py-1 pl-1 pr-8',
        )}
      >
        {roomy ? (
          <>
            <CompanyLogo ticker={ev.ticker} name={ev.company_name} size={30} />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span className="font-data text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                  {ev.ticker}
                </span>
                <StatusChip status={ev.status} />
                {ev.anticipation_score >= ANTICIPATION_FLAME_THRESHOLD && (
                  <FlameIcon
                    aria-label="Highly anticipated"
                    className="h-3.5 w-3.5 text-warning-light dark:text-warning-dark"
                  />
                )}
              </span>
              <span className="mt-0.5 block truncate text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                {ev.company_name}
                {note ? ` · ${note}` : ''}
              </span>
            </span>
            <EpsFigure ev={ev} roomy />
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5">
              <CompanyLogo ticker={ev.ticker} name={ev.company_name} size={20} />
              <span className="font-data text-xs font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                {ev.ticker}
              </span>
              {ev.anticipation_score >= ANTICIPATION_FLAME_THRESHOLD && (
                <FlameIcon aria-label="Highly anticipated" className="h-3 w-3 text-warning-light dark:text-warning-dark" />
              )}
              <StatusChip status={ev.status} />
            </span>
            <span className="mt-px flex items-baseline gap-1.5 pl-[26px]" title={note ?? undefined}>
              <span className="min-w-0 flex-1 truncate text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                {ev.company_name}
              </span>
              <EpsFigure ev={ev} />
            </span>
          </>
        )}
      </Link>
      <AlertBell
        ticker={ev.ticker}
        alerts={alerts}
        signedIn={signedIn}
        size={roomy ? 'lg' : 'sm'}
        className={cx('absolute top-1/2 -translate-y-1/2', roomy ? 'right-2' : 'right-0.5')}
      />
    </li>
  )
}

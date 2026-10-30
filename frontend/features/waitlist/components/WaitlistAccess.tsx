'use client'

import Link from 'next/link'
import { cx } from '@/components/ui/cx'
import { usePublicAccess, usePublicReadiness } from '@/features/marketing/components/PublicAccessProvider'
import WaitlistCounter from './WaitlistCounter'
import WaitlistPill, { PILL_LABEL } from './WaitlistPill'

const LINE = 'text-sm text-text-secondary-light dark:text-text-secondary-dark'
const CELL = 'col-start-1 row-start-1'

/** The status's sentence while registration readiness checks. Above the form it stands alone, so it keeps the second
 *  sentence the hero's shorter checking line leaves to its button (CHECKING_LINE, E224), and its rows hold the status as
 *  tall as a landed count's pill: at about 330 to 390px under 200% text "Join 1,234+ others" takes a line more than
 *  "Join the waitlist" (E225), and with the hero's line in this cell a landing count would grow the status 34 to 40px
 *  there (E224's measure, in CI's fonts). */
export const CHECKING_STATUS = 'Checking registration availability. You can explore a live example.'

/**
 * The status above the waitlist form: its checking sentence while registration readiness checks, the counter's pill once
 * it answers open, and the closed or unconfirmed line otherwise. The checking sentence and the pill (on PILL_LABEL, as the
 * counter opens) share one grid cell, the shown one visible and the other invisible and aria-hidden, so the status keeps
 * one height as readiness answers open and the form under it holds still: as the line became the pill, in CI's fonts,
 * the form moved 18px down from 470 to 1440px and 2px up below, and under 200% text 6 to 86px up, or 34px down at
 * 900 to 1000px and from 1760px (E222, chief design on #1686, comment 6433704320). items-center keeps the shown one
 * central where the other is taller. The held pill is static: the counter loads its stats only once readiness answers
 * open. A closed or unconfirmed answer joins the cell when shown and can still grow it, as on the hero's access line.
 */
export function WaitlistAccessStatus() {
  const { readiness, loading } = usePublicReadiness()
  const access = usePublicAccess('invite')
  const open = readiness?.collection_available === true
  return (
    <div className="grid items-center justify-items-center lg:justify-items-start">
      {open ? <WaitlistCounter className={CELL} /> : <p className={cx(LINE, CELL)}>{loading ? CHECKING_STATUS : access.line}</p>}
      {!loading && (
        <p aria-hidden="true" className={cx(LINE, 'invisible', CELL)}>
          {CHECKING_STATUS}
        </p>
      )}
      {!open && (
        <WaitlistPill aria-hidden="true" className={cx('invisible', CELL)}>
          <span>{PILL_LABEL}</span>
        </WaitlistPill>
      )}
    </div>
  )
}

export function WaitlistEntryLink({ className }: { className: string }) {
  const { readiness } = usePublicReadiness()
  const access = usePublicAccess('invite')
  const available = readiness?.collection_available === true
  return (
    <Link
      href={available ? '#waitlist' : access.href}
      className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', className)}
    >
      {available ? 'Join the waitlist' : access.cta}
    </Link>
  )
}

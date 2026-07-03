'use client'

/* =============================================================================
   AlertBell + BellPopover (features/calendar/components/AlertBell.tsx)
   -----------------------------------------------------------------------------
   The per-company earnings-alert toggle. Everyone sees the bell:
     - signed-out  → popover prompting sign-in
     - free at cap → upsell popover (deliberate conversion surface, §3.7)
     - pro at cap  → the API's terse 403 message, verbatim, no upsell
   aria-pressed carries the on/off state; the popover is a real dialog with
   focus management, Esc, and outside-click dismissal.
============================================================================= */

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { BellIcon, LockSimpleIcon, WarningCircleIcon } from '@/lib/icons'
import { Button, buttonVariants } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import type { BlockedState, EarningsAlertsApi } from '../hooks/useCalendar'

export function AlertBell({
  ticker,
  alerts,
  signedIn,
  size = 'sm',
  className,
}: {
  ticker: string
  alerts: EarningsAlertsApi
  signedIn: boolean
  /** sm = 28px (dense desktop cells) · lg = 44px (mobile / dialog rows). */
  size?: 'sm' | 'lg'
  className?: string
}) {
  const on = alerts.isOn(ticker)
  const pending = alerts.isPending(ticker)
  const label = !signedIn
    ? `Sign in to get earnings alerts for ${ticker}`
    : on
      ? `Turn off earnings alerts for ${ticker}`
      : `Get an email the morning ${ticker} reports`
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={label}
      title={label}
      disabled={pending}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        alerts.toggle(ticker, e.currentTarget)
      }}
      className={cx(
        'inline-flex flex-none items-center justify-center rounded-lg transition-colors duration-fast',
        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
        size === 'sm' ? 'h-7 w-7' : 'h-11 w-11',
        on
          ? 'bg-brand-weak text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark'
          : 'text-text-tertiary-light hover:bg-brand-weak hover:text-brand-strong dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark',
        pending ? 'cursor-progress opacity-60' : '',
        className,
      )}
    >
      <BellIcon weight={on ? 'fill' : 'regular'} className={size === 'sm' ? 'h-4 w-4' : 'h-[18px] w-[18px]'} />
    </button>
  )
}

/** One popover per page, anchored to the bell that raised `blocked`. */
export function BellPopover({ blocked, onClose }: { blocked: BlockedState; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const first = ref.current?.querySelector<HTMLElement>('a, button')
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
        blocked.trigger?.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [blocked, onClose])

  const W = 300
  const margin = 12
  const left = Math.max(margin, Math.min(blocked.anchor.left + blocked.anchor.width / 2 - W / 2, window.innerWidth - W - margin))
  const below = blocked.anchor.bottom + 8
  const top = below + 190 > window.innerHeight ? Math.max(margin, blocked.anchor.top - 178) : below

  const isError = blocked.kind === 'error'
  const title = isError
    ? 'Alert not enabled'
    : blocked.kind === 'signin'
      ? 'Sign in to set earnings alerts'
      : 'Free includes 3 earnings alerts'
  const body = isError
    ? blocked.message // the API's message, verbatim — never rewritten client-side
    : blocked.kind === 'signin'
      ? 'Day-of email alerts for companies you follow are free once you sign in.'
      : blocked.message

  return createPortal(
    <div className="fixed inset-0 z-50" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role={isError ? 'alertdialog' : 'dialog'}
        aria-label={title}
        style={{ left, top, width: W }}
        className="fixed rounded-lg border border-border-light bg-panel-light p-4 shadow-e4 dark:border-white/10 dark:bg-panel-dark"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className={cx(
              'flex h-8 w-8 flex-none items-center justify-center rounded-full border',
              isError
                ? 'border-error-light/25 bg-error-light/10 text-error-light dark:border-error-dark/25 dark:bg-error-dark/10 dark:text-error-dark'
                : 'border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
            )}
          >
            {isError ? (
              <WarningCircleIcon className="h-4 w-4" />
            ) : blocked.kind === 'signin' ? (
              <LockSimpleIcon className="h-4 w-4" />
            ) : (
              <BellIcon className="h-4 w-4" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{title}</p>
            <p className="mt-0.5 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{body}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {blocked.kind === 'upsell' && (
                <>
                  <Link href="/pricing" className={buttonVariants({ variant: 'primary', size: 'sm' })}>
                    Upgrade to Pro
                  </Link>
                  <Button variant="ghost" size="sm" onClick={onClose}>
                    Not now
                  </Button>
                </>
              )}
              {blocked.kind === 'signin' && (
                <>
                  <Link href="/login" className={buttonVariants({ variant: 'primary', size: 'sm' })}>
                    Sign in
                  </Link>
                  <Link href="/register" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
                    Create account
                  </Link>
                </>
              )}
              {isError && (
                <Button variant="secondary" size="sm" onClick={onClose}>
                  Dismiss
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

'use client'

/* =============================================================================
   AlertBell + BellPopover (features/calendar/components/AlertBell.tsx)
   -----------------------------------------------------------------------------
   The per-company earnings-alert toggle. Everyone sees the bell:
     - signed-out  → popover prompting sign-in
     - free at cap → upsell popover (deliberate conversion surface, §3.7)
     - pro at cap  → the API's terse 403 message, verbatim, no upsell
   aria-pressed carries the on/off state.

   BellPopover is a NON-MODAL popover, not a dialog (DESIGN_SYSTEM §4 Stacking:
   z-overlay). It explains one control, anchored to it, and dismisses lightly:
   nothing behind it is made inert, Tab is not trapped and the page does not
   lock. Modal semantics (a dialog role plus a trap, or ui/Modal's centred scrim)
   would claim an interruption it does not make, and ui/Modal portals to <body>,
   where a bell inside DayDetailDialog's native top layer could not reach it.
   So it carries no dialog role: a group named by its title and described by
   its message (the async error kind is announced as an alert instead), with
   the popover keyboard contract —
     - focus moves to the first action on open, unless the user already moved
       it elsewhere while a request was pending; the effect arms ONCE per popover
       (onClose read through a ref — the page hands a new one every render);
     - Escape closes (window capture + preventDefault, so a native <dialog>
       beneath does not close on the same key);
     - Tab past the last action or Shift+Tab before the first closes it and
       resumes the page's order at the bell, as a native popover's would;
     - scrolling or resizing closes it (fixed at the bell's rect, it would
       detach), as CitationChip's popover does;
     - every close returns focus to the bell unless the user moved it on.
   The transparent click-catcher stays: an outside press closes only the
   popover, so it cannot also close the day dialog through its backdrop or
   re-toggle the bell that raised it.
   While a native <dialog> is open it portals into that dialog, sharing its top
   layer instead of rendering inert beneath it.
============================================================================= */

import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { BellIcon, LockSimpleIcon, WarningCircleIcon } from '@/lib/icons'
import { Button, buttonVariants } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import type { BlockedState, EarningsAlertsApi } from '../hooks/useCalendar'
import { FREE_EARNINGS_ALERT_LIMIT } from '@/lib/planLimits'

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
  const checking = alerts.identityPending
  const label = checking
    ? `Checking your account before managing alerts for ${ticker}`
    : !signedIn
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
      // While its own toggle is in flight the bell is aria-disabled, not natively disabled: a focused
      // button that turns `disabled` is blurred to <body> (Chromium), so every keyboard toggle sent the
      // user back to the top of the page. `checking` stays native — it only holds before identity
      // resolves, when the bell cannot have focus yet.
      disabled={checking}
      aria-disabled={pending || undefined}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        if (pending) return
        alerts.toggle(ticker, e.currentTarget)
      }}
      className={cx(
        'inline-flex flex-none items-center justify-center rounded-lg transition-colors duration-fast',
        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
        size === 'sm' ? 'h-7 w-7' : 'h-11 w-11',
        on
          ? 'bg-brand-weak text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark'
          : 'text-text-tertiary-light hover:bg-brand-weak hover:text-brand-strong dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark',
        pending || checking ? 'cursor-progress opacity-60' : '',
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
  const titleId = useId()
  const bodyId = useId()
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const popover = ref.current
    const trigger = blocked.trigger
    // Focus is "free" when nobody else claimed it: an async result must not yank a user who moved on
    // (the error kind's alert announces it instead). A pending bell is disabled, so it blurred to <body>.
    const free = (el: Element | null) => !el || el === document.body || el === trigger || !!popover?.contains(el)
    const actions = () => Array.from(popover?.querySelectorAll<HTMLElement>('a[href], button') ?? [])
    if (free(document.activeElement)) actions()[0]?.focus({ preventScroll: true })

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab' || !trigger) return
      const items = actions()
      const active = document.activeElement
      // The panel itself takes focus when its text is clicked; Shift+Tab from there leaves too.
      const leaving = e.shiftKey ? active === items[0] || active === popover : active === items[items.length - 1]
      if (!leaving) return
      // Leaving the popover: Shift+Tab lands on the bell; Tab focuses the bell and lets the
      // browser's own Tab move past it, so the page's order resumes where the user was.
      e.stopPropagation()
      if (e.shiftKey) e.preventDefault()
      trigger.focus()
      onCloseRef.current()
    }
    // Fixed at the bell's rect, the popover would detach from it on scroll or resize (a wheel goes
    // straight through the catcher), so it closes, as CitationChip's does. Scroll does not bubble:
    // capture catches any scroller, the day dialog's list included; the popover's own is exempt.
    const onMove = (e: Event) => {
      if (e.type === 'scroll' && e.target instanceof Node && popover?.contains(e.target)) return
      onCloseRef.current()
    }
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('resize', onMove, { passive: true })
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('resize', onMove)
      // Escape, Not now / Dismiss, the outside click and a scroll all land here with focus gone from
      // the (unmounted) popover; send it back to the bell without scrolling the page to it. A Tab
      // out already moved it on, and a user who moved on keeps their place.
      if (trigger?.isConnected && free(document.activeElement)) trigger.focus({ preventScroll: true })
    }
  }, [blocked])

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
      : `Free includes ${FREE_EARNINGS_ALERT_LIMIT} earnings alerts`
  const body = isError
    ? blocked.message // the API's message, verbatim — never rewritten client-side
    : blocked.kind === 'signin'
      ? 'Day-of email alerts for companies you follow are free once you sign in.'
      : blocked.message

  return createPortal(
    <div className="fixed inset-0 z-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role="group"
        aria-labelledby={titleId}
        // The error is announced by its alert below; describing the group too would read it twice.
        aria-describedby={isError ? undefined : bodyId}
        tabIndex={-1}
        style={{ left, top, width: W }}
        className="fixed rounded-lg outline-none border border-border-light bg-panel-light p-4 shadow-e4 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
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
            {/* A failed toggle lands asynchronously, so it is announced as an alert. */}
            <div role={isError ? 'alert' : undefined}>
              <p id={titleId} className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                {title}
              </p>
              <p id={bodyId} className="mt-0.5 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
                {body}
              </p>
            </div>
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
    // While a native <dialog> is open (DayDetailDialog) the popover renders inside it: the top layer
    // would otherwise paint over a <body> portal and make it inert. That includes a failed toggle
    // whose error arrives after the user opened a day, from a bell outside the dialog.
    document.querySelector('dialog[open]') ?? document.body,
  )
}

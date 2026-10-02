'use client'

/* =============================================================================
   Modal — components/ui/Modal.tsx  (v3, DS-04)
   -----------------------------------------------------------------------------
   The ONE dialog primitive. Replaces the hand-rolled shells (UpgradeModal,
   EmailVerificationModal, Resend/RevokeShareModal, FeedbackWidget dialog,
   CookieConsent settings). The copilot rail / filing-viewer SHEETS keep their
   bespoke pane behavior (already focus-trapped) and only adopt the z/scrim
   tokens; the calendar's DayDetailDialog stays a native <dialog> + showModal()
   (only its scrim token changed) — never raise a Modal from inside it.

   Contract (all non-negotiable):
     - portal to <body>; scrim = bg-overlay z-modal + backdrop-blur-sm
     - panel = the Card recipe at the featured radius (rounded-2xl, panel fill,
       hairline, shadow-e5 light / shadow:none dark), entrance animate-fadeIn
       (globals reduce-guards it); the panel never outgrows the viewport — it
       stops at the scrim's inset and scrolls inside, so on a short or zoomed
       screen the ✕ and the actions stay reachable (the body is locked, so
       nothing else scrolls), and a control scrolled in by focus lands its
       ring clear of the edge (scroll padding = the panel's p-6 inset).
       Callers never size its height.
     - focus: moves into the panel on open (initialFocusRef ?? first focusable
       ?? the panel), Tab/Shift-Tab cycle inside, Escape closes (when
       dismissible), focus RETURNS to the opener on close; the trap arms once
       per open (onClose is read through a ref — inline callbacks are fine);
       the TOP open dialog owns Tab/Escape — its listener runs in window
       capture, ahead of any document-level trap beneath it (the copilot
       sheet), and stops them there — so content inside a panel cannot handle
       Tab/Escape itself
     - body scroll locked while any dialog is open (the stack holds the lock,
       so a lower layer closing first neither unlocks the page nor moves
       focus); scrim click closes unless dismissible={false}
     - a11y: role="dialog" aria-modal="true" + ariaLabel OR labelledBy pointing
       at the ModalHeader's id
   Compose: <Modal><ModalHeader/><ModalBody/><ModalFooter/></Modal>. Footer
   actions are <Button>s (they carry hover/active/focus/loading) — full-width
   stacked on mobile via className="w-full sm:w-auto".
============================================================================= */

import { useEffect, useRef, type HTMLAttributes, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { cx } from './cx'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

const SIZE = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg' } as const

// Open dialogs, innermost last. Only the top one answers Tab/Escape, so a dialog opened over another
// dialog or over a trapped sheet never lets a key reach the layer beneath it. The stack, not each
// dialog, also owns the body scroll lock and focus return: a lower layer that closes first must not
// unlock the page or pull focus out from under the dialog still open above it.
const openStack: object[] = []
let overflowBeforeLock = ''

export interface ModalProps {
  open: boolean
  onClose: () => void
  /** Accessible name — pass labelledBy (the ModalHeader id) or ariaLabel. */
  labelledBy?: string
  ariaLabel?: string
  size?: keyof typeof SIZE
  /** false = Escape/scrim-click don't close (confirm-or-act flows). Default true. */
  dismissible?: boolean
  /** Receives focus on open; defaults to the first focusable, else the panel. */
  initialFocusRef?: RefObject<HTMLElement | null>
  className?: string
  children: ReactNode
}

export function Modal({
  open,
  onClose,
  labelledBy,
  ariaLabel,
  size = 'md',
  dismissible = true,
  initialFocusRef,
  className,
  children,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  // The trap arms ONCE per open. onClose is read through a ref so a parent that re-renders while
  // the dialog is up (an inline arrow, a cooldown tick) cannot re-run the effect — which would
  // fire the focus-return cleanup, re-capture an element INSIDE the panel as the "opener", and
  // yank focus back to the first focusable every render (measured on the admin invite row).
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const layer = {}
    if (openStack.length === 0) {
      overflowBeforeLock = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
    openStack.push(layer)
    openerRef.current = document.activeElement as HTMLElement | null
    const panel = panelRef.current
    const target =
      initialFocusRef?.current ?? panel?.querySelector<HTMLElement>(FOCUSABLE) ?? panel
    target?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (openStack[openStack.length - 1] !== layer) return
      if (e.key === 'Escape') {
        // Stopped even when not dismissible: the layer beneath must not close instead.
        e.stopPropagation()
        if (dismissible) onCloseRef.current()
        return
      }
      if (e.key !== 'Tab' || !panel) return
      e.stopPropagation()
      // Cycle inside the panel — rendered (visible) focusables only.
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (n) => n.getClientRects().length > 0,
      )
      if (nodes.length === 0) {
        e.preventDefault()
        panel.focus()
        return
      }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const active = document.activeElement
      const inside = active instanceof Node && panel.contains(active)
      if (e.shiftKey && (!inside || active === first || active === panel)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (!inside || active === last)) {
        e.preventDefault()
        first.focus()
      }
    }

    // Window capture runs before every document-level listener, including a trap that armed first.
    window.addEventListener('keydown', onKeyDown, true)
    return () => {
      window.removeEventListener('keydown', onKeyDown, true)
      const wasTop = openStack[openStack.length - 1] === layer
      openStack.splice(openStack.indexOf(layer), 1)
      if (openStack.length === 0) document.body.style.overflow = overflowBeforeLock
      // Return focus to whatever opened the modal (it may have unmounted — optional chain), but only
      // when this was the top layer: a lower one closing leaves focus with the dialog above it.
      if (wasTop) openerRef.current?.focus?.()
    }
  }, [open, dismissible, initialFocusRef])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div
      className="fixed inset-0 z-modal flex items-center justify-center bg-overlay p-4 backdrop-blur-sm"
      onClick={dismissible ? onClose : undefined}
    >
      <div
        ref={panelRef}
        role="dialog"
        data-ui-modal="true"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={cx(
          'relative max-h-full w-full animate-fadeIn overflow-y-auto scroll-py-6 rounded-2xl border border-border-light bg-panel-light shadow-e5 outline-none',
          'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
          SIZE[size],
          className,
        )}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}

/* ------------------------------------------------------------- subparts -- */

// The icon tile speaks the dialog's state, as GuidanceCard's does: brand for a neutral prompt, the
// status hue for a state glyph — brand never signals a state (DESIGN_SYSTEM §1).
const ICON_TONE = {
  brand: cx(
    'border-brand-border bg-brand-weak text-brand-strong',
    'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
  ),
  success: cx(
    'border-success-light/25 bg-success-light/10 text-success-light',
    'dark:border-success-dark/25 dark:bg-success-dark/10 dark:text-success-dark',
  ),
  warning: cx(
    'border-warning-light/25 bg-warning-light/10 text-warning-light',
    'dark:border-warning-dark/25 dark:bg-warning-dark/10 dark:text-warning-dark',
  ),
  error: cx(
    'border-error-light/25 bg-error-light/10 text-error-light',
    'dark:border-error-dark/25 dark:bg-error-dark/10 dark:text-error-dark',
  ),
} as const

export interface ModalHeaderProps extends HTMLAttributes<HTMLDivElement> {
  /** Set this AND the Modal's labelledBy to the same value. */
  id?: string
  /** Optional leading glyph — rendered in a tinted circle (GuidanceCard idiom). */
  icon?: ReactNode
  /** The circle's tint: brand (default) for a neutral prompt, a status hue for a state glyph. */
  tone?: keyof typeof ICON_TONE
  /** Renders the focus-ringed close ✕. Omit on non-dismissible confirms. */
  onClose?: () => void
}

export function ModalHeader({ id, icon, tone = 'brand', onClose, className, children, ...rest }: ModalHeaderProps) {
  return (
    <div className={cx('flex items-start gap-3 px-6 pt-6', className)} {...rest}>
      {icon ? (
        <span
          aria-hidden="true"
          className={cx('flex h-10 w-10 flex-none items-center justify-center rounded-full border', ICON_TONE[tone])}
        >
          {icon}
        </span>
      ) : null}
      <h2 id={id} className={cx('min-w-0 flex-1 text-lg', icon ? 'pt-2' : undefined)}>
        {children}
      </h2>
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className={cx(
            '-m-2 flex-none rounded-lg p-2 text-text-tertiary-light transition-colors duration-fast',
            'hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark',
            'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
          )}
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </button>
      ) : null}
    </div>
  )
}

export function ModalBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('px-6 py-4', className)} {...rest} />
}

export function ModalFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx('flex flex-col gap-2 px-6 pb-6 pt-2 sm:flex-row sm:justify-end', className)}
      {...rest}
    />
  )
}

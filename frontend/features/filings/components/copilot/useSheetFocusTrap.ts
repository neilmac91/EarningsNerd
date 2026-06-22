'use client'

import { useEffect, type RefObject } from 'react'

interface UseSheetFocusTrapOptions {
  /** When true the trap is engaged: focus is moved in, kept inside, and restored on deactivate. */
  active: boolean
  /** The container that owns the trapped focus (the bottom-sheet shell / panel). */
  containerRef: RefObject<HTMLElement | null>
  /** Called on Escape (and is the close handler the consumer wires up). */
  onClose: () => void
  /**
   * Element to return focus to on close — the trigger (e.g. the launcher), which typically
   * UNMOUNTS while the sheet is open and remounts on close. We prefer this over the element that
   * was focused at activation time, because by then the trigger has already blurred to <body>
   * (capturing `document.activeElement` in the effect would restore focus to the page top).
   */
  restoreFocusRef?: RefObject<HTMLElement | null>
}

// Standard focusable selector — anything keyboard-reachable, excluding explicitly removed (-1) tabstops.
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    // "Is rendered" via getClientRects(): robust inside position:fixed containers (the sheet is
    // fixed), where offsetParent can be null even for visible elements. Excludes display:none /
    // hidden tab panels. Keep the active element regardless so focus is never lost mid-cycle.
    (el) => el.getClientRects().length > 0 || el === document.activeElement,
  )
}

/**
 * Modal-dialog focus management for a bottom-sheet (mobile only). While `active`:
 *  - captures the previously-focused element and restores it on deactivate/unmount;
 *  - moves focus into the container on activate;
 *  - keeps Tab / Shift+Tab cycling within the container (wraps at both ends);
 *  - closes on Escape.
 *
 * SSR-safe (guards `document`). The caller decides when it's a modal — pass `active` false on
 * desktop (lg+) where the sheet is a static side pane, so nothing is trapped there.
 */
export function useSheetFocusTrap({ active, containerRef, onClose, restoreFocusRef }: UseSheetFocusTrapOptions): void {
  useEffect(() => {
    if (!active) return
    if (typeof document === 'undefined') return

    const container = containerRef.current
    if (!container) return

    // Fallback restore target: whatever had focus before activation (often <body>, since the
    // trigger usually unmounts on open). `restoreFocusRef` (the remounted trigger) is preferred.
    const previouslyFocused = document.activeElement as HTMLElement | null

    // Move focus into the sheet: first focusable element, else the container itself.
    const focusables = getFocusable(container)
    if (focusables.length > 0) {
      focusables[0].focus()
    } else {
      if (!container.hasAttribute('tabindex')) container.setAttribute('tabindex', '-1')
      container.focus()
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return

      const items = getFocusable(container)
      if (items.length === 0) {
        // Nothing focusable inside — keep focus on the container.
        e.preventDefault()
        container.focus()
        return
      }

      const first = items[0]
      const last = items[items.length - 1]
      const activeEl = document.activeElement as HTMLElement | null

      if (e.shiftKey) {
        if (activeEl === first || !container.contains(activeEl)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (activeEl === last || !container.contains(activeEl)) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', onKeyDown, true)

    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      // Read restoreFocusRef.current AT CLEANUP time on purpose: the trigger (launcher) remounts on
      // close, so its *current* value is the element to return focus to — copying it at setup would
      // capture the unmounted/null trigger and defeat the focus return. Falls back to the
      // pre-activation element.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const restore = restoreFocusRef?.current ?? previouslyFocused
      restore?.focus?.()
    }
  }, [active, containerRef, onClose, restoreFocusRef])
}

export default useSheetFocusTrap

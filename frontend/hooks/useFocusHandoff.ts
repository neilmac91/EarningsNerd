'use client'

import { useCallback, useRef, type MouseEvent, type RefObject } from 'react'

export interface FocusHandoff {
  /** The control's callback ref: it sees the control leave. */
  attach: (el: HTMLElement | null) => void
  /** The control's onFocus: a new focus forgets the last press. */
  onFocus: () => void
  /** Call from the control's onClick: records whether the press came from a pointer. */
  onPress: (e: MouseEvent<HTMLElement>) => void
}

/**
 * When the control unmounts while it holds focus, for any reason (its own success, a recovery nobody
 * pressed, a new search term), focus goes to `target`: a heading or status line with tabIndex={-1}, or
 * a text field. Chromium drops a removed element's focus to <body>. Focus the control never held is
 * never moved, and nothing is armed by a press, so no later event can fire a stale hand-off.
 *
 * How: React calls a callback ref with null while it detaches the node, before the node leaves the
 * document (for a node deep inside a removed subtree too), so the callback still sees it focused. A
 * microtask, after the commit, then checks that the node really left (a node React kept, under a new ref
 * callback, did not) and that focus is on <body> (nothing else took it), and moves it. The target may be
 * in the branch that replaced the control (the dashboard title): it is attached by then. Verified in
 * Chromium under React 18.3.1 (the unit tests' runtime) and under Next's vendored React 19 canary (what
 * the App Router ships), lessons/frontend-busy-controls-stay-focusable.md (g).
 *
 * `textField`: the target is a text field, and focusing one after a tap raises the touch keyboard, so the
 * hand-off is skipped when the last press since the control took focus came from a pointer
 * (`e.detail > 0`). A keyboard press (Enter or Space, detail 0), or no press at all (focus arrived by Tab),
 * hands off. `:focus-visible` cannot stand in: it reflects how the control got focus, not how it was
 * activated.
 */
export function useFocusHandoff(
  target: RefObject<HTMLElement | null>,
  { textField = false }: { textField?: boolean } = {},
): FocusHandoff {
  const node = useRef<HTMLElement | null>(null)
  const pointerPress = useRef(false)
  const attach = useCallback(
    (el: HTMLElement | null) => {
      if (el) {
        node.current = el
        return
      }
      const left = node.current
      node.current = null
      if (!left || document.activeElement !== left) return
      if (textField && pointerPress.current) return
      queueMicrotask(() => {
        if (left.isConnected) return
        const active = document.activeElement
        if (active !== null && active !== document.body) return
        target.current?.focus({ preventScroll: true })
      })
    },
    [target, textField],
  )
  const onFocus = useCallback(() => {
    pointerPress.current = false
  }, [])
  const onPress = useCallback((e: MouseEvent<HTMLElement>) => {
    // A click from Enter or Space has detail 0; a pointer or tap has 1+.
    pointerPress.current = e.detail > 0
  }, [])
  return { attach, onFocus, onPress }
}

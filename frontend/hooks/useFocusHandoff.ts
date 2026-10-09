'use client'

import { useCallback, useEffect, useRef, type MouseEvent, type PointerEvent, type RefObject } from 'react'

export interface FocusHandoff {
  /** The control's callback ref: it sees the control leave. */
  attach: (el: HTMLElement | null) => void
  /** The control's onFocus: a keyboard focus forgets the last press; a focus a pointerdown started keeps it. */
  onFocus: () => void
  /** The control's onPointerDown: a pointer touched it, even where a busy control refuses the click. */
  onPointerDown: (e: PointerEvent<HTMLElement>) => void
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
 * hand-off is skipped when the last press since the control took focus came from a pointer. The origin is
 * taken at pointerdown, not only at the click: a busy control (the DS Button's `loading`) refuses the click
 * before its onClick runs, so a tap on it would otherwise record nothing, while its focus would forget the
 * earlier press. So a pointerdown marks the press as a pointer's, and the focus it starts keeps that mark;
 * only a focus no pointerdown started (Tab, a script) forgets it. A click records its own origin
 * (`e.detail > 0` for a pointer, 0 for Enter or Space). A keyboard press, or no press at all since a
 * keyboard focus, hands off. `:focus-visible` cannot stand in: it reflects how the control got focus, not
 * how it was activated.
 *
 * `keyboardOnly`: the same skip for a target that is not a text field, when a pointer's press should leave
 * focus to the pointer: the research pane's selected tab, which would take the arrow keys and Space from
 * someone who clicked the control that opened the pane (FilingWorkspace's launcher and the coachmark's Try,
 * EN-05). `textField` implies it.
 *
 * Limit: a pointerdown that starts no focus and no click (a touch scroll that begins on the control, or a
 * Safari mouse press on a busy control, since Safari does not focus buttons on click) leaves its mark for
 * the next focus, so a keyboard focus right after it skips the hand-off once. That errs toward no touch
 * keyboard, and the next press or focus records afresh.
 */
export function useFocusHandoff(
  target: RefObject<HTMLElement | null>,
  { textField = false, keyboardOnly = textField }: { textField?: boolean; keyboardOnly?: boolean } = {},
): FocusHandoff {
  const node = useRef<HTMLElement | null>(null)
  /** The last press since the control took focus came from a pointer. */
  const pointerPress = useRef(false)
  /** A pointerdown on the unfocused control: the focus it starts is a pointer's, not a keyboard's. */
  const pointerFocus = useRef(false)
  const attach = useCallback(
    (el: HTMLElement | null) => {
      if (el) {
        node.current = el
        return
      }
      const left = node.current
      node.current = null
      if (!left || document.activeElement !== left) return
      if (keyboardOnly && pointerPress.current) return
      queueMicrotask(() => {
        if (left.isConnected) return
        const active = document.activeElement
        if (active !== null && active !== document.body) return
        target.current?.focus({ preventScroll: true })
      })
    },
    [target, keyboardOnly],
  )
  const onPointerDown = useCallback((e: PointerEvent<HTMLElement>) => {
    pointerPress.current = true
    // A pointerdown on the focused control starts no focus, so there is no focus to mark.
    pointerFocus.current = document.activeElement !== e.currentTarget
  }, [])
  const onFocus = useCallback(() => {
    if (!pointerFocus.current) pointerPress.current = false
    pointerFocus.current = false
  }, [])
  const onPress = useCallback((e: MouseEvent<HTMLElement>) => {
    // A click from Enter or Space has detail 0; a pointer or tap has 1+.
    pointerPress.current = e.detail > 0
    pointerFocus.current = false
  }, [])
  return { attach, onFocus, onPointerDown, onPress }
}

/**
 * The other direction: a surface the user has to act on arrives (a failed generation's card), and focus
 * goes to `target`, its heading with tabIndex={-1}, when `shown` turns true. Only if nobody holds focus
 * (it is on <body>), the same check the hand-off makes: focus in a field or on a link is never moved. Nor
 * is focus taken from behind an open modal dialog (`aria-modal="true"`) the target is not in: a focused
 * control unmounting inside a dialog also drops focus to <body>, and the dialog still owns the keyboard.
 * The arrival is read after the commit, so a focused element the same commit removed (the progress
 * card's heading the error card replaced) has already dropped focus to <body>. The heading, not the
 * card's button: a key pressed as the card lands (Space to scroll, Enter) never activates its action, and
 * the target's type (a heading) holds every caller to that. Once per arrival: a re-render while shown never
 * takes focus back.
 */
export function useFocusOnArrival(target: RefObject<HTMLHeadingElement | null>, shown: boolean): void {
  useEffect(() => {
    const node = target.current
    if (!shown || !node) return
    const active = document.activeElement
    if (active !== null && active !== document.body) return
    for (const dialog of document.querySelectorAll('[aria-modal="true"]')) if (!dialog.contains(node)) return
    node.focus({ preventScroll: true })
  }, [target, shown])
}

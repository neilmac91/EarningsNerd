'use client'

import { useReducer, useState, type RefObject } from 'react'
import { hashKey, type QueryKey, type UseQueryResult } from '@tanstack/react-query'
import { Button, type ButtonProps } from '@/components/ui/Button'
import { useFocusHandoff } from '@/hooks/useFocusHandoff'

/**
 * A Retry for a failed query: `useRetainedFailure` owns the error UI's condition, `<RetryButton>` owns the
 * control (busy state, the press, the focus hand-off, the label). Every Retry of a query goes through both. A
 * Retry that restarts a stream instead (the filing page's generation restart) has no query to hold: it gives
 * RetryButton a failure built from the stream's own state, pinned in the gate's ALLOW_HAND_BUILT_FAILURE. Gates:
 * tests/unit/busyControlsStayFocusable.spec.ts (every Retry is RetryButton, each of its failures is
 * useRetainedFailure's or pinned, and every retry control reads the one retry verb) and
 * tests/unit/useRetainedFailure.spec.tsx (every caller passes its own query's key); rules:
 * lessons/frontend-busy-controls-stay-focusable.md (d), (g).
 *
 * Why RetryButton lives here and not in a file of its own: it has no clean home. components/ui is the
 * design system's primitives, kept free of react-query; components/ root is app chrome only
 * (componentsAllowlist.spec.ts); features/<domain> is one domain's code, and RetryButton serves the
 * dashboard, settings, search and the pricing page. It is this hook's control, so it sits with it.
 *
 * Runtime: the unit tests render with react 18.3.1 (package.json). The App Router aliases `react` and
 * `react-dom` to Next's vendored React (next/dist/compiled/react*, 19.3.0-canary with next 16.3.6;
 * node_modules/next/dist/build/create-compiler-aliases.js), and there is no pages/ router, so production
 * runs React 19. Nothing here depends on the difference: the hand-off was checked in Chromium on both.
 */
export interface RetainedFailure {
  /** Show the error UI: the query failed, and nothing has replaced that failure with data yet. */
  failed: boolean
  /** The failure's error, kept while a refetch has cleared the query's own `error`. */
  error: unknown
  /** A fetch is in flight, including one paused offline or in a hidden tab (`fetchStatus !== 'idle'`). */
  busy: boolean
  /** Refetch (for a stream restart, restart the stream). Only `<RetryButton>` calls it. */
  retry: () => void
}

/** The failure this component rendered, identified by the query and the query state that produced it. */
interface Shown {
  error: unknown
  /** `hashKey(queryKey)`: which query failed. */
  key: string
  at: number
  count: number
}

/**
 * React Query puts a failed query that has no data back to `pending` (`error: null`) the moment it
 * refetches, for any reason: a Retry press, a reconnect, window focus, an invalidation, a new observer
 * mounting. Read raw, that unmounts the error UI, and a focused Retry in it, for a skeleton. So a failure
 * this component has rendered stays failed through every refetch of that query until data replaces it:
 * the error UI stays up with its Retry busy, and only a fetch that succeeds ends it. A first load is never
 * held: nothing failed yet. A query with data needs no hold (it stays `error` while it refetches).
 *
 * The hold is tied to the failing query, not to the hook. `queryKey` is that query's own key (the one its
 * `useQuery` was given: a query result does not carry it), and the hold is the triple `hashKey(queryKey)`,
 * `errorUpdatedAt`, `errorUpdateCount`, which a pending refetch keeps. The key: a key change (another user,
 * a new search term) is another query, so its first load shows its own pending state, never the old query's
 * error; the state alone cannot tell two keys apart, since both may have failed in the same millisecond as
 * often. The count: a second failure of the query in the same millisecond is a new failure, and a count
 * that grew while nothing rendered (the query failed again and refetched before a render) is still that
 * query's failure, so it stays held. The time: a reset (`resetQueries`) or a rebuilt query starts the
 * count over, so its refetch is a first load, and a failure after it may repeat the old count. A fresh mount over a failure it never rendered (a child
 * observer whose mount refetches it) shows the ordinary pending state.
 *
 * Placeholder data: a query with `placeholderData` (the search's `keepPreviousData`) reports a refetch of
 * its failure as `success` with `isPlaceholderData`, carrying the previous query's data: the query itself
 * is still `pending` with no data. So while a failure is held, a placeholder-backed result counts as
 * pending, never as success: the error UI and its Retry stay mounted, busy and focused through the
 * refetch, and only the query's own data ends the hold. A caller without `placeholderData` never sees
 * `isPlaceholderData`, so nothing changes for it (at this commit the search is the only caller with one).
 *
 * Derived from the query's state on each render, with no record of presses or of fetches seen: a second
 * press, a paused fetch, or a fetch that settles inside one notify batch cannot wedge it.
 */
export function useRetainedFailure(query: UseQueryResult<unknown>, queryKey: QueryKey): RetainedFailure {
  const { isError, error, status, isPlaceholderData, fetchStatus, errorUpdatedAt, errorUpdateCount, refetch } = query
  const key = hashKey(queryKey)
  // A placeholder stands in for data the query does not have yet: the query is still pending.
  const pending = status === 'pending' || isPlaceholderData
  const busy = fetchStatus !== 'idle'
  const [shown, setShown] = useState<Shown | null>(null)
  // The query state is still the failure `shown` recorded: the same query, at the same failure.
  const same = shown !== null && shown.key === key && shown.at === errorUpdatedAt && shown.count === errorUpdateCount
  // The same query failed again since, and refetched before a render showed it: its count only grows (a
  // reset starts it over at 0), so a higher count is still that query's failure, not a first load.
  const failedAgain = shown !== null && shown.key === key && errorUpdateCount > shown.count
  let next = shown
  if (isError) {
    // A new failure (a failure of the same query moves its count, or after a reset its time), or another query's.
    if (!same) next = { error, key, at: errorUpdatedAt, count: errorUpdateCount }
  } else if (shown !== null && pending && failedAgain) {
    // Held through it: keep the error that was shown (a pending refetch has cleared the newer one), at the new count.
    next = { ...shown, at: errorUpdatedAt, count: errorUpdateCount }
  } else if (shown !== null && (!pending || !same)) {
    // Data replaced it, or this is another query's state (the key changed, or the query started over).
    next = null
  }
  if (next !== shown) setShown(next)
  // refetch() puts the fetch in the query's state at once, but React hears of it only on TanStack's next
  // notify, a later task. Render now, so the Retry is busy before a second press can land.
  const [, rerender] = useReducer((n: number) => n + 1, 0)
  const failed = isError || (next !== null && busy)
  return {
    failed,
    error: failed ? error ?? next?.error ?? null : null,
    busy,
    retry: () => {
      void refetch()
      rerender()
    },
  }
}

/** The one retry verb's busy form (D-032): shown while this button's own press runs, and its room kept at rest. */
const BUSY_LABEL = 'Trying again…'

export interface RetryButtonProps
  extends Omit<
    ButtonProps,
    | 'children'
    | 'aria-label'
    | 'aria-labelledby'
    | 'loading'
    | 'loadingText'
    | 'reserveLoadingText'
    | 'onClick'
    | 'onFocus'
    | 'onPointerDown'
  > {
  /** The failures this control retries. Busy while any has a fetch in flight; a press retries the failed ones. */
  failures: RetainedFailure[]
  /** Where focus goes if the Retry unmounts while it holds focus: a heading or status line with tabIndex={-1}.
   * Any { current } object works; a getter resolves at focus time, as in the dashboard's saved-summary retry. */
  focusTarget: RefObject<HTMLElement | null>
  /** The target is a text field: skip the hand-off after a pointer press (a tap on it busy included), so a tap never raises the touch keyboard. */
  textField?: boolean
  /** No label of a caller's own: the label is RetryButton's (D-032). Each is declared `never`, so TypeScript refuses
   * one (an omitted name alone would not do: JSX leaves an undeclared hyphenated name such as aria-label unchecked),
   * and RetryButton drops each at run time too, for one that a spread or a cast brings in. The gate in
   * tests/unit/busyControlsStayFocusable.spec.ts holds these three declarations. */
  children?: never
  'aria-label'?: never
  'aria-labelledby'?: never
}

/**
 * The DS Button as a Retry. Busy (`loading`: aria-busy + aria-disabled + a spinner + a refused press, focus
 * kept) while any of its failures has a fetch in flight, paused included, whoever started it. A press
 * retries only the failures that failed: a healthy sibling refetched too could settle first and end the
 * error UI early.
 *
 * Its label is the product's one retry verb (docs/brand/decisions-log.md D-032): "Try again", and "Trying
 * again…" only while this button's own press runs. The label is RetryButton's own, so no caller names it
 * otherwise: TypeScript refuses a child, an aria-label and an aria-labelledby (RetryButtonProps declares them
 * `never`), RetryButton drops all three before the rest of its props reach Button (one a spread or a cast brings
 * in never replaces the name), and the one-verb clause of tests/unit/busyControlsStayFocusable.spec.ts fails a
 * call site that passes one (useRetainedFailure.spec.tsx renders each and finds the name "Try again").
 *
 * Its size never changes with its state: the room of the spinner and "Trying again…" is kept at rest (Button's
 * reserveLoadingText), so neither a press nor a refetch nobody pressed widens it, wraps its label or moves the
 * card around it (without it, at 390px under 200% text the swap wrapped the label and grew the card 22 to 24px,
 * and the search alert's message re-wrapped beside a wider button; e2e filing-source-chip.spec.ts holds the box
 * through the swap in a real browser).
 *
 * The Retry usually sits inside its card's role=alert, which Chromium presents again, whole, on any text change
 * inside it: a label swap on every refetch nobody pressed (a reconnect, window focus) would re-announce the
 * failure each time. A press is the user asking, so its "Trying again…", and the swap back to "Try again" when
 * it fails again, are announced (lessons/frontend-busy-controls-stay-focusable.md (g)).
 *
 * When it unmounts while it holds focus, for any reason, focus goes to `focusTarget` (useFocusHandoff).
 */
export function RetryButton({
  failures,
  focusTarget,
  textField = false,
  variant = 'secondary',
  // A label of a caller's own is dropped here, so it never reaches the button and replaces the one verb.
  children: _child,
  'aria-label': _label,
  'aria-labelledby': _labelledBy,
  ...rest
}: RetryButtonProps) {
  const busy = failures.some((failure) => failure.busy)
  // This button's press started the fetch now running. The press renders busy at once (retry() renders
  // the fetch it started), so the first render that sees no fetch is the end of the press's retry.
  const [pressed, setPressed] = useState(false)
  if (pressed && !busy) setPressed(false)
  const { attach, onFocus, onPointerDown, onPress } = useFocusHandoff(focusTarget, { textField })
  return (
    <Button
      {...rest}
      ref={attach}
      variant={variant}
      loading={busy}
      loadingText={pressed ? BUSY_LABEL : undefined}
      // Its room is kept at rest: "Trying again…" with the spinner is wider than "Try again", and the swap
      // would otherwise widen the button, wrap its label at 200% text on a phone, and move the card around it.
      reserveLoadingText={BUSY_LABEL}
      onFocus={onFocus}
      // A busy Button refuses the click before onClick runs; pointerdown still reaches us, so a tap on a
      // busy Retry counts as a pointer press (no touch keyboard when it then unmounts).
      onPointerDown={onPointerDown}
      onClick={(e) => {
        onPress(e)
        setPressed(true)
        for (const failure of failures) if (failure.failed) failure.retry()
      }}
    >
      Try again
    </Button>
  )
}

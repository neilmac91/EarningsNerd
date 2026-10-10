'use client'

import { useReducer, useState, type RefObject } from 'react'
import { hashKey, type QueryKey, type UseQueryResult } from '@tanstack/react-query'
import { Button, type ButtonProps } from '@/components/ui/Button'
import { useFocusHandoff } from '@/hooks/useFocusHandoff'

/**
 * A Retry for a failed query: `useRetainedFailure` owns the error UI's condition, `<RetryButton>` owns the
 * control (busy state, the press, the focus hand-off). Every Retry of a query goes through both. A Retry that
 * restarts a stream instead (the filing page's Retry generation) has no query to hold: it gives RetryButton a
 * failure built from the stream's own state, pinned in the gate's ALLOW_HAND_BUILT_FAILURE. Gates:
 * tests/unit/busyControlsStayFocusable.spec.ts (every Retry is RetryButton, and each of its failures is
 * useRetainedFailure's or pinned) and tests/unit/useRetainedFailure.spec.tsx (every caller passes its own
 * query's key); rules: lessons/frontend-busy-controls-stay-focusable.md (d), (g).
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
 * Derived from the query's state on each render, with no record of presses or of fetches seen: a second
 * press, a paused fetch, or a fetch that settles inside one notify batch cannot wedge it.
 */
export function useRetainedFailure(query: UseQueryResult<unknown>, queryKey: QueryKey): RetainedFailure {
  const { isError, error, status, fetchStatus, errorUpdatedAt, errorUpdateCount, refetch } = query
  const key = hashKey(queryKey)
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
  } else if (shown !== null && status === 'pending' && failedAgain) {
    // Held through it: keep the error that was shown (a pending refetch has cleared the newer one), at the new count.
    next = { ...shown, at: errorUpdatedAt, count: errorUpdateCount }
  } else if (shown !== null && (status !== 'pending' || !same)) {
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

export interface RetryButtonProps
  extends Omit<ButtonProps, 'loading' | 'loadingText' | 'onClick' | 'onFocus' | 'onPointerDown'> {
  /** The failures this control retries. Busy while any has a fetch in flight; a press retries the failed ones. */
  failures: RetainedFailure[]
  /** Where focus goes if the Retry unmounts while it holds focus: a heading or status line with tabIndex={-1}. */
  focusTarget: RefObject<HTMLElement | null>
  /** The target is a text field: skip the hand-off after a pointer press (a tap on it busy included), so a tap never raises the touch keyboard. */
  textField?: boolean
}

/**
 * The DS Button as a Retry. Busy (`loading`: aria-busy + aria-disabled + a spinner + a refused press, focus
 * kept) while any of its failures has a fetch in flight, paused included, whoever started it. A press
 * retries only the failures that failed: a healthy sibling refetched too could settle first and end the
 * error UI early.
 *
 * "Retrying…" replaces the label only while this button's own press runs. The Retry usually sits inside
 * its card's role=alert, which Chromium presents again, whole, on any text change inside it: a label swap
 * on every refetch nobody pressed (a reconnect, window focus) would re-announce the failure each time. A
 * press is the user asking, so its "Retrying…", and the swap back to "Retry" when it fails again, are
 * announced (lessons/frontend-busy-controls-stay-focusable.md (g)).
 *
 * When it unmounts while it holds focus, for any reason, focus goes to `focusTarget` (useFocusHandoff).
 */
export function RetryButton({ failures, focusTarget, textField = false, variant = 'secondary', ...rest }: RetryButtonProps) {
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
      loadingText={pressed ? 'Retrying…' : undefined}
      onFocus={onFocus}
      // A busy Button refuses the click before onClick runs; pointerdown still reaches us, so a tap on a
      // busy Retry counts as a pointer press (no touch keyboard when it then unmounts).
      onPointerDown={onPointerDown}
      onClick={(e) => {
        onPress(e)
        setPressed(true)
        for (const failure of failures) if (failure.failed) failure.retry()
      }}
    />
  )
}

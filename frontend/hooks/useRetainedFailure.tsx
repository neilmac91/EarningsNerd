'use client'

import { useReducer, useState, type RefObject } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Button, type ButtonProps } from '@/components/ui/Button'
import { useFocusHandoff } from '@/hooks/useFocusHandoff'

/**
 * A Retry for a failed query: `useRetainedFailure` owns the error UI's condition, `<RetryButton>` owns the
 * control (busy state, the press, the focus hand-off). Every Retry of a query goes through both. Gate:
 * tests/unit/busyControlsStayFocusable.spec.ts; rules: lessons/frontend-busy-controls-stay-focusable.md (d), (g).
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
  /** Refetch. Only `<RetryButton>` calls it. */
  retry: () => void
}

/** The failure this component rendered, identified by the query state that produced it. */
interface Shown {
  error: unknown
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
 * The hold is tied to the failing query, not to the hook: a pending refetch keeps the failed state's
 * `errorUpdatedAt` and `errorUpdateCount`, and any other query (a new key: another user, a new search
 * term) has its own, so when the caller's key changes the new query's first load shows its own pending
 * state, never the old query's error. A fresh mount over a failure it never rendered (a child observer
 * whose mount refetches it) shows the ordinary pending state too.
 *
 * Derived from the query's state on each render, with no record of presses or of fetches seen: a second
 * press, a paused fetch, or a fetch that settles inside one notify batch cannot wedge it.
 */
export function useRetainedFailure(query: UseQueryResult<unknown>): RetainedFailure {
  const { isError, error, status, fetchStatus, errorUpdatedAt, errorUpdateCount, refetch } = query
  const busy = fetchStatus !== 'idle'
  const [shown, setShown] = useState<Shown | null>(null)
  let next = shown
  if (isError) {
    if (shown?.error !== error || shown.at !== errorUpdatedAt || shown.count !== errorUpdateCount) {
      next = { error, at: errorUpdatedAt, count: errorUpdateCount }
    }
  } else if (
    shown !== null &&
    (status !== 'pending' || shown.at !== errorUpdatedAt || shown.count !== errorUpdateCount)
  ) {
    // Data replaced it, or this is another query's state (the key changed).
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

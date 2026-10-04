import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager, useQuery } from '@tanstack/react-query'
import { useRef, useState, type ReactNode } from 'react'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { useFocusHandoff } from '@/hooks/useFocusHandoff'

/**
 * hooks/useRetainedFailure.tsx and hooks/useFocusHandoff.ts on their own: the failure a component has shown
 * is held through any refetch of that query until data replaces it, and a focused control that unmounts
 * hands focus to its target (lessons/frontend-busy-controls-stay-focusable.md (g)). The pages' Retry
 * buttons are pinned in busyControls.{dashboard,forms,settings,watchlist}.spec.tsx and CompanySearch.spec.tsx.
 */

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
afterEach(() => {
  onlineManager.setOnline(true)
  vi.useRealTimers()
})
/** Freeze `Date` (only): React Query stamps `errorUpdatedAt` from it, so failures can share a millisecond. */
const freezeDate = (iso: string) => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(iso))
}

const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })

/** A query keyed by `k` (a user id, a search term) and the hook over it. */
function setup(fn: ReturnType<typeof vi.fn>, client = newClient()) {
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const hook = renderHook(({ k }: { k: string }) => {
    const query = useQuery({ queryKey: ['t', k], queryFn: () => fn(k) })
    return { query, failure: useRetainedFailure(query) }
  }, { wrapper, initialProps: { k: 'a' } })
  return { client, ...hook }
}

describe('useRetainedFailure', () => {
  it('a first load is never held', () => {
    const fn = vi.fn().mockReturnValueOnce(deferred<string>().promise)
    const { result } = setup(fn)
    expect(result.current.failure).toMatchObject({ failed: false, busy: true })
  })

  it('two presses while paused cannot wedge it: the failure ends exactly when data lands', async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('one'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    onlineManager.setOnline(false)
    act(() => result.current.failure.retry())
    act(() => result.current.failure.retry())
    expect(result.current.failure).toMatchObject({ failed: true, busy: true })
    fn.mockRejectedValueOnce(new Error('two'))
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(result.current.failure.busy).toBe(false))
    expect(result.current.failure.failed).toBe(true)
    expect(fn).toHaveBeenCalledTimes(2)
    // A refetch nobody pressed holds the shown failure, with its error, while it runs, and data ends it.
    const next = deferred<string>()
    fn.mockReturnValueOnce(next.promise)
    act(() => { void client.refetchQueries() })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.failure.failed).toBe(true)
    expect((result.current.failure.error as Error).message).toBe('two')
    await act(async () => next.resolve('ok'))
    await waitFor(() => expect(result.current.failure.failed).toBe(false))
  })

  it.each([['paused', true], ['fetching', false]])('a second retry() while %s joins the first: one request, held until it settles', async (_label, offline) => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('first'))
    const { result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    const again = deferred<string>()
    fn.mockReturnValueOnce(again.promise)
    if (offline) act(() => onlineManager.setOnline(false))
    act(() => result.current.failure.retry())
    await settle()
    act(() => result.current.failure.retry())
    await settle()
    expect(result.current.failure).toMatchObject({ failed: true, busy: true })
    if (offline) act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2))
    await act(async () => again.reject(new Error('again')))
    await waitFor(() => expect(result.current.failure.busy).toBe(false))
    expect(result.current.failure.failed).toBe(true)
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it("a new key's first load is pending, not the old key's failure", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    const { result, rerender } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    fn.mockReturnValueOnce(deferred<string>().promise)
    rerender({ k: 'b' })
    expect(result.current.query.status).toBe('pending')
    expect(result.current.failure).toMatchObject({ failed: false, error: null, busy: true })
  })

  it("a new key whose query failed before, unseen here, refetches as pending, not as the old key's failure", async () => {
    const client = newClient()
    // b failed twice before this component ever showed it (another observer, an earlier visit).
    for (let i = 0; i < 2; i++) {
      await client.fetchQuery({ queryKey: ['t', 'b'], queryFn: () => Promise.reject(new Error('b down')) }).catch(() => {})
    }
    expect(client.getQueryState(['t', 'b'])).toMatchObject({ status: 'error', errorUpdateCount: 2 })
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    const { result, rerender } = setup(fn, client)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    // b's state has a failure count and is fetching: `errorUpdateCount > 0` alone would hold it as a's.
    fn.mockReturnValueOnce(deferred<string>().promise)
    rerender({ k: 'b' })
    expect(result.current.query).toMatchObject({ status: 'pending', errorUpdateCount: 2 })
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
  })

  // The hold's query identity is the pair (errorUpdatedAt, errorUpdateCount): each half alone has a case.
  it('two keys that failed in the same millisecond are told apart by their failure count', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const client = newClient()
    for (let i = 0; i < 2; i++) {
      await client.fetchQuery({ queryKey: ['t', 'b'], queryFn: () => Promise.reject(new Error('b down')) }).catch(() => {})
    }
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    const { result, rerender } = setup(fn, client)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    expect(client.getQueryState(['t', 'a'])?.errorUpdatedAt).toBe(client.getQueryState(['t', 'b'])?.errorUpdatedAt)
    fn.mockReturnValueOnce(deferred<string>().promise)
    rerender({ k: 'b' })
    expect(result.current.query).toMatchObject({ status: 'pending', errorUpdateCount: 2 })
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
  })

  it('a new key that failed as many times as the old one, at another time, is not held as the old failure', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const client = newClient()
    await client.fetchQuery({ queryKey: ['t', 'b'], queryFn: () => Promise.reject(new Error('b down')) }).catch(() => {})
    vi.setSystemTime(new Date('2026-10-04T00:00:01Z'))
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    const { result, rerender } = setup(fn, client)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    expect(result.current.query.errorUpdateCount).toBe(1)
    fn.mockReturnValueOnce(deferred<string>().promise)
    rerender({ k: 'b' })
    expect(result.current.query).toMatchObject({ status: 'pending', errorUpdateCount: 1 })
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
  })

  it('the same Error failing twice in one millisecond is a new failure, so the next refetch still holds it', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const down = new Error('down')
    const fn = vi.fn().mockRejectedValueOnce(down).mockRejectedValueOnce(down)
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    act(() => result.current.failure.retry())
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(result.current.failure.busy).toBe(false))
    expect(result.current.query.errorUpdateCount).toBe(2)
    const next = deferred<string>()
    fn.mockReturnValueOnce(next.promise)
    act(() => { void client.refetchQueries() })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.failure).toMatchObject({ failed: true, error: down })
    await act(async () => next.resolve('ok'))
  })

  it('a fresh mount over a failure it never rendered shows the ordinary pending state', async () => {
    const client = newClient()
    await client.prefetchQuery({ queryKey: ['t', 'a'], queryFn: () => Promise.reject(new Error('earlier')) })
    expect(client.getQueryState(['t', 'a'])?.status).toBe('error')
    const fn = vi.fn().mockReturnValueOnce(deferred<string>().promise)
    const { result } = setup(fn, client)
    expect(result.current.query.status).toBe('pending')
    expect(result.current.failure.failed).toBe(false)
  })
})

describe('useFocusHandoff', () => {
  /** A control that `show` mounts, handing focus to `Target A` or `Target B` when it leaves. */
  function Harness({ textField = false }: { textField?: boolean }) {
    const [show, setShow] = useState(true)
    const [second, setSecond] = useState(false)
    const a = useRef<HTMLHeadingElement>(null)
    const b = useRef<HTMLInputElement>(null)
    const { attach, onFocus, onPointerDown, onPress } = useFocusHandoff(second ? b : a, { textField })
    return (
      <div>
        <h2 ref={a} tabIndex={-1}>Target A</h2>
        <input ref={b} aria-label="Target B" />
        {show && <button ref={attach} onFocus={onFocus} onPointerDown={onPointerDown} onClick={onPress}>Retry</button>}
        <button onClick={() => setShow((s) => !s)}>toggle</button>
        <button onClick={() => setSecond(true)}>retarget</button>
      </div>
    )
  }
  const retry = () => screen.getByRole('button', { name: 'Retry' })
  /** An update from outside the control (a query notify), with focus where it is. */
  const outside = (name: string) => act(() => { screen.getByRole('button', { name }).click() })

  it('hands focus to the target when the focused control unmounts, whatever unmounts it', async () => {
    render(<Harness />)
    retry().focus()
    outside('toggle')
    await settle()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Target A' }))
  })

  it('never moves focus the control did not hold', async () => {
    render(<Harness />)
    const other = screen.getByRole('button', { name: 'retarget' })
    other.focus()
    outside('toggle')
    await settle()
    expect(document.activeElement).toBe(other)
  })

  it('focus that something else takes in the same task, before the hand-off runs, stays there', async () => {
    render(<Harness />)
    retry().focus()
    outside('toggle')
    // Still in the task that unmounted it (an autoFocus, a layout effect, another hand-off): focus moves on.
    const other = screen.getByRole('button', { name: 'retarget' })
    other.focus()
    await settle()
    expect(document.activeElement).toBe(other)
  })

  it('a node React kept under a new ref callback is no hand-off, even when its focus then falls to <body>', async () => {
    render(<Harness />)
    const node = retry()
    node.focus()
    outside('retarget')
    // Same task: the kept node loses focus (blurred, hidden, or moved by a keyed reorder in a browser).
    node.blur()
    await settle()
    expect(node.isConnected).toBe(true)
    expect(document.activeElement).toBe(document.body)
  })

  it('a node React keeps under a new ref callback (its target changed) is no hand-off: focus stays on it', async () => {
    render(<Harness />)
    const node = retry()
    node.focus()
    outside('retarget')
    await settle()
    expect(retry()).toBe(node)
    expect(document.activeElement).toBe(node)
    // The new callback owns the node: its unmount hands off to the new target.
    outside('toggle')
    await settle()
    expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Target B' }))
  })

  it.each([
    ['a pointer press', 1, 'skipped'],
    ['a keyboard press', 0, 'made'],
    ['no press (focus arrived by Tab)', null, 'made'],
  ] as const)('textField: after %s, the hand-off to the field is %s', async (_how, detail, outcome) => {
    render(<Harness textField />)
    act(() => screen.getByRole('button', { name: 'retarget' }).click())
    retry().focus()
    if (detail !== null) fireEvent.click(retry(), { detail })
    outside('toggle')
    await settle()
    const field = screen.getByRole('textbox', { name: 'Target B' })
    if (outcome === 'made') expect(document.activeElement).toBe(field)
    else expect(document.activeElement).toBe(document.body)
  })
})

describe('RetryButton', () => {
  /** A failed query's Retry over a text field, as CompanySearch's "Try again": it goes when data lands. */
  function FieldRetry({ fn }: { fn: () => Promise<string> }) {
    const query = useQuery({ queryKey: ['field'], queryFn: fn })
    const failure = useRetainedFailure(query)
    const field = useRef<HTMLInputElement>(null)
    return (
      <div>
        <input ref={field} aria-label="Search" />
        {failure.failed && <RetryButton failures={[failure]} focusTarget={field} textField>Try again</RetryButton>}
        <button>elsewhere</button>
      </div>
    )
  }
  async function failedRetry() {
    const client = newClient()
    const fn = vi.fn().mockRejectedValueOnce(new Error('down'))
    render(<QueryClientProvider client={client}><FieldRetry fn={fn} /></QueryClientProvider>)
    const retry = await screen.findByRole('button', { name: 'Try again' })
    return { client, fn, retry }
  }
  const field = () => screen.getByRole('textbox', { name: 'Search' })
  /** A tap, as a browser sends it: pointerdown, the focus it starts (none if already focused), the click. */
  const tap = (el: HTMLElement) => {
    fireEvent.pointerDown(el)
    act(() => el.focus())
    fireEvent.click(el, { detail: 1 })
  }

  it('busy is focusable: aria-busy and aria-disabled, never native disabled, and a press while busy sends nothing', async () => {
    const { client, fn, retry } = await failedRetry()
    retry.focus()
    const recovery = deferred<string>()
    fn.mockReturnValueOnce(recovery.promise)
    act(() => { void client.refetchQueries() })
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    expect(retry).toHaveAttribute('aria-disabled', 'true')
    expect(retry).not.toBeDisabled()
    expect(document.activeElement).toBe(retry)
    fireEvent.click(retry, { detail: 0 })
    await settle()
    expect(fn).toHaveBeenCalledTimes(2)
    await act(async () => recovery.resolve('ok'))
  })

  // The pointer origin is taken at pointerdown: a busy Retry refuses the click before onClick runs, and the
  // focus a tap starts must not read as a keyboard's. The last press since the Retry took focus decides.
  it.each([
    ['a tap on it while busy from a refetch nobody pressed', 'skipped'],
    ['a tap, a tap elsewhere, then a tap on it busy', 'skipped'],
    ['a tap, then Tab away and back', 'made'],
    ['a click that starts no focus (Safari), then focus by Tab', 'made'],
    ['a tap on it busy while keyboard-focused, then Tab away and back', 'made'],
  ] as const)('textField: after %s, the hand-off to the field is %s', async (how, outcome) => {
    const { client, fn, retry } = await failedRetry()
    const recovery = deferred<string>()
    fn.mockReturnValueOnce(recovery.promise)
    const elsewhere = screen.getByRole('button', { name: 'elsewhere' })
    const busyFromRefetch = async () => {
      act(() => { void client.refetchQueries() })
      await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    }
    const tabAwayAndBack = () => {
      act(() => retry.blur())
      act(() => retry.focus())
    }
    if (how === 'a tap on it while busy from a refetch nobody pressed') {
      await busyFromRefetch()
      tap(retry)
    } else if (how === 'a tap, a tap elsewhere, then a tap on it busy') {
      tap(retry)
      await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
      tap(elsewhere)
      tap(retry)
    } else if (how === 'a tap, then Tab away and back') {
      tap(retry)
      tabAwayAndBack()
    } else if (how === 'a click that starts no focus (Safari), then focus by Tab') {
      fireEvent.pointerDown(retry)
      fireEvent.click(retry, { detail: 1 })
      act(() => retry.focus())
    } else {
      act(() => retry.focus())
      await busyFromRefetch()
      fireEvent.pointerDown(retry)
      fireEvent.click(retry, { detail: 1 })
      tabAwayAndBack()
    }
    expect(document.activeElement).toBe(retry)
    expect(fn).toHaveBeenCalledTimes(2)
    await act(async () => recovery.resolve('ok'))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    if (outcome === 'made') expect(document.activeElement).toBe(field())
    else expect(document.activeElement).toBe(document.body)
  })
})

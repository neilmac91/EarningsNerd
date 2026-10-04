import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager, useQuery } from '@tanstack/react-query'
import { useRef, useState, type ReactNode } from 'react'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { useFocusHandoff } from '@/hooks/useFocusHandoff'
import { bindingResolver, type Binding } from './astBindings'

/**
 * hooks/useRetainedFailure.tsx and hooks/useFocusHandoff.ts on their own: the failure a component has shown
 * is held through any refetch of that query until data replaces it, and a focused control that unmounts
 * hands focus to its target (lessons/frontend-busy-controls-stay-focusable.md (g)). The pages' Retry
 * buttons are pinned in busyControls.{dashboard,forms,settings,watchlist}.spec.tsx and CompanySearch.spec.tsx.
 * The last block gates the hook's callers: each passes the key its own query was given.
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
  vi.restoreAllMocks()
})
/** Freeze `Date` (only): React Query stamps `errorUpdatedAt` from it, so failures can share a millisecond. */
const freezeDate = (iso: string) => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(iso))
}

const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })

/** A query keyed by `k` (a user id, a search term) and the hook over it; `enabled` per key (default: all). */
function setup(fn: ReturnType<typeof vi.fn>, client = newClient(), enabled: (k: string) => boolean = () => true) {
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const hook = renderHook(({ k }: { k: string }) => {
    const query = useQuery({ queryKey: ['t', k], queryFn: () => fn(k), enabled: enabled(k) })
    return { query, failure: useRetainedFailure(query, ['t', k]) }
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

  // The hold's identity is the query's key (`hashKey(queryKey)`) and its failure (`errorUpdatedAt`,
  // `errorUpdateCount`). The state alone cannot tell two keys apart: the first case is the collision.
  it("two keys that failed once each in the same millisecond: the new key's refetch is pending, not the old key's failure", async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const client = newClient()
    await client.fetchQuery({ queryKey: ['t', 'b'], queryFn: () => Promise.reject(new Error('b down')) }).catch(() => {})
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    const { result, rerender } = setup(fn, client)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    // Same time, same count: a's failure state and b's are indistinguishable without the key.
    expect(client.getQueryState(['t', 'a'])).toMatchObject({
      errorUpdateCount: 1,
      errorUpdatedAt: client.getQueryState(['t', 'b'])?.errorUpdatedAt,
    })
    fn.mockReturnValueOnce(deferred<string>().promise)
    rerender({ k: 'b' })
    expect(result.current.query).toMatchObject({ status: 'pending', errorUpdateCount: 1 })
    expect(result.current.failure).toMatchObject({ failed: false, error: null, busy: true })
  })

  it('two keys that failed in the same millisecond, unequally often: the new key is not held as the old failure', async () => {
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

  it('a new key that failed as often as the old one, at another time, is not held as the old failure', async () => {
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

  it("a new key's failure shown as it is (no refetch on the switch) is recorded under its own key: its refetch is held", async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const client = newClient()
    await client.fetchQuery({ queryKey: ['t', 'b'], queryFn: () => Promise.reject(new Error('b down')) }).catch(() => {})
    const fn = vi.fn().mockRejectedValueOnce(new Error('a down'))
    // b is disabled here, so the switch shows b's cached failure as it is, with no refetch.
    const { result, rerender } = setup(fn, client, (k) => k === 'a')
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    rerender({ k: 'b' })
    // Same time, same count as a's failure: only the key tells them apart.
    expect(result.current.query).toMatchObject({ status: 'error', errorUpdateCount: 1, errorUpdatedAt: Date.now() })
    expect(result.current.failure).toMatchObject({ failed: true, error: expect.objectContaining({ message: 'b down' }) })
    const next = deferred<string>()
    fn.mockReturnValueOnce(next.promise)
    act(() => result.current.failure.retry())
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.query.status).toBe('pending')
    expect(result.current.failure).toMatchObject({ failed: true, error: expect.objectContaining({ message: 'b down' }) })
    await act(async () => next.resolve('ok'))
    await waitFor(() => expect(result.current.failure.failed).toBe(false))
  })

  // Same key: a new failure moves the failure count (a second failure in the same millisecond) or the failure
  // time (a reset starts the count over). Either way it is recorded, so the next refetch holds the newer error.
  it.each([['the same Error', true], ['another Error', false]])(
    'the query failing again in the same millisecond (%s) is a new failure: the next refetch holds the newer one',
    async (_label, sameError) => {
      freezeDate('2026-10-04T00:00:00Z')
      const first = new Error('down')
      const second = sameError ? first : new Error('still down')
      const fn = vi.fn().mockRejectedValueOnce(first).mockRejectedValueOnce(second)
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
      expect(result.current.failure).toMatchObject({ failed: true, error: second })
      await act(async () => next.resolve('ok'))
    },
  )

  it('a reset whose refetch fails again is a new failure at the same count: the next refetch holds the newer one', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const fn = vi.fn().mockRejectedValueOnce(new Error('before the reset'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    vi.setSystemTime(new Date('2026-10-04T00:00:01Z'))
    fn.mockRejectedValueOnce(new Error('after the reset'))
    // The refetch fails before React Query notifies, so the reset's pending state is never rendered: the next
    // render is the new failure, at the old count (the reset started it over) and a new time.
    act(() => { void client.resetQueries({ queryKey: ['t', 'a'] }) })
    await settle()
    expect(result.current.query).toMatchObject({ status: 'error', errorUpdateCount: 1, errorUpdatedAt: Date.now() })
    const next = deferred<string>()
    fn.mockReturnValueOnce(next.promise)
    act(() => { void client.refetchQueries() })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.failure.failed).toBe(true)
    expect((result.current.failure.error as Error).message).toBe('after the reset')
    await act(async () => next.resolve('ok'))
  })

  it("a reset of the shown failure's own query starts it over: its refetch is a first load, not held", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('down'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    const next = deferred<string>()
    fn.mockReturnValueOnce(next.promise)
    // Same key; the reset puts its state back to the start (no failure count, no failure time) and refetches.
    act(() => { void client.resetQueries({ queryKey: ['t', 'a'] }) })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.query).toMatchObject({ status: 'pending', errorUpdateCount: 0, errorUpdatedAt: 0 })
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
    await act(async () => next.resolve('ok'))
  })

  it('a failure the query repeats unrendered, then a refetch: the shown failure stays held until data lands', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const fn = vi.fn().mockRejectedValueOnce(new Error('one'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    vi.setSystemTime(new Date('2026-10-04T00:00:01Z'))
    const next = deferred<string>()
    fn.mockRejectedValueOnce(new Error('two')).mockReturnValueOnce(next.promise)
    await act(async () => {
      // The query fails again (count 2, never rendered) and a new fetch starts before React Query notifies.
      await client.refetchQueries()
      void client.refetchQueries()
    })
    await waitFor(() => expect(result.current.query.status).toBe('pending'))
    expect(result.current.query).toMatchObject({ fetchStatus: 'fetching', errorUpdateCount: 2 })
    // Still the failure on screen: the error UI and its Retry stay, busy, with the error that was shown.
    expect(result.current.failure).toMatchObject({ failed: true, busy: true })
    expect((result.current.failure.error as Error).message).toBe('one')
    await act(async () => next.resolve('ok'))
    await waitFor(() => expect(result.current.failure).toMatchObject({ failed: false, error: null }))
  })

  it('a reset whose refetch fails again unrendered, at the old count, then a refetch: the old failure is not held', async () => {
    freezeDate('2026-10-04T00:00:00Z')
    const fn = vi.fn().mockRejectedValueOnce(new Error('before the reset'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    vi.setSystemTime(new Date('2026-10-04T00:00:01Z'))
    const next = deferred<string>()
    fn.mockRejectedValueOnce(new Error('after the reset')).mockReturnValueOnce(next.promise)
    await act(async () => {
      // The reset starts the query over and its refetch fails (count 1 again, never rendered); a new fetch
      // starts before React Query notifies.
      await client.resetQueries({ queryKey: ['t', 'a'] })
      void client.refetchQueries()
    })
    // React hears of it on React Query's next notify, a later task: the first render after the act.
    await waitFor(() => expect(result.current.query.status).toBe('pending'))
    // Only the time tells this state from the shown failure's: same key, same count.
    expect(result.current.query).toMatchObject({ fetchStatus: 'fetching', errorUpdateCount: 1, errorUpdatedAt: Date.now() })
    expect(result.current.failure).toMatchObject({ failed: false, error: null, busy: true })
    await act(async () => next.resolve('ok'))
  })

  it('once data replaced the failure, a later refetch nobody pressed shows no failure', async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('down')).mockResolvedValueOnce('ok')
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    act(() => result.current.failure.retry())
    await waitFor(() => expect(result.current.query.status).toBe('success'))
    await waitFor(() => expect(result.current.failure.busy).toBe(false))
    // The success keeps the query's failure count and time: only its status says data replaced the failure.
    expect(result.current.query).toMatchObject({ errorUpdateCount: 1, data: 'ok' })
    const later = deferred<string>()
    fn.mockReturnValueOnce(later.promise)
    act(() => { void client.refetchQueries() })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
    await act(async () => later.resolve('ok again'))
  })

  it('data that lands with a new refetch already running ends the hold: data, not an idle fetch, ends it', async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error('down'))
    const { client, result } = setup(fn)
    await waitFor(() => expect(result.current.failure.failed).toBe(true))
    const later = deferred<string>()
    fn.mockReturnValueOnce(later.promise)
    // A mutation's onSuccess that writes the cache and refetches: the first render after it has data and a fetch.
    act(() => {
      client.setQueryData(['t', 'a'], 'ok')
      void client.refetchQueries()
    })
    await waitFor(() => expect(result.current.failure.busy).toBe(true))
    expect(result.current.query).toMatchObject({ status: 'success', data: 'ok' })
    expect(result.current.failure).toMatchObject({ failed: false, error: null })
    await act(async () => later.resolve('ok again'))
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
    ['a pointer press', 'skipped', [1]],
    ['a keyboard press', 'made', [0]],
    ['no press (focus arrived by Tab)', 'made', []],
    // The last press decides: a keyboard press after a tap is a keyboard's.
    ['a tap, then a keyboard press', 'made', [1, 0]],
  ] as const)('textField: after %s, the hand-off to the field is %s', async (_how, outcome, details) => {
    render(<Harness textField />)
    act(() => screen.getByRole('button', { name: 'retarget' }).click())
    retry().focus()
    for (const detail of details) fireEvent.click(retry(), { detail })
    outside('toggle')
    await settle()
    const field = screen.getByRole('textbox', { name: 'Target B' })
    if (outcome === 'made') expect(document.activeElement).toBe(field)
    else expect(document.activeElement).toBe(document.body)
  })

  it('not a text field: a pointer press still hands off to the heading (no touch keyboard to spare)', async () => {
    render(<Harness />)
    fireEvent.pointerDown(retry())
    act(() => retry().focus())
    fireEvent.click(retry(), { detail: 1 })
    outside('toggle')
    await settle()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Target A' }))
  })

  it('focuses the target with preventScroll, so the hand-off never scrolls the page', async () => {
    render(<Harness />)
    retry().focus()
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    outside('toggle')
    await settle()
    expect(focus).toHaveBeenCalledTimes(1)
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Target A' }))
  })
})

describe('RetryButton', () => {
  /** A failed query's Retry over a text field, as CompanySearch's "Try again": it goes when data lands. */
  function FieldRetry({ fn }: { fn: () => Promise<string> }) {
    const query = useQuery({ queryKey: ['field'], queryFn: fn })
    const failure = useRetainedFailure(query, ['field'])
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
    ['a tap on it busy while unfocused, then Tab away and back', 'made'],
    // The tap lands on the spinner inside the focused Retry: the pointerdown's target is the svg, its
    // currentTarget the Retry, which already holds focus, so the tap starts no focus to mark.
    ["a tap on its spinner while it is busy and keyboard-focused, then Tab away and back", 'made'],
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
    } else if (how === 'a tap on it busy while keyboard-focused, then Tab away and back') {
      act(() => retry.focus())
      await busyFromRefetch()
      fireEvent.pointerDown(retry)
      fireEvent.click(retry, { detail: 1 })
      tabAwayAndBack()
    } else if (how === 'a tap on it busy while unfocused, then Tab away and back') {
      await busyFromRefetch()
      tap(retry)
      tabAwayAndBack()
    } else {
      act(() => retry.focus())
      await busyFromRefetch()
      const spinner = retry.querySelector('svg')
      expect(spinner).not.toBeNull()
      fireEvent.pointerDown(spinner as Element)
      fireEvent.click(spinner as Element, { detail: 1 })
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

/**
 * Rule-12 gate for the hold's identity: `useRetainedFailure(query, queryKey)` is told which query it holds by
 * `queryKey`, so a caller that passes another key (or none) brings back the collision the key closes: a key
 * change held as the old key's failure. Every call under app/, components/, features/, hooks/ and lib/ must name
 * a same-file `useQuery` / `useSuspenseQuery` / `useInfiniteQuery` call (directly or through a const) and pass,
 * as its key, the same expression as that call's `queryKey:` (whitespace aside).
 */
describe("every useRetainedFailure caller passes its own query's key (rule-12 gate)", () => {
  const QUERY_HOOK = /^(useQuery|useSuspenseQuery|useInfiniteQuery)$/
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  const bare = (node: ts.Node) => node.getText().replace(/\s+/g, '')

  /** Each `useRetainedFailure(…)` call whose key is not its query's own `queryKey`, as `line: call`. */
  function keyMismatches(source: string, fileName: string): { calls: number; offenders: string[] } {
    const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const visible = bindingResolver(sf)
    /** The `queryKey:` of the query hook call `e` holds: the call itself, or a const bound to one. */
    const ownKey = (e: ts.Expression, seen = new Set<Binding>()): ts.Expression | null => {
      if (ts.isParenthesizedExpression(e)) return ownKey(e.expression, seen)
      if (ts.isCallExpression(e) && ts.isIdentifier(e.expression) && QUERY_HOOK.test(e.expression.text)) {
        const options = e.arguments[0]
        if (!options || !ts.isObjectLiteralExpression(options)) return null
        for (const p of options.properties) {
          if (ts.isPropertyAssignment(p) && p.name.getText() === 'queryKey') return p.initializer
        }
        return null
      }
      if (!ts.isIdentifier(e)) return null
      const b = visible(e)
      if (!b?.init || seen.has(b)) return null
      return ownKey(b.init, new Set([...seen, b]))
    }
    let calls = 0
    const offenders: string[] = []
    const visit = (node: ts.Node): void => {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'useRetainedFailure') {
        calls += 1
        const [query, key] = node.arguments
        const own = query ? ownKey(query) : null
        if (!own || !key || bare(own) !== bare(key)) {
          const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
          offenders.push(`${line + 1}: ${node.getText(sf).replace(/\s+/g, ' ')}`)
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
    return { calls, offenders }
  }

  it("sees a key that is not the query's own, a missing key and a query it cannot name", () => {
    const fixture = [
      'export function A({ query, key }: Props) {',
      '  const userQuery = useQuery({ queryKey: queryKeys.currentUser(), queryFn })',
      '  const usage = useQuery({',
      '    queryKey: queryKeys.usage.byUser(user?.id),',
      '    queryFn,',
      '  })',
      '  const aliased = usage',
      '  const own = useRetainedFailure(userQuery, queryKeys.currentUser())', // its own key
      '  const wrapped = useRetainedFailure(aliased, queryKeys.usage.byUser(',
      '    user?.id', // whitespace aside
      '  ))',
      '  const other = useRetainedFailure(usage, queryKeys.usage.byUser(id))', // another user's key
      '  const swapped = useRetainedFailure(userQuery, queryKeys.usage.byUser(user?.id))', // another query's key
      '  const none = useRetainedFailure(userQuery)', // no key
      '  const prop = useRetainedFailure(query, key)', // not a same-file query: nothing to compare
      '}',
    ].join('\n')
    expect(keyMismatches(fixture, 'fixture.tsx')).toEqual({
      calls: 6,
      offenders: [
        '12: useRetainedFailure(usage, queryKeys.usage.byUser(id))',
        '13: useRetainedFailure(userQuery, queryKeys.usage.byUser(user?.id))',
        '14: useRetainedFailure(userQuery)',
        '15: useRetainedFailure(query, key)',
      ],
    })
  })

  it('every caller in the app passes the key its own query was given', () => {
    const walk = (dir: string, out: string[]): string[] => {
      for (const name of readdirSync(dir)) {
        const p = path.join(dir, name)
        if (statSync(p).isDirectory()) walk(p, out)
        else if (/\.tsx?$/.test(p) && !p.endsWith('.d.ts')) out.push(p)
      }
      return out
    }
    let calls = 0
    const offenders: string[] = []
    for (const abs of ['app', 'components', 'features', 'hooks', 'lib'].flatMap((root) => walk(path.join(frontendRoot, root), []))) {
      const rel = path.relative(frontendRoot, abs).split(path.sep).join('/')
      const found = keyMismatches(readFileSync(abs, 'utf8'), rel)
      calls += found.calls
      offenders.push(...found.offenders.map((offender) => `${rel}:${offender}`))
    }
    expect(
      offenders,
      'Pass useRetainedFailure the key its own useQuery was given: `useRetainedFailure(query, <that queryKey>)`.',
    ).toEqual([])
    // The dashboard's four, the settings page, the pricing page's three, CompanySearch, BillingPanel's two, FilingFeed.
    expect(calls).toBeGreaterThanOrEqual(12)
  })
})

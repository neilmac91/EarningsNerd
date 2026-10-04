import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager, useQuery } from '@tanstack/react-query'
import { useRef, useState, type ReactNode } from 'react'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'
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
afterEach(() => onlineManager.setOnline(true))

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
    const { attach, onFocus, onPress } = useFocusHandoff(second ? b : a, { textField })
    return (
      <div>
        <h2 ref={a} tabIndex={-1}>Target A</h2>
        <input ref={b} aria-label="Target B" />
        {show && <button ref={attach} onFocus={onFocus} onClick={onPress}>Retry</button>}
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

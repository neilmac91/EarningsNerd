import { afterEach, describe, expect, it, vi } from 'vitest'
import { PAGE_LEAVE_TIMEOUT_MS, untilPageReturns } from '@/lib/untilPageReturns'

// The hold a mutation returns while its success navigates the page away (Manage billing, Manage
// subscription). Those controls' own specs pin the pageshow path in place; this pins the timeout that
// releases a navigation the user aborted, and that whichever fires first cleans up the other.
describe('untilPageReturns', () => {
  afterEach(() => vi.useRealTimers())

  const settled = (promise: Promise<void>) => {
    let done = false
    void promise.then(() => { done = true })
    return () => done
  }

  it('settles on pageshow (a back-forward cache restore) and clears its timer', async () => {
    vi.useFakeTimers()
    const isDone = settled(untilPageReturns())
    await vi.advanceTimersByTimeAsync(PAGE_LEAVE_TIMEOUT_MS - 1)
    expect(isDone()).toBe(false)
    window.dispatchEvent(new Event('pageshow'))
    await vi.advanceTimersByTimeAsync(0)
    expect(isDone()).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('settles after the timeout when the navigation never commits, and stops listening for pageshow', async () => {
    vi.useFakeTimers()
    const remove = vi.spyOn(window, 'removeEventListener')
    const isDone = settled(untilPageReturns(5_000))
    await vi.advanceTimersByTimeAsync(4_999)
    expect(isDone()).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(isDone()).toBe(true)
    expect(remove).toHaveBeenCalledWith('pageshow', expect.any(Function))
    remove.mockRestore()
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { PAGE_LEAVE_TIMEOUT_MS, untilPageReturns } from '@/lib/untilPageReturns'

// The hold a mutation returns while its success navigates the page away (Manage billing, Manage
// subscription). Those controls' own specs pin the pageshow path in place. This pins when else the
// hold lets go: on an aborted navigation (Navigation API `navigateerror`) and never on a slow one,
// and only where that API is missing, after a bounded timeout. Whichever fires first cleans up the rest.
describe('untilPageReturns', () => {
  afterEach(() => {
    vi.useRealTimers()
    Reflect.deleteProperty(window, 'navigation')
  })

  const settled = (promise: Promise<void>) => {
    let done = false
    void promise.then(() => { done = true })
    return () => done
  }
  /** jsdom has no Navigation API; a bare EventTarget stands in for `window.navigation`. */
  const withNavigationApi = () => {
    const navigation = new EventTarget()
    Object.defineProperty(window, 'navigation', { value: navigation, configurable: true })
    return navigation
  }

  describe('with the Navigation API', () => {
    it('holds through a slow navigation, with no timer, and lets go when it is aborted', async () => {
      vi.useFakeTimers()
      const navigation = withNavigationApi()
      const remove = vi.spyOn(window, 'removeEventListener')
      const isDone = settled(untilPageReturns())
      expect(vi.getTimerCount()).toBe(0)
      await vi.advanceTimersByTimeAsync(PAGE_LEAVE_TIMEOUT_MS * 6)
      expect(isDone()).toBe(false)

      navigation.dispatchEvent(new Event('navigateerror'))
      await vi.advanceTimersByTimeAsync(0)
      expect(isDone()).toBe(true)
      expect(remove).toHaveBeenCalledWith('pageshow', expect.any(Function))
      remove.mockRestore()
    })

    it('lets go on pageshow (a back-forward cache restore) and stops listening for navigateerror', async () => {
      const navigation = withNavigationApi()
      const remove = vi.spyOn(navigation, 'removeEventListener')
      const isDone = settled(untilPageReturns())
      window.dispatchEvent(new Event('pageshow'))
      await Promise.resolve()
      expect(isDone()).toBe(true)
      expect(remove).toHaveBeenCalledWith('navigateerror', expect.any(Function))
    })
  })

  describe('without the Navigation API', () => {
    it('lets go on pageshow and clears its fallback timer', async () => {
      vi.useFakeTimers()
      const isDone = settled(untilPageReturns())
      await vi.advanceTimersByTimeAsync(PAGE_LEAVE_TIMEOUT_MS - 1)
      expect(isDone()).toBe(false)
      window.dispatchEvent(new Event('pageshow'))
      await vi.advanceTimersByTimeAsync(0)
      expect(isDone()).toBe(true)
      expect(vi.getTimerCount()).toBe(0)
    })

    it('lets go after the timeout, since an aborted navigation fires nothing, and stops listening for pageshow', async () => {
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
})

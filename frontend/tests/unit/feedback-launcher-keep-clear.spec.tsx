import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import { queryKeys } from '@/lib/queryKeys'
import { CONSENT_LAYER_EVENT } from '@/lib/consentLayer'
import { LAUNCHER_KEEP_CLEAR_GAP, overlapsKeepClear } from '@/lib/launcherKeepClear'

/**
 * N17: on a phone the floating feedback launcher rested over the analysis headline figures after Run, so "$14.3B"
 * read "4.3B" (three blind evaluators, severity 3). The launcher now steps aside without moving: while its box,
 * LAUNCHER_KEEP_CLEAR_GAP px around, meets a region marked `data-launcher-keep-clear` (the KPI strip), it takes
 * `opacity-0 pointer-events-none`, `focus:` brings it back, and it never yields while its own dialog is open. It stays
 * one fixed site at z-30 on BOTTOM_CHROME_OFFSET (tests/unit/bottomChromeLadder.spec.ts, unchanged).
 *
 * jsdom lays nothing out, so the boxes are stubbed and requestAnimationFrame is a queue this spec flushes; what a
 * browser paints is tests/e2e/feedback-launcher-keep-clear.spec.ts's.
 *
 * Mutation (on committed state): `yielding && …` → `false && …` in FeedbackWidget.tsx fails the widget cases.
 */

vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FEEDBACK_WIDGET: true,
}))
vi.mock('@/features/feedback/api/feedback-api', () => ({ submitFeedback: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: vi.fn() }))

type Box = { left: number; top: number; width: number; height: number }
const rect = ({ left, top, width, height }: Box) =>
  ({ left, top, width, height, x: left, y: top, right: left + width, bottom: top + height, toJSON: () => ({}) }) as DOMRect

/** The launcher on a 390x844 phone: a 44px circle 20px from the left and the bottom. */
const LAUNCHER: Box = { left: 20, top: 780, width: 44, height: 44 }
const BOX = rect(LAUNCHER)
const GAP = LAUNCHER_KEEP_CLEAR_GAP

describe('overlapsKeepClear', () => {
  const regions = (...boxes: Array<Box & { marked?: boolean }>) => {
    const root = document.createElement('div')
    for (const { marked = true, ...box } of boxes) {
      const el = document.createElement('div')
      if (marked) el.setAttribute('data-launcher-keep-clear', '')
      el.getBoundingClientRect = () => rect(box)
      root.appendChild(el)
    }
    return root
  }

  it('meets a region under the box or inside the gap around it, and nothing at or past the gap', () => {
    expect(GAP).toBe(8)
    // Under the box: the KPI strip on the launcher's line.
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: 800, width: 358, height: 200 }))).toBe(true)
    // Below the box: half a pixel inside the gap, then exactly at it.
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: BOX.bottom + GAP - 0.5, width: 358, height: 200 }))).toBe(true)
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: BOX.bottom + GAP, width: 358, height: 200 }))).toBe(false)
    // Above the box.
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: 500, width: 358, height: BOX.top - GAP - 500 + 0.5 }))).toBe(true)
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: 500, width: 358, height: BOX.top - GAP - 500 }))).toBe(false)
    // To the right of the box, and to its left.
    expect(overlapsKeepClear(BOX, regions({ left: BOX.right + GAP - 0.5, top: 780, width: 100, height: 44 }))).toBe(true)
    expect(overlapsKeepClear(BOX, regions({ left: BOX.right + GAP, top: 780, width: 100, height: 44 }))).toBe(false)
    expect(overlapsKeepClear(BOX, regions({ left: 0, top: 780, width: BOX.left - GAP + 0.5, height: 44 }))).toBe(true)
    expect(overlapsKeepClear(BOX, regions({ left: 0, top: 780, width: BOX.left - GAP, height: 44 }))).toBe(false)
  })

  it('skips a region that renders no box and an element that is not marked', () => {
    expect(overlapsKeepClear(BOX, regions({ left: 30, top: 790, width: 0, height: 0 }))).toBe(false)
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: 800, width: 358, height: 200, marked: false }))).toBe(false)
    // One region anywhere in the root is enough.
    expect(overlapsKeepClear(BOX, regions({ left: 16, top: 100, width: 358, height: 200 }, { left: 16, top: 800, width: 358, height: 200 }))).toBe(true)
  })
})

describe('FeedbackWidget steps aside from a keep-clear region', () => {
  let frames = new Map<number, FrameRequestCallback>()
  let nextFrame = 1
  let region: Box
  let observed: Array<{ target: Element; callback: () => void }>

  /** Runs the frames queued so far, as the browser's next frame would. */
  const flush = () => act(() => {
    const run = [...frames.values()]
    frames = new Map()
    for (const callback of run) callback(0)
  })
  const yieldClasses = ['opacity-0', 'pointer-events-none']

  beforeEach(() => {
    frames = new Map()
    nextFrame = 1
    observed = []
    region = { left: 16, top: 900, width: 358, height: 200 } // below the launcher's gap
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      const id = nextFrame++
      frames.set(id, callback)
      return id
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => { frames.delete(id) })
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      if (this.hasAttribute('data-launcher-keep-clear')) return rect(region)
      if (this.getAttribute('aria-haspopup') === 'dialog') return rect(LAUNCHER)
      return rect({ left: 0, top: 0, width: 0, height: 0 })
    })
    vi.stubGlobal('ResizeObserver', class {
      constructor(private callback: () => void) {}
      observe(target: Element) { observed.push({ target, callback: this.callback }) }
      unobserve() {}
      disconnect() { observed = observed.filter((entry) => entry.callback !== this.callback) }
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  /** A reader the current-user query already confirms, as busyControls.forms.spec.tsx mounts one. */
  const reader: CurrentUser = {
    id: 1, email: '1@example.test', full_name: null, is_pro: false, is_beta: true, is_admin: false, email_verified: true,
  }
  const renderWidget = async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), reader)
    render(
      <QueryClientProvider client={client}>
        <div data-launcher-keep-clear>Headline figures</div>
        <FeedbackWidget />
      </QueryClientProvider>,
    )
    const launcher = await screen.findByRole('button', { name: 'Send feedback' })
    flush() // the check queued on mount
    return launcher
  }

  it('yields while the region meets its box, keeps its name, and returns when the region moves away', async () => {
    const launcher = await renderWidget()
    for (const name of yieldClasses) expect(launcher).not.toHaveClass(name)

    region = { left: 16, top: 800, width: 358, height: 200 } // the strip scrolled under the launcher
    fireEvent.scroll(window)
    flush()
    expect(launcher).toHaveClass(...yieldClasses)
    // Keyboard focus brings it back (`focus:`, so a focus Modal returns after a pointer close counts too).
    expect(launcher).toHaveClass('focus:opacity-100', 'focus:pointer-events-auto')
    // It stays in the accessibility tree with its name, and keeps its place: one fixed site at z-30.
    expect(screen.getByRole('button', { name: 'Send feedback' })).toBe(launcher)
    expect(launcher).toHaveClass('fixed', 'z-30')

    region = { left: 16, top: 900, width: 358, height: 200 }
    fireEvent(window, new Event('resize'))
    flush()
    for (const name of [...yieldClasses, 'focus:opacity-100']) expect(launcher).not.toHaveClass(name)
  })

  it('checks once a frame on a scroll, a resize, the consent bar and a change of the page size, and stops on unmount', async () => {
    const launcher = await renderWidget()
    region = { left: 16, top: 800, width: 358, height: 200 }

    // Three scrolls in one frame queue one check.
    fireEvent.scroll(window)
    fireEvent.scroll(window)
    fireEvent.scroll(window)
    expect(frames.size).toBe(1)
    flush()
    expect(launcher).toHaveClass(...yieldClasses)

    // The consent bar coming or going moves the launcher (BOTTOM_CHROME_OFFSET): the check runs again.
    region = { left: 16, top: 900, width: 358, height: 200 }
    window.dispatchEvent(new CustomEvent(CONSENT_LAYER_EVENT, { detail: { visible: true, height: 120 } }))
    expect(frames.size).toBe(1)
    flush()
    expect(launcher).not.toHaveClass('opacity-0')

    // Results mount after Run with no scroll: the page's size changes, and the observer on <body> queues the check.
    expect(observed.map((entry) => entry.target)).toEqual([document.body])
    region = { left: 16, top: 800, width: 358, height: 200 }
    observed[0].callback()
    flush()
    expect(launcher).toHaveClass(...yieldClasses)

    cleanup()
    expect(observed).toEqual([])
    fireEvent.scroll(window)
    fireEvent(window, new Event('resize'))
    window.dispatchEvent(new CustomEvent(CONSENT_LAYER_EVENT, { detail: { visible: false, height: 0 } }))
    expect(frames.size).toBe(0)
  })

  it('never yields while its own dialog is open', async () => {
    region = { left: 16, top: 800, width: 358, height: 200 }
    const launcher = await renderWidget()
    expect(launcher).toHaveClass(...yieldClasses)

    fireEvent.click(launcher)
    expect(await screen.findByRole('dialog', { name: 'Send feedback' })).toBeInTheDocument()
    expect(launcher).toHaveAttribute('aria-expanded', 'true')
    fireEvent.scroll(window)
    flush()
    for (const name of [...yieldClasses, 'focus:opacity-100']) expect(launcher).not.toHaveClass(name)

    fireEvent.click(launcher)
    expect(launcher).toHaveAttribute('aria-expanded', 'false')
    expect(launcher).toHaveClass(...yieldClasses)
  })
})

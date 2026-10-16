import { useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BellPopover, POPOVER_MARGIN, POPOVER_MIN_SIDE_REM, placeBellPopover } from '@/features/calendar/components/AlertBell'
import { Modal } from '@/components/ui/Modal'
import type { BlockedKind, BlockedState } from '@/features/calendar/hooks/useCalendar'
import { FREE_EARNINGS_ALERT_LIMIT } from '@/lib/planLimits'

/**
 * BellPopover is a NON-MODAL popover (DESIGN_SYSTEM §4: z-overlay, no dialog role; the reasons are
 * in AlertBell.tsx's header). These cases pin its popover contract:
 *  - a group named by its title and described by its message — not a dialog or alertdialog;
 *  - it arms ONCE per popover: the calendar page hands it a new `onClose` on every render
 *    (lessons/frontend-dialog-trap-arms-once-per-open.md);
 *  - Escape closes without letting a native <dialog> beneath close too;
 *  - every close path returns focus to the bell; Tab out resumes the page's order at the bell;
 *  - raised from a bell inside an open <dialog>, it renders inside that dialog's top layer.
 */

const ANCHOR = { left: 100, top: 100, bottom: 128, right: 128, width: 28, height: 28 } as DOMRect

function blockedFor(kind: BlockedKind, trigger: HTMLElement | null, message = ''): BlockedState {
  return { kind, ticker: 'AAPL', message, anchor: ANCHOR, trigger }
}

/** The page's shape: a bell, and a popover whose onClose is a NEW inline arrow on every render. */
function Page({ kind, message, tick = 0 }: { kind: BlockedKind; message?: string; tick?: number }) {
  const [blocked, setBlocked] = useState<BlockedState | null>(null)
  return (
    <>
      <button type="button" onClick={(e) => setBlocked(blockedFor(kind, e.currentTarget, message))}>
        Bell {tick}
      </button>
      <button type="button">Next on page</button>
      {blocked && <BellPopover blocked={blocked} onClose={() => setBlocked(null)} />}
    </>
  )
}

const openFromBell = async (kind: BlockedKind, message?: string) => {
  const user = userEvent.setup()
  const utils = render(<Page kind={kind} message={message} />)
  const bell = screen.getByRole('button', { name: /^Bell/ })
  await user.click(bell)
  return { user, bell, ...utils }
}

describe('BellPopover', () => {
  afterEach(() => {
    document.querySelectorAll('dialog').forEach((d) => d.remove())
  })

  it('is a labelled, described group on the overlay layer — never a dialog', async () => {
    await openFromBell('signin')
    const group = screen.getByRole('group', { name: 'Sign in to set earnings alerts' })
    expect(group).toHaveAccessibleDescription(
      `Sign in to get an email the morning a company reports. Free includes ${FREE_EARNINGS_ALERT_LIMIT} companies.`,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(group.parentElement).toHaveClass('z-overlay')
    expect(group).toHaveClass('dark:shadow-none')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Sign in' }))
  })

  // The account action follows the one access decision (features/marketing/lib/access.ts): while
  // registration is invite-only (the default, and the fail-closed answer), /register would refuse the
  // sign-up, so the prompt offers the invite; only a public mode offers the free account (audit CAL-07).
  it.each([
    ['invite (the default)', 'Request an invite', '/waitlist', undefined],
    ['invite', 'Request an invite', '/waitlist', 'invite'],
    ['public', 'Create a free account', '/register', 'public'],
  ] as const)('under %s mode the signed-out prompt offers "%s" to %s', (_mode, label, href, accessMode) => {
    const bell = document.createElement('button')
    document.body.appendChild(bell)
    try {
      render(<BellPopover blocked={blockedFor('signin', bell)} accessMode={accessMode} onClose={() => {}} />)
      expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
      expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href)
      expect(screen.queryByRole('link', { name: /create account/i })).not.toBeInTheDocument()
    } finally {
      bell.remove()
    }
  })

  it('announces the async error as an alert with the API message verbatim — no alertdialog role', async () => {
    await openFromBell('error', 'Pro includes 50 earnings alerts.')
    const group = screen.getByRole('group', { name: 'Alert not enabled for AAPL' })
    expect(screen.getByRole('alert')).toHaveTextContent('Alert not enabled for AAPL' + 'Pro includes 50 earnings alerts.')
    // Focus moving in can cut the alert's speech off; the description keeps the message reachable.
    expect(group).toHaveAccessibleDescription('Pro includes 50 earnings alerts.')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Dismiss' }))
  })

  it('arms once: a parent re-render with a new onClose leaves focus where the user put it', async () => {
    const { rerender, user, bell } = await openFromBell('upsell', 'Free includes earnings alerts for 3 companies.')
    const notNow = screen.getByRole('button', { name: 'Not now' })
    notNow.focus()
    rerender(<Page kind="upsell" tick={1} />)
    rerender(<Page kind="upsell" tick={2} />)
    expect(document.activeElement).toBe(notNow)

    // …and it still closes through the latest onClose, back to the bell.
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('Escape closes, is consumed (a native <dialog> beneath stays open) and returns focus to the bell', async () => {
    const { bell } = await openFromBell('signin')
    const pageListener = vi.fn()
    document.addEventListener('keydown', pageListener)
    try {
      const notCancelled = fireEvent.keyDown(document.activeElement as Element, { key: 'Escape' })
      expect(notCancelled).toBe(false) // preventDefault: the browser fires no dialog cancel
      expect(pageListener).not.toHaveBeenCalled() // stopPropagation: nothing beneath sees it
    } finally {
      document.removeEventListener('keydown', pageListener)
    }
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('leaves Escape to an upper modal when an async error arrives behind it', () => {
    function PageWithDelayedError({ failed }: { failed: boolean }) {
      const [open, setOpen] = useState(false)
      const [dismissed, setDismissed] = useState(false)
      return (
        <>
          <button onClick={() => setOpen(true)}>Open feedback</button>
          {failed && !dismissed && (
            <BellPopover blocked={blockedFor('error', null, 'Alert unavailable')} onClose={() => setDismissed(true)} />
          )}
          <Modal open={open} onClose={() => setOpen(false)} ariaLabel="Feedback">
            <textarea aria-label="Feedback message" />
          </Modal>
        </>
      )
    }

    const view = render(<PageWithDelayedError failed={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open feedback' }))
    const message = screen.getByRole('textbox', { name: 'Feedback message' })
    expect(message).toHaveFocus()
    view.rerender(<PageWithDelayedError failed />)
    const popover = screen.getByRole('group', { name: 'Alert not enabled for AAPL' })
    expect(message).toHaveFocus()

    fireEvent.keyDown(message, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Feedback' })).not.toBeInTheDocument()
    expect(popover).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('button', { name: 'Dismiss' }), { key: 'Escape' })
    expect(popover).not.toBeInTheDocument()
  })

  it.each([
    ['upsell', 'Not now'],
    ['error', 'Dismiss'],
  ] as const)('the %s popover’s %s button returns focus to the bell', async (kind, label) => {
    const { user, bell } = await openFromBell(kind, 'message')
    await user.click(screen.getByRole('button', { name: label }))
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('an outside click closes it and returns focus to the bell; a click on its own text does not', async () => {
    const { user, bell } = await openFromBell('signin')
    await user.click(screen.getByText(/the morning a company reports/i))
    const group = screen.getByRole('group')
    await user.click(group.parentElement as HTMLElement)
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('does not steal focus from a user who moved on while the request was pending', () => {
    const pageBell = document.createElement('button')
    const elsewhere = document.createElement('button')
    document.body.append(pageBell, elsewhere)
    try {
      elsewhere.focus()
      render(<BellPopover blocked={blockedFor('error', pageBell, 'Try again later.')} onClose={() => {}} />)
      expect(document.activeElement).toBe(elsewhere)
      expect(screen.getByRole('alert')).toHaveTextContent('Try again later.') // still announced
      cleanup()
      expect(document.activeElement).toBe(elsewhere) // closing does not pull them back either
    } finally {
      pageBell.remove()
      elsewhere.remove()
    }
  })

  it('moves focus without scrolling the page, in and back out', async () => {
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    try {
      const { user } = await openFromBell('signin')
      expect(focus).toHaveBeenLastCalledWith({ preventScroll: true }) // into the first action
      await user.keyboard('{Escape}')
      expect(focus).toHaveBeenLastCalledWith({ preventScroll: true }) // back to the bell
    } finally {
      focus.mockRestore()
    }
  })

  it('closes quietly when its bell is gone (row unmounted)', async () => {
    const pageBell = document.createElement('button')
    document.body.appendChild(pageBell)
    render(<BellPopover blocked={blockedFor('signin', pageBell)} onClose={() => {}} />)
    pageBell.remove()
    expect(() => cleanup()).not.toThrow()
  })

  it('closes once a scroll moves its bell (it would detach) or on resize, but not on its own scroll', async () => {
    const { user, bell } = await openFromBell('signin')
    const rect = vi.spyOn(bell, 'getBoundingClientRect')
    try {
      fireEvent.scroll(screen.getByRole('group'))
      expect(screen.getByRole('group')).toBeInTheDocument()

      rect.mockReturnValue({ ...ANCHOR, top: ANCHOR.top - 120 } as DOMRect) // the page scrolled the bell away
      fireEvent.scroll(window)
      expect(screen.queryByRole('group')).not.toBeInTheDocument()
      expect(document.activeElement).toBe(bell)

      // Scroll does not bubble: an ancestor scroller (the day dialog's list) is caught in capture.
      rect.mockReturnValue(ANCHOR)
      await user.click(bell)
      rect.mockReturnValue({ ...ANCHOR, top: ANCHOR.top + 40 } as DOMRect)
      fireEvent.scroll(bell.parentElement as HTMLElement)
      expect(screen.queryByRole('group')).not.toBeInTheDocument()

      rect.mockReturnValue(ANCHOR)
      await user.click(bell)
      fireEvent(window, new Event('resize'))
      expect(screen.queryByRole('group')).not.toBeInTheDocument()
    } finally {
      rect.mockRestore()
    }
  })

  it('stays open through a scroll that leaves its bell in place (the page behind the fixed day dialog)', async () => {
    await openFromBell('signin')
    fireEvent.scroll(window) // the bell's rect is unchanged
    expect(screen.getByRole('group')).toBeInTheDocument()
  })

  it('Tab past the last action resumes at the bell (the browser moves on); Shift+Tab before the first lands on it', async () => {
    const { user, bell } = await openFromBell('signin')
    const last = screen.getByRole('link', { name: 'Request an invite' })
    last.focus()
    // Not prevented: with focus on the bell, the browser's own Tab moves to what follows it.
    expect(fireEvent.keyDown(last, { key: 'Tab' })).toBe(true)
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)

    await user.click(bell)
    const first = screen.getByRole('link', { name: 'Sign in' })
    expect(document.activeElement).toBe(first)
    expect(fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })).toBe(false)
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('Tab between its own actions stays inside', async () => {
    await openFromBell('signin')
    const first = screen.getByRole('link', { name: 'Sign in' })
    expect(fireEvent.keyDown(first, { key: 'Tab' })).toBe(true)
    expect(screen.getByRole('group')).toBeInTheDocument()
  })

  it('Shift+Tab from the panel itself (focused by a click on its text) also leaves onto the bell', async () => {
    const { bell } = await openFromBell('signin')
    const group = screen.getByRole('group')
    group.focus()
    expect(fireEvent.keyDown(group, { key: 'Tab', shiftKey: true })).toBe(false)
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(bell)
  })

  it('raised from a bell inside an open <dialog>, it renders inside that dialog', () => {
    const dialog = document.createElement('dialog')
    dialog.setAttribute('open', '')
    const bell = document.createElement('button')
    dialog.appendChild(bell)
    document.body.appendChild(dialog)
    act(() => {
      render(<BellPopover blocked={blockedFor('signin', bell)} onClose={() => {}} />)
    })
    expect(dialog).toContainElement(screen.getByRole('group', { name: 'Sign in to set earnings alerts' }))
  })

  it('an error that arrives after a day dialog opened renders inside that dialog, not inert beneath it', () => {
    // The toggle failed for a bell on the page; by the time the error lands the user opened a day.
    const pageBell = document.createElement('button')
    document.body.appendChild(pageBell)
    const dialog = document.createElement('dialog')
    dialog.setAttribute('open', '')
    document.body.appendChild(dialog)
    try {
      act(() => {
        render(<BellPopover blocked={blockedFor('error', pageBell, 'Try again later.')} onClose={() => {}} />)
      })
      expect(dialog).toContainElement(screen.getByRole('group', { name: 'Alert not enabled for AAPL' }))
    } finally {
      pageBell.remove()
    }
  })

  it('closes with the day dialog it lives in (a close request that is not a key, e.g. Android back)', () => {
    const dialog = document.createElement('dialog')
    dialog.setAttribute('open', '')
    const bell = document.createElement('button')
    dialog.appendChild(bell)
    document.body.appendChild(dialog)
    const onClose = vi.fn()
    act(() => {
      render(<BellPopover blocked={blockedFor('signin', bell)} onClose={onClose} />)
    })
    expect(dialog).toContainElement(screen.getByRole('group'))
    act(() => {
      dialog.dispatchEvent(new Event('cancel'))
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('keeps one host for its life: a parent re-render after a dialog opened does not re-mount it', async () => {
    const { rerender } = await openFromBell('signin')
    const create = screen.getByRole('link', { name: 'Request an invite' })
    create.focus()
    const dialog = document.createElement('dialog')
    dialog.setAttribute('open', '')
    document.body.appendChild(dialog)
    rerender(<Page kind="signin" tick={1} />)
    expect(dialog).not.toContainElement(screen.getByRole('group'))
    expect(document.activeElement).toBe(create)
  })

  it('keeps focus inside the day dialog when its bell outside it is inert', () => {
    const pageBell = document.createElement('button')
    const inertFocus = vi.spyOn(pageBell, 'focus').mockImplementation(() => {}) // jsdom has no inert
    const dialog = document.createElement('dialog')
    dialog.setAttribute('open', '')
    const dialogClose = document.createElement('button')
    dialog.appendChild(dialogClose)
    document.body.append(pageBell, dialog)
    try {
      act(() => {
        render(<BellPopover blocked={blockedFor('error', pageBell, 'Try again later.')} onClose={() => {}} />)
      })
      expect(dialog).toContainElement(document.activeElement as HTMLElement) // Dismiss, in the dialog
      cleanup()
      expect(document.activeElement).toBe(dialogClose)
    } finally {
      inertFocus.mockRestore()
      pageBell.remove()
    }
  })

  it('with no dialog open it renders under <body>', async () => {
    await openFromBell('signin')
    const group = screen.getByRole('group')
    expect(group.closest('dialog')).toBeNull()
    expect(document.body).toContainElement(group)
  })
})

/**
 * Placement (the 2026-10-14 capture review of #1301): at 200% text the sign-in popover was 300x808px,
 * placed below the bell at y=625 from a guessed 190px height, and ran about 590px past the bottom of the
 * 844px screen. It is now placed from its measured height, inside what the reader can see.
 */
describe('BellPopover placement', () => {
  // The 390x844 phone at 200% text: a bell in the day dialog's first row, the popover 366px wide.
  const PHONE = { left: 0, top: 0, width: 390, height: 844 }
  const BELL = { left: 290, top: 534, bottom: 622, width: 88 }
  const inside = (box: { left: number; top: number; maxHeight: number }, width: number, area = PHONE) => {
    expect(box.left).toBeGreaterThanOrEqual(area.left + POPOVER_MARGIN)
    expect(box.left + width).toBeLessThanOrEqual(area.left + area.width - POPOVER_MARGIN)
    expect(box.top).toBeGreaterThanOrEqual(area.top + POPOVER_MARGIN)
    expect(box.top + box.maxHeight).toBeLessThanOrEqual(area.top + area.height - POPOVER_MARGIN)
  }

  it('goes below the bell when it fits there whole', () => {
    const box = placeBellPopover({ left: 100, top: 100, bottom: 128, width: 28 }, { width: 300, height: 168 }, PHONE)
    expect(box.top).toBe(136)
    inside(box, 300)
  })

  it('goes above the bell when only that side holds it whole, capped at its own height so it never reaches over the bell', () => {
    const box = placeBellPopover(BELL, { width: 366, height: 400 }, PHONE)
    expect(box.top + 400).toBe(BELL.top - 8)
    expect(box.maxHeight).toBe(400)
    inside(box, 366)
  })

  it('too tall for either side, it takes the roomier one, capped there, and never covers the bell', () => {
    const box = placeBellPopover(BELL, { width: 366, height: 808 }, PHONE)
    inside(box, 366)
    expect(box.top + box.maxHeight).toBeLessThanOrEqual(BELL.top - 8) // above: 514px of room against 202 below
    expect(box.maxHeight).toBe(BELL.top - 8 - POPOVER_MARGIN)
  })

  it('stays inside the visible area when its bell is out of view (below it or above it)', () => {
    inside(placeBellPopover({ left: 290, top: 1100, bottom: 1188, width: 88 }, { width: 366, height: 500 }, PHONE), 366)
    inside(placeBellPopover({ left: 290, top: -300, bottom: -212, width: 88 }, { width: 366, height: 500 }, PHONE), 366)
  })

  it('too tall for either side with more room below, it goes below, capped there, clear of the bell', () => {
    // 536px below a high bell and 180px above it; the popover needs 808px.
    const HIGH = { left: 290, top: 200, bottom: 288, width: 88 }
    const box = placeBellPopover(HIGH, { width: 366, height: 808 }, PHONE)
    expect(box.top).toBe(HIGH.bottom + 8)
    expect(box.maxHeight).toBe(844 - POPOVER_MARGIN - (HIGH.bottom + 8))
    inside(box, 366)
  })

  it('when neither side offers 6rem, it spans the visible height over its bell and scrolls inside', () => {
    // A landscape phone with the keyboard up: 260px of height, an 88px bell in the middle, 66px on either side. A
    // side that short shows little more than the panel's 2rem of padding, so the popover takes the whole height,
    // over the bell (the one placement that covers it), and scrolls inside.
    const SHORT = { left: 0, top: 0, width: 390, height: 260 }
    const MID = { left: 290, top: 86, bottom: 174, width: 88 }
    const box = placeBellPopover(MID, { width: 366, height: 400 }, SHORT)
    expect(box).toMatchObject({ top: POPOVER_MARGIN, maxHeight: 260 - 2 * POPOVER_MARGIN })
    inside(box, 366, SHORT)
    expect(box.top < MID.top && box.top + box.maxHeight > MID.bottom).toBe(true)
  })

  it("the 6rem is the reader's: 136px a side is the roomier side at the default size and the whole height at 200% text", () => {
    const AREA = { left: 0, top: 0, width: 390, height: 400 }
    const MID = { left: 290, top: 156, bottom: 244, width: 88 } // 136px on either side
    // A tie goes below.
    expect(placeBellPopover(MID, { width: 366, height: 600 }, AREA, POPOVER_MIN_SIDE_REM * 16)).toMatchObject({ top: 252, maxHeight: 136 })
    expect(placeBellPopover(MID, { width: 366, height: 600 }, AREA, POPOVER_MIN_SIDE_REM * 32)).toMatchObject({
      top: POPOVER_MARGIN,
      maxHeight: 400 - 2 * POPOVER_MARGIN,
    })
  })

  it('places inside the visible area, which on a page wider than the phone is offset in the layout viewport', () => {
    // Chromium widened this page's layout viewport to 552x1195 and shows 390x844 of it from (24, 25).
    const area = { left: 24, top: 25, width: 390, height: 844 }
    const box = placeBellPopover({ left: 314, top: 559, bottom: 647, width: 88 }, { width: 366, height: 808 }, area)
    inside(box, 366, area)
  })

  /** Renders the popover with its panel measuring `height` tall, and restores jsdom after. */
  const renderMeasured = (height: number, anchor: DOMRect, run: (group: HTMLElement) => void) => {
    const scroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollHeight')
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
      configurable: true,
      get(this: HTMLElement) {
        return this.getAttribute('role') === 'group' ? height : 0
      },
    })
    const bell = document.createElement('button')
    document.body.appendChild(bell)
    try {
      render(<BellPopover blocked={{ kind: 'signin', ticker: 'AAPL', message: '', anchor, trigger: bell }} onClose={() => {}} />)
      run(screen.getByRole('group', { name: 'Sign in to set earnings alerts' }))
    } finally {
      bell.remove()
      if (scroll) Object.defineProperty(HTMLElement.prototype, 'scrollHeight', scroll)
      else delete (HTMLElement.prototype as { scrollHeight?: number }).scrollHeight
    }
  }

  it('renders from the height it measured: above the bell by that height, or capped on the roomier side', () => {
    // jsdom's window is 1024x768: a bell at y 600-628 has 120px below it and 580 above.
    const LOW = { left: 100, top: 600, bottom: 628, right: 128, width: 28, height: 28 } as DOMRect
    renderMeasured(400, LOW, (group) => {
      expect(group.style.top).toBe(`${600 - 8 - 400}px`)
    })
    cleanup()
    renderMeasured(2000, LOW, (group) => {
      expect(group).toHaveClass('overflow-y-auto')
      expect(group.style.top).toBe(`${POPOVER_MARGIN}px`)
      expect(group.style.maxHeight).toBe(`${600 - 8 - POPOVER_MARGIN}px`)
    })
  })

  it('measures its painted box rounded up, so placed above, a fractional height is neither a pixel short nor scrolls', () => {
    // A browser rounds scrollHeight to a whole pixel, while the box it paints can be 400.4px tall.
    const LOW = { left: 100, top: 600, bottom: 628, right: 128, width: 28, height: 28 } as DOMRect
    const own = Element.prototype.getBoundingClientRect
    const rect = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      return this.getAttribute('role') === 'group' ? ({ height: 400.4 } as DOMRect) : own.call(this)
    })
    try {
      renderMeasured(400, LOW, (group) => {
        expect(group.style.top).toBe(`${600 - 8 - 401}px`)
        expect(group.style.maxHeight).toBe('401px')
      })
    } finally {
      rect.mockRestore()
    }
  })

  it('scrolls its own panel, never the page, to the first action once capped, so a keyboard reader sees that focus', () => {
    // The Free cap's upsell at 200% text, above a low bell: 611px of panel in the 580px above it, so it is capped and
    // its actions end below the scrollport (Codex's P2 on #1369). jsdom lays nothing out, so the panel's box, its
    // content and client heights and the first action's box are given; the panel's scrollTop is what the code sets.
    const LOW = { left: 100, top: 600, bottom: 628, right: 128, width: 28, height: 28 } as DOMRect
    const stubs: Array<[object, string, PropertyDescriptor | undefined]> = []
    const stub = (proto: object, prop: string, get: (el: HTMLElement) => number) => {
      stubs.push([proto, prop, Object.getOwnPropertyDescriptor(proto, prop)])
      Object.defineProperty(proto, prop, {
        configurable: true,
        get(this: HTMLElement) {
          return get(this)
        },
      })
    }
    const isPanel = (el: Element) => el.getAttribute('role') === 'group'
    // The panel's box follows its inline top and cap: 611px (609 of content and two 1px borders) until the cap lands,
    // so the open effect, which focuses before the cap, finds the action in view and the cap's effect does not.
    const panelBox = (el: HTMLElement) => {
      const top = parseFloat(el.style.top) || 0
      const height = el.style.maxHeight ? Math.min(611, parseFloat(el.style.maxHeight)) : 611
      return { top, bottom: top + height, height }
    }
    let actionOffset = 554 // the first action's top, from the panel's top edge
    stub(HTMLElement.prototype, 'scrollHeight', (el) => (isPanel(el) ? 609 : 0))
    stub(HTMLElement.prototype, 'offsetHeight', (el) => (isPanel(el) ? panelBox(el).height : 0))
    stub(Element.prototype, 'clientHeight', (el) => (isPanel(el) ? panelBox(el).height - 2 : 0))
    stub(Element.prototype, 'clientTop', (el) => (isPanel(el) ? 1 : 0))
    const own = Element.prototype.getBoundingClientRect
    const rect = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      if (isPanel(this)) return panelBox(this as HTMLElement) as DOMRect
      const panel = this.closest<HTMLElement>('[role="group"]')
      if (panel && this.textContent === 'Upgrade to Pro') {
        // Its box moves with the panel, and up as the panel scrolls, as a browser's does.
        const top = panelBox(panel).top + actionOffset - panel.scrollTop
        return { top, bottom: top + 36, height: 36 } as DOMRect
      }
      return own.call(this)
    })
    const bell = document.createElement('button')
    document.body.appendChild(bell)
    const upsell = { kind: 'upsell' as const, ticker: 'AAPL', message: 'Free includes earnings alerts for 3 companies.', anchor: LOW, trigger: bell }
    try {
      render(<BellPopover blocked={upsell} onClose={() => {}} />)
      const group = screen.getByRole('group', { name: 'Free includes 3 earnings alerts' })
      expect(group.style.maxHeight).toBe('580px') // capped on the roomier side, above the bell
      expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Upgrade to Pro' }))
      // The scrollport ends at 13 + 578 = 591px and the action at 602px: the panel scrolls the 11px between.
      expect(group.scrollTop).toBe(11)
      cleanup()
      // An action already in view leaves the panel where it is.
      actionOffset = 288
      render(<BellPopover blocked={{ ...upsell }} onClose={() => {}} />)
      expect(screen.getByRole('group', { name: 'Free includes 3 earnings alerts' }).scrollTop).toBe(0)
    } finally {
      bell.remove()
      rect.mockRestore()
      for (const [proto, prop, desc] of stubs.reverse()) {
        if (desc) Object.defineProperty(proto, prop, desc)
        else delete (proto as Record<string, unknown>)[prop]
      }
    }
  })

  it('reads the visible area from window.visualViewport, not the layout viewport a wide page stretches', () => {
    // The phone shows 390x844 of a layout viewport stretched past it (jsdom's window stands for that one).
    const own = Object.getOwnPropertyDescriptor(window, 'visualViewport')
    Object.defineProperty(window, 'visualViewport', { configurable: true, value: { offsetLeft: 24, offsetTop: 25, width: 390, height: 844 } })
    try {
      renderMeasured(2000, { left: 314, top: 559, bottom: 647, right: 402, width: 88, height: 88 } as DOMRect, (group) => {
        const left = parseFloat(group.style.left)
        const top = parseFloat(group.style.top)
        expect(left).toBeGreaterThanOrEqual(24 + POPOVER_MARGIN)
        expect(left + parseFloat(group.style.width)).toBeLessThanOrEqual(24 + 390 - POPOVER_MARGIN)
        expect(top).toBeGreaterThanOrEqual(25 + POPOVER_MARGIN)
        expect(top + parseFloat(group.style.maxHeight)).toBeLessThanOrEqual(25 + 844 - POPOVER_MARGIN)
      })
    } finally {
      if (own) Object.defineProperty(window, 'visualViewport', own)
      else delete (window as { visualViewport?: unknown }).visualViewport
    }
  })

  it("reads 6rem from the reader's text size: at a 32px root, 136px a side is too short and it spans the visible height", () => {
    // A 400px visible area with the bell in the middle: 136px above and below it.
    const own = Object.getOwnPropertyDescriptor(window, 'visualViewport')
    Object.defineProperty(window, 'visualViewport', { configurable: true, value: { offsetLeft: 0, offsetTop: 0, width: 390, height: 400 } })
    const MID = { left: 290, top: 156, bottom: 244, right: 378, width: 88, height: 88 } as DOMRect
    try {
      renderMeasured(600, MID, (group) => {
        expect([group.style.top, group.style.maxHeight]).toEqual(['252px', '136px']) // the default size: the roomier side
      })
      cleanup()
      document.documentElement.style.fontSize = '32px'
      renderMeasured(600, MID, (group) => {
        expect([group.style.top, group.style.maxHeight]).toEqual([`${POPOVER_MARGIN}px`, `${400 - 2 * POPOVER_MARGIN}px`])
      })
    } finally {
      document.documentElement.style.fontSize = ''
      if (own) Object.defineProperty(window, 'visualViewport', own)
      else delete (window as { visualViewport?: unknown }).visualViewport
    }
  })
})

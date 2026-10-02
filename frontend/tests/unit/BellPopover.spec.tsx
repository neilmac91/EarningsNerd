import { useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BellPopover } from '@/features/calendar/components/AlertBell'
import type { BlockedKind, BlockedState } from '@/features/calendar/hooks/useCalendar'

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
    expect(group).toHaveAccessibleDescription(/free once you sign in/i)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(group.parentElement).toHaveClass('z-overlay')
    expect(group).toHaveClass('dark:shadow-none')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Sign in' }))
  })

  it('announces the async error as an alert with the API message verbatim — no alertdialog role', async () => {
    await openFromBell('error', 'Pro includes 50 earnings alerts.')
    const group = screen.getByRole('group', { name: 'Alert not enabled' })
    expect(screen.getByRole('alert')).toHaveTextContent('Alert not enabled' + 'Pro includes 50 earnings alerts.')
    expect(group).not.toHaveAttribute('aria-describedby') // the alert already reads it; no double read
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
    await user.click(screen.getByText(/free once you sign in/i))
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
    const last = screen.getByRole('link', { name: 'Create account' })
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
      expect(dialog).toContainElement(screen.getByRole('group', { name: 'Alert not enabled' }))
    } finally {
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

import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Modal, ModalBody, ModalHeader } from '@/components/ui/Modal'

/**
 * ui/Modal is the one dialog primitive (DESIGN_SYSTEM §4, gated by dialogAllowlist.spec.ts). This
 * spec pins its keyboard contract — focus moves in, Tab wraps, Escape closes, focus returns to the
 * opener — and two regressions the design-v3 review found:
 *  - the trap effect listed `onClose` in its dependencies, so a parent that re-rendered while the
 *    dialog was open (the admin invite row's 1 s resend cooldown, with an inline `onClose`) re-ran
 *    it every render, refocused the ✕ and lost the opener. The trap must arm once per open.
 *    lessons/frontend-dialog-trap-arms-once-per-open.md
 *  - opened over the mobile copilot sheet, whose document-capture trap armed first, Tab left the
 *    dialog and one Escape closed both layers. The top dialog owns the keyboard.
 *    lessons/frontend-top-dialog-owns-the-keyboard.md
 */

/** Opens on click; `tick` forces a parent re-render that hands Modal a NEW inline onClose. */
function Host({ tick = 0, dismissible = true }: { tick?: number; dismissible?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open dialog
      </button>
      <Modal open={open} onClose={() => setOpen(false)} labelledBy="host-title" dismissible={dismissible}>
        <ModalHeader id="host-title" onClose={() => setOpen(false)}>
          Host dialog {tick}
        </ModalHeader>
        <ModalBody>
          <button type="button">First action</button>
          <button type="button">Last action</button>
        </ModalBody>
      </Modal>
    </>
  )
}

/** Two stacked dialogs, each driven by a prop, so the lower one can close while the upper stays open. */
function TwoLayers({ lower, upper }: { lower: boolean; upper: boolean }) {
  return (
    <>
      <button type="button">Page button</button>
      <Modal open={lower} onClose={() => {}} ariaLabel="Lower dialog">
        <ModalBody>
          <button type="button">Lower action</button>
        </ModalBody>
      </Modal>
      <Modal open={upper} onClose={() => {}} ariaLabel="Upper dialog">
        <ModalBody>
          <button type="button">Upper action</button>
        </ModalBody>
      </Modal>
    </>
  )
}

describe('ui/Modal keyboard contract', () => {
  // jsdom lays nothing out, so getClientRects() is empty and the trap would treat every focusable as
  // hidden. Give elements one rect so the Tab cycle sees them as rendered (as a browser would).
  let rects: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    rects = vi
      .spyOn(HTMLElement.prototype, 'getClientRects')
      .mockReturnValue([{}] as unknown as DOMRectList)
  })
  afterEach(() => rects.mockRestore())

  const openFromOpener = async () => {
    const user = userEvent.setup()
    const opener = screen.getByRole('button', { name: 'Open dialog' })
    await user.click(opener)
    return { user, opener, dialog: screen.getByRole('dialog', { name: /host dialog/i }) }
  }

  it('moves focus into the labelled panel on open and locks body scroll', async () => {
    render(<Host />)
    const { dialog } = await openFromOpener()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }))
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('wraps Tab from the last focusable to the first, and Shift-Tab back', async () => {
    render(<Host />)
    await openFromOpener()
    const close = screen.getByRole('button', { name: 'Close' })
    const last = screen.getByRole('button', { name: 'Last action' })
    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(document.activeElement).toBe(close)
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('closes on Escape, restores body scroll and returns focus to the opener', async () => {
    render(<Host />)
    const { user, opener } = await openFromOpener()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(opener)
  })

  it('ignores Escape and scrim clicks when not dismissible', async () => {
    render(<Host dismissible={false} />)
    const { user, dialog } = await openFromOpener()
    await user.keyboard('{Escape}')
    fireEvent.click(dialog.parentElement as HTMLElement)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('owns Tab and Escape over a trap that armed first (the copilot sheet beneath it)', async () => {
    // A document-capture trap shaped like useSheetFocusTrap: Escape closes the sheet, Tab pulls
    // focus back into it. It armed before the dialog opened, as the sheet does under UpgradeModal.
    const closeSheet = vi.fn()
    const sheetButton = document.createElement('button')
    document.body.appendChild(sheetButton)
    const sheetTrap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSheet()
      if (e.key === 'Tab') {
        e.preventDefault()
        sheetButton.focus()
      }
    }
    document.addEventListener('keydown', sheetTrap, true)
    try {
      render(<Host />)
      const { user } = await openFromOpener()
      const last = screen.getByRole('button', { name: 'Last action' })
      last.focus()
      fireEvent.keyDown(last, { key: 'Tab' })
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }))

      await user.keyboard('{Escape}')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(closeSheet).not.toHaveBeenCalled()
    } finally {
      document.removeEventListener('keydown', sheetTrap, true)
      sheetButton.remove()
    }
  })

  it('keeps the scroll lock and focus with the upper dialog when a lower one closes first', () => {
    const { rerender } = render(<TwoLayers lower={false} upper={false} />)
    screen.getByRole('button', { name: 'Page button' }).focus() // the lower dialog's opener
    rerender(<TwoLayers lower upper={false} />)
    rerender(<TwoLayers lower upper />)
    const upperAction = screen.getByRole('button', { name: 'Upper action' })
    expect(document.activeElement).toBe(upperAction)

    // The lower layer closes underneath (an event-driven dialog dismissing itself, say).
    rerender(<TwoLayers lower={false} upper />)
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.activeElement).toBe(upperAction)

    rerender(<TwoLayers lower={false} upper={false} />)
    expect(document.body.style.overflow).toBe('')
  })

  it('does not re-arm when the parent re-renders with a new inline onClose (regression)', async () => {
    const { rerender } = render(<Host tick={0} />)
    const { user, opener } = await openFromOpener()
    const last = screen.getByRole('button', { name: 'Last action' })
    last.focus()

    // A parent render while open (a cooldown tick, a refetch) must leave focus where the user put it.
    rerender(<Host tick={1} />)
    rerender(<Host tick={2} />)
    expect(screen.getByRole('dialog', { name: 'Host dialog 2' })).toBeInTheDocument()
    expect(document.activeElement).toBe(last)

    // …and the trap still remembers the real opener.
    await user.keyboard('{Escape}')
    expect(document.activeElement).toBe(opener)
  })
})

import { useRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSheetFocusTrap } from '@/features/filings/components/copilot/useSheetFocusTrap'

/**
 * The mobile copilot sheet's focus trap (AskCopilotRail standalone overlay, FilingWorkspace shell).
 * Pins the two behaviours it shares with ui/Modal:
 *  - it arms ONCE per activation: `onClose` is read through a ref, so a caller handing a new callback
 *    on each render cannot re-run the effect, return focus, re-capture an element inside the sheet
 *    as the restore target and refocus the first focusable.
 *    lessons/frontend-dialog-trap-arms-once-per-open.md
 *  - keys typed inside another aria-modal layer belong to that layer, not to the sheet beneath it.
 *    lessons/frontend-top-dialog-owns-the-keyboard.md
 */

function Sheet({ active, onClose, tick = 0 }: { active: boolean; onClose: () => void; tick?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useSheetFocusTrap({ active, containerRef: ref, onClose })
  return (
    <>
      <button type="button">Page button</button>
      <div ref={ref} role="dialog" aria-modal={active ? true : undefined} aria-label={`Sheet ${tick}`}>
        <button type="button">First</button>
        <button type="button">Last</button>
      </div>
    </>
  )
}

describe('useSheetFocusTrap', () => {
  // jsdom lays nothing out, so getClientRects() is empty and the trap would treat every focusable as
  // hidden. Give elements one rect so the Tab cycle sees them as rendered (as a browser would).
  let rects: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    rects = vi
      .spyOn(HTMLElement.prototype, 'getClientRects')
      .mockReturnValue([{}] as unknown as DOMRectList)
  })
  afterEach(() => rects.mockRestore())

  it('arms once per activation: a new onClose on re-render leaves focus put and the restore target intact', () => {
    const { rerender } = render(<Sheet active={false} onClose={() => {}} />)
    const pageButton = screen.getByRole('button', { name: 'Page button' })
    pageButton.focus() // the element focus returns to on deactivate

    rerender(<Sheet active onClose={() => {}} />)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'First' }))
    const last = screen.getByRole('button', { name: 'Last' })
    last.focus()

    // Parent renders while the sheet is open, each handing the hook a NEW callback.
    rerender(<Sheet active onClose={() => {}} tick={1} />)
    const latest = vi.fn()
    rerender(<Sheet active onClose={latest} tick={2} />)
    expect(screen.getByRole('dialog', { name: 'Sheet 2' })).toBeInTheDocument()
    expect(document.activeElement).toBe(last)

    // Escape reaches the LATEST callback, and deactivating returns focus to the real opener.
    fireEvent.keyDown(last, { key: 'Escape' })
    expect(latest).toHaveBeenCalledTimes(1)
    rerender(<Sheet active={false} onClose={latest} tick={2} />)
    expect(document.activeElement).toBe(pageButton)
  })

  it('still wraps Tab and pulls stray focus back into the sheet', () => {
    render(<Sheet active onClose={() => {}} />)
    const first = screen.getByRole('button', { name: 'First' })
    const last = screen.getByRole('button', { name: 'Last' })
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)

    const pageButton = screen.getByRole('button', { name: 'Page button' })
    pageButton.focus()
    fireEvent.keyDown(pageButton, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
  })

  it('leaves Tab and Escape to another aria-modal layer stacked over the sheet', () => {
    const onClose = vi.fn()
    render(<Sheet active onClose={onClose} />)
    // A modal layer that is not ui/Modal (so nothing stops its keys in window capture first), shaped
    // like SourceTrace's portalled source-detail sheet.
    const layer = document.createElement('div')
    layer.setAttribute('role', 'dialog')
    layer.setAttribute('aria-modal', 'true')
    const layerButton = document.createElement('button')
    layer.appendChild(layerButton)
    document.body.appendChild(layer)
    try {
      layerButton.focus()
      fireEvent.keyDown(layerButton, { key: 'Tab' })
      expect(document.activeElement).toBe(layerButton)
      fireEvent.keyDown(layerButton, { key: 'Escape' })
      expect(onClose).not.toHaveBeenCalled()
    } finally {
      layer.remove()
    }
  })
})

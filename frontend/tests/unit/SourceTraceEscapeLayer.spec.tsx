import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { Modal } from '@/components/ui/Modal'

/**
 * On a phone, SourceTrace's source-detail sheet can sit over the copilot sheet. The open panel is the
 * top layer, so Escape is its own: it closes the source sheet and stops there. Without that, the copilot
 * sheet's document-capture trap and the rail's window Escape listener both closed the copilot on the
 * same key (measured on a real build). lessons/frontend-top-dialog-owns-the-keyboard.md
 */

describe('SourceTrace owns Escape while its panel is open', () => {
  let matchMedia: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    // A touch device: the chip opens the bottom sheet rather than the hover popover.
    matchMedia = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(pointer: coarse)',
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          onchange: null,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    )
  })
  afterEach(() => matchMedia.mockRestore())

  it('closes the source sheet even when focus is in the lower copilot layer', () => {
    // Stand-ins for the copilot sheet's trap (document capture) and the rail's listener (window bubble).
    const trapBeneath = vi.fn()
    const railBeneath = vi.fn()
    document.addEventListener('keydown', trapBeneath, true)
    window.addEventListener('keydown', railBeneath)
    try {
      render(
        <>
          <div role="dialog" aria-modal="true" aria-label="Copilot">
            <button>Copilot action</button>
          </div>
          <SourceTrace url="https://www.sec.gov/x.htm" verified={false} />
        </>,
      )
      fireEvent.click(screen.getByRole('button', { name: /source/i }))
      const sheet = screen.getByRole('dialog', { name: 'Source detail' })
      fireEvent.keyDown(screen.getByRole('button', { name: 'Copilot action' }), { key: 'Escape' })

      expect(sheet).not.toBeInTheDocument()
      expect(trapBeneath).not.toHaveBeenCalled()
      expect(railBeneath).not.toHaveBeenCalled()
    } finally {
      document.removeEventListener('keydown', trapBeneath, true)
      window.removeEventListener('keydown', railBeneath)
    }
  })

  it('leaves Escape inside a modal opened above the source sheet to that modal', () => {
    function StackedLayers() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <SourceTrace url="https://www.sec.gov/x.htm" verified={false} />
          <button onClick={() => setOpen(true)}>Open another dialog</button>
          <Modal open={open} onClose={() => setOpen(false)} ariaLabel="Another dialog">
            <button>Nested action</button>
          </Modal>
        </>
      )
    }

    render(<StackedLayers />)
    fireEvent.click(screen.getByRole('button', { name: /source/i }))
    const source = screen.getByRole('dialog', { name: 'Source detail' })
    fireEvent.click(screen.getByRole('button', { name: 'Open another dialog' }))
    const upper = screen.getByRole('dialog', { name: 'Another dialog' })
    fireEvent.keyDown(screen.getByRole('button', { name: 'Nested action' }), { key: 'Escape' })

    expect(upper).not.toBeInTheDocument()
    expect(source).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('button', { name: 'Close source detail' }), { key: 'Escape' })
    expect(source).not.toBeInTheDocument()
  })

})

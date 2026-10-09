import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
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

/**
 * A fine pointer: the chip's hover/focus popover is no layer of its own. Below lg the research pane is
 * a modal sheet whose trap takes focus when a window narrows; a popover that was open on a page chip
 * (EN-03's layout-twin hand-off focuses one as the table hides) then waits out its close delay with
 * focus already in the sheet. Escape typed in the sheet is the sheet's: in CI the popover's
 * window-capture listener stopped it and the copilot sheet stayed open
 * (metrics-stacked-cards.spec.ts, "the research pane a metric chip opened").
 */
describe('the popover leaves Escape to a modal layer that holds focus but not its chip', () => {
  let matchMedia: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    vi.useFakeTimers()
    matchMedia = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: false, // a fine pointer: never '(pointer: coarse)'
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
  afterEach(() => {
    matchMedia.mockRestore()
    vi.useRealTimers()
  })

  const chip = () => screen.getByRole('button', { name: 'Source: Verified in filing' })
  const popover = () => screen.queryByRole('group', { name: 'Source detail' })
  function Page({ chipInSheet = false }: { chipInSheet?: boolean }) {
    const trace = <SourceTrace url="https://www.sec.gov/x.htm" verified sectionRef="Item 8" excerpt="Total net sales" />
    return (
      <FilingViewerProvider>
        {chipInSheet ? null : trace}
        <div role="dialog" aria-modal="true" aria-label="Ask this Filing">
          <button>Answer</button>
          {chipInSheet ? trace : null}
        </div>
      </FilingViewerProvider>
    )
  }
  function withListenersBeneath(run: (trap: ReturnType<typeof vi.fn>, rail: ReturnType<typeof vi.fn>) => void) {
    // Stand-ins for the copilot sheet's trap (document capture) and the rail's listener (window bubble).
    const trap = vi.fn()
    const rail = vi.fn()
    document.addEventListener('keydown', trap, true)
    window.addEventListener('keydown', rail)
    try {
      run(trap, rail)
    } finally {
      document.removeEventListener('keydown', trap, true)
      window.removeEventListener('keydown', rail)
    }
  }

  it('Escape in the copilot sheet reaches the sheet while a page chip’s popover is still closing', () => {
    withListenersBeneath((trap, rail) => {
      render(<Page />)
      act(() => chip().focus())
      expect(popover()).toBeInTheDocument()
      // The sheet's trap takes focus: the chip blurs and its popover waits out the close delay.
      act(() => screen.getByRole('button', { name: 'Answer' }).focus())
      expect(popover()).toBeInTheDocument()
      fireEvent.keyDown(screen.getByRole('button', { name: 'Answer' }), { key: 'Escape' })
      expect(trap).toHaveBeenCalledTimes(1)
      expect(rail).toHaveBeenCalledTimes(1)
      act(() => vi.runAllTimers())
      expect(popover()).not.toBeInTheDocument()
    })
  })

  it('a chip inside that layer keeps the key: Escape closes its popover alone', () => {
    withListenersBeneath((trap, rail) => {
      render(<Page chipInSheet />)
      act(() => chip().focus())
      expect(popover()).toBeInTheDocument()
      fireEvent.keyDown(chip(), { key: 'Escape' })
      expect(popover()).not.toBeInTheDocument()
      expect(trap).not.toHaveBeenCalled()
      expect(rail).not.toHaveBeenCalled()
    })
  })

  it('with no modal layer around the focus, the popover still owns Escape', () => {
    withListenersBeneath((trap, rail) => {
      render(
        <FilingViewerProvider>
          <SourceTrace url="https://www.sec.gov/x.htm" verified sectionRef="Item 8" excerpt="Total net sales" />
          <button>Elsewhere</button>
        </FilingViewerProvider>,
      )
      act(() => chip().focus())
      act(() => screen.getByRole('button', { name: 'Elsewhere' }).focus())
      expect(popover()).toBeInTheDocument()
      fireEvent.keyDown(screen.getByRole('button', { name: 'Elsewhere' }), { key: 'Escape' })
      expect(popover()).not.toBeInTheDocument()
      expect(trap).not.toHaveBeenCalled()
      expect(rail).not.toHaveBeenCalled()
    })
  })
})

import { describe, it, expect } from 'vitest'
import { createRef, useRef } from 'react'
import { act, render, screen, fireEvent } from '@testing-library/react'
import CopilotComposer, {
  type CopilotComposerHandle,
} from '@/features/filings/components/copilot/CopilotComposer'
import { rect, scrollBox, watchThePage } from './scrollBoxes'

function Harness() {
  const ref = useRef<CopilotComposerHandle>(null)
  return (
    <>
      <button type="button" onClick={() => ref.current?.prefill('Explain this excerpt: "Revenue rose 8%"')}>
        fill
      </button>
      <CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />
    </>
  )
}

describe('CopilotComposer prefill handle', () => {
  it('fills the textarea via the imperative handle (used by "Ask about this")', () => {
    render(<Harness />)
    const textarea = screen.getByLabelText(/ask about this filing/i) as HTMLTextAreaElement
    expect(textarea.value).toBe('')

    fireEvent.click(screen.getByRole('button', { name: 'fill' }))

    expect(textarea.value).toBe('Explain this excerpt: "Revenue rose 8%"')
  })
})

/**
 * The composer inside a column (its form's parent, as in the rail), on screen from 100 to 400px, with the shell that
 * draws the focus ring at 420 to 470px of the column's content: below the column's foot until the column scrolls. A box
 * around the column scrolls too, and the column runs past it (the page's own layout, as the desktop pane can before it
 * measures its top): the reveal stops at the column and never moves that box or the page.
 */
function renderInColumn({ shellTop = 420 }: { shellTop?: number } = {}) {
  const ref = createRef<CopilotComposerHandle>()
  render(
    <div data-testid="outer">
      <button type="button">elsewhere</button>
      <div data-testid="column">
        <CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />
      </div>
    </div>,
  )
  const field = screen.getByLabelText(/ask about this filing/i)
  const column = scrollBox(screen.getByTestId('column'), 100, 300)
  const outer = scrollBox(screen.getByTestId('outer'), 0, 200)
  const shell = field.closest('.scroll-mb-1') as HTMLElement
  shell.getBoundingClientRect = () => rect(shellTop - column.scrollTop, 50)
  return { ref, field, send: screen.getByRole('button', { name: /^send$/i }), shell, column, outer }
}

describe('CopilotComposer focus handles never move the page (E248)', () => {
  it("focus: the field takes focus without the browser's scroll, and the column alone brings the shell into view", () => {
    const page = watchThePage()
    try {
      const { ref, field, column, outer } = renderInColumn()
      ref.current?.focus()
      expect(document.activeElement).toBe(field)
      expect(page.focusOptions(field)).toEqual([{ preventScroll: true }])
      // The shell's foot (470px) to the column's foot (400px): 70px, the least distance, its top still inside.
      expect(column.writes).toEqual([70])
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })

  it('prefill: the same focus and reveal, with the text in and the caret at its end', () => {
    const page = watchThePage()
    try {
      const { ref, field, column, outer } = renderInColumn()
      act(() => ref.current?.prefill('Explain this excerpt'))
      const textarea = field as HTMLTextAreaElement
      expect(document.activeElement).toBe(field)
      expect(textarea.value).toBe('Explain this excerpt')
      expect(textarea.selectionStart).toBe('Explain this excerpt'.length)
      expect(page.focusOptions(field)).toEqual([{ preventScroll: true }])
      expect(column.writes).toEqual([70])
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })

  it('a shell already in view moves nothing, not even the box whose foot the column runs past', () => {
    const page = watchThePage()
    try {
      const { ref, field, column, outer } = renderInColumn({ shellTop: 300 })
      ref.current?.focus()
      expect(document.activeElement).toBe(field)
      expect(page.focusOptions(field)).toEqual([{ preventScroll: true }])
      expect(column.writes).toEqual([])
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })

  it('a shell above the column comes down to its top edge', () => {
    const page = watchThePage()
    try {
      const { ref, column, outer } = renderInColumn({ shellTop: 40 })
      // The column has been scrolled 100px, so the shell's content at 140px shows at 40px, above the column's top.
      Object.defineProperty(screen.getByTestId('column'), 'scrollTop', { configurable: true, writable: true, value: 100 })
      ref.current?.focus()
      expect(screen.getByTestId('column').scrollTop).toBe(40)
      expect(column.writes).toEqual([])
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })
})

describe('CopilotComposer revealFocus handle', () => {
  it("brings the shell that draws the focus ring to the column's nearest edge, only while focus is inside it, never the page", () => {
    const page = watchThePage()
    try {
      const { ref, field, send, shell, column, outer } = renderInColumn()

      // Focus outside the composer: nothing moves.
      screen.getByRole('button', { name: 'elsewhere' }).focus()
      ref.current?.revealFocus()
      expect(column.writes).toEqual([])

      // Focus in the field, then on Send: each time the shell around both comes to the column's foot. Not the form,
      // whose privacy note would push the conversation off a short sheet; scroll-mb-1 leaves room below the shell for
      // the 3px ring.
      expect(shell.tagName).not.toBe('FORM')
      for (const control of [field, send]) {
        control.focus()
        column.reset()
        ref.current?.revealFocus()
        expect(column.writes).toEqual([70])
        // Now in view: a second reveal moves nothing.
        ref.current?.revealFocus()
        expect(column.writes).toEqual([70])
      }
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })
})

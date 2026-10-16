import { describe, it, expect, vi } from 'vitest'
import { createRef, useRef } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import CopilotComposer, {
  type CopilotComposerHandle,
} from '@/features/filings/components/copilot/CopilotComposer'

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

describe('CopilotComposer revealFocus handle', () => {
  it('scrolls the shell that draws the focus ring to the nearest edge, and only while focus is inside it', () => {
    // jsdom has no scrollIntoView; record each call's element and options.
    const calls: { el: Element; arg: unknown }[] = []
    const jsdomScrollIntoView = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = vi.fn(function (this: Element, arg?: boolean | ScrollIntoViewOptions) {
      calls.push({ el: this, arg })
    })
    try {
      const ref = createRef<CopilotComposerHandle>()
      render(
        <>
          <button type="button">elsewhere</button>
          <CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />
        </>,
      )
      const field = screen.getByLabelText(/ask about this filing/i)
      const send = screen.getByRole('button', { name: /^send$/i })

      // Focus outside the composer: nothing moves.
      screen.getByRole('button', { name: 'elsewhere' }).focus()
      ref.current?.revealFocus()
      expect(calls).toEqual([])

      // Focus in the field, then on Send: each time the shell around both comes to the nearest edge. Not the form,
      // whose privacy note would push the conversation off a short sheet; scroll-mb-1 leaves room below it for the 3px ring.
      for (const control of [field, send]) {
        control.focus()
        ref.current?.revealFocus()
      }
      expect(calls).toHaveLength(2)
      for (const { el, arg } of calls) {
        expect(arg).toEqual({ block: 'nearest' })
        expect(el.contains(field) && el.contains(send)).toBe(true)
        expect(el.tagName).not.toBe('FORM')
        expect(el.classList.contains('scroll-mb-1')).toBe(true)
      }
    } finally {
      Element.prototype.scrollIntoView = jsdomScrollIntoView
    }
  })
})

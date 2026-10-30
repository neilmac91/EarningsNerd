import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest'
import { createRef, useRef, type RefObject } from 'react'
import { act, render, screen, fireEvent } from '@testing-library/react'
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

/** Lays out the rail's column around the composer, as jsdom does not: 300px tall at the window's top, its content
 *  putting the composer's shell 400px down, `tall` px high. The column's scrollTop and the shell's box follow each
 *  other, and every write to the scrollTop is recorded; `scroll` moves the column as the reader would, unrecorded. */
function layOut(column: HTMLElement, shell: Element, tall = 50) {
  let top = 0
  const writes: number[] = []
  Object.defineProperty(column, 'scrollTop', {
    configurable: true,
    get: () => top,
    set: (value: number) => {
      top = value
      writes.push(value)
    },
  })
  Object.defineProperty(column, 'clientHeight', { configurable: true, get: () => 300 })
  column.getBoundingClientRect = () => new DOMRect(0, 0, 400, 300)
  shell.getBoundingClientRect = () => new DOMRect(0, 400 - top, 400, tall)
  return { writes, scroll: (value: number) => { top = value } }
}

/** Every way the page itself could scroll: an element's scrollIntoView (jsdom has none) and the window's scrolls. */
function watchPageScrolls() {
  const calls: string[] = []
  const jsdomScrollIntoView = Element.prototype.scrollIntoView
  Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
    calls.push(`scrollIntoView on ${this.tagName}`)
  })
  const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => { calls.push('window.scrollTo') })
  const scrollBy = vi.spyOn(window, 'scrollBy').mockImplementation(() => { calls.push('window.scrollBy') })
  return {
    calls,
    restore: () => {
      Element.prototype.scrollIntoView = jsdomScrollIntoView
      scrollTo.mockRestore()
      scrollBy.mockRestore()
    },
  }
}

function InColumn({ composer }: { composer: RefObject<CopilotComposerHandle> }) {
  const column = useRef<HTMLDivElement>(null)
  return (
    <>
      <button type="button">elsewhere</button>
      <div ref={column} data-testid="column">
        <CopilotComposer ref={composer} scrollerRef={column} onSubmit={() => {}} locked={false} />
      </div>
    </>
  )
}

/** The composer in the rail's column, laid out, with the page's scrolls and every focus() watched. */
function renderInColumn(tall?: number) {
  const ref = createRef<CopilotComposerHandle>()
  render(<InColumn composer={ref} />)
  const field = screen.getByLabelText(/ask about this filing/i) as HTMLTextAreaElement
  // The shell that draws the focus ring around the field and Send: not the form, whose privacy note would push the
  // conversation off a short sheet; scroll-mb-1 leaves room below it for the 3px ring.
  const shell = field.closest('.scroll-mb-1')!
  expect(shell.tagName).not.toBe('FORM')
  expect(shell.contains(screen.getByRole('button', { name: /^send$/i }))).toBe(true)
  return { ref, field, shell, column: layOut(screen.getByTestId('column'), shell, tall) }
}

// A press on Source should never move the page under the reader (E248, chief design on #1813): the composer's focus
// and its reveal move the rail's column, the one box handed to it, and nothing else.
describe('CopilotComposer focuses and reveals itself in its column, never moving the page', () => {
  let page: ReturnType<typeof watchPageScrolls>
  let focus: MockInstance<HTMLElement['focus']>
  beforeEach(() => {
    page = watchPageScrolls()
    focus = vi.spyOn(HTMLElement.prototype, 'focus')
  })
  afterEach(() => {
    page.restore()
    focus.mockRestore()
  })
  /** The options of each focus() the field took. */
  const fieldFocuses = (field: HTMLElement) => focus.mock.contexts.flatMap((el, i) => (el === field ? [focus.mock.calls[i]] : []))

  it('focus() takes focus without scrolling, then brings the shell to the nearest edge of its column', () => {
    const { ref, field, column } = renderInColumn()
    ref.current!.focus()
    expect(document.activeElement).toBe(field)
    expect(fieldFocuses(field)).toEqual([[{ preventScroll: true }]])
    // The shell, 400 to 450px down a 300px column: its foot comes to the column's.
    expect(column.writes).toEqual([150])
    expect(page.calls).toEqual([])
  })

  it('prefill() does the same, with its words in the field and the caret at their end', () => {
    const { ref, field, column } = renderInColumn()
    act(() => ref.current!.prefill('Explain this excerpt'))
    expect(field.value).toBe('Explain this excerpt')
    expect([field.selectionStart, field.selectionEnd]).toEqual([20, 20])
    expect(document.activeElement).toBe(field)
    expect(fieldFocuses(field)).toEqual([[{ preventScroll: true }]])
    expect(column.writes).toEqual([150])
    expect(page.calls).toEqual([])
  })

  it('revealFocus() brings the shell to the nearest edge only while focus is inside it, and moves nothing else', () => {
    const { ref, field, column } = renderInColumn()
    const send = screen.getByRole('button', { name: /^send$/i })

    // Focus outside the composer: nothing moves.
    screen.getByRole('button', { name: 'elsewhere' }).focus()
    ref.current!.revealFocus()
    expect(column.writes).toEqual([])

    // Focus in the field, then on Send, each with the shell below the column: its foot comes to the column's.
    field.focus()
    ref.current!.revealFocus()
    column.scroll(0)
    send.focus()
    ref.current!.revealFocus()
    expect(column.writes).toEqual([150, 150])

    // The shell above the column (the reader scrolled past it): its top comes to the column's.
    column.scroll(420)
    ref.current!.revealFocus()
    expect(column.writes).toEqual([150, 150, 400])

    // The shell already in view: nothing moves.
    column.scroll(200)
    ref.current!.revealFocus()
    expect(column.writes).toEqual([150, 150, 400])
    expect(page.calls).toEqual([])
  })

  it('a shell taller than its column keeps its top in view', () => {
    const { ref, column } = renderInColumn(350)
    ref.current!.focus()
    // 400 to 750px down a 300px column: its top comes to the column's, where its foot would push the top out.
    expect(column.writes).toEqual([400])
    expect(page.calls).toEqual([])
  })

  it('without a column, focus() moves nothing', () => {
    const ref = createRef<CopilotComposerHandle>()
    render(<CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />)
    const field = screen.getByLabelText(/ask about this filing/i)
    ref.current!.focus()
    expect(document.activeElement).toBe(field)
    expect(fieldFocuses(field)).toEqual([[{ preventScroll: true }]])
    expect(page.calls).toEqual([])
  })
})

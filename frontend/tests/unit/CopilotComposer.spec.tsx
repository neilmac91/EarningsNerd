import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRef, useRef } from 'react'
import { act, cleanup, render, screen, fireEvent } from '@testing-library/react'
import CopilotComposer, {
  type CopilotComposerHandle,
} from '@/features/filings/components/copilot/CopilotComposer'
import { rect, scrollBox, watchResizes, watchThePage } from './scrollBoxes'

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
 * draws the focus ring at 420 to 470px of the column's content: below the column's foot until the column scrolls. The
 * column scrolls from the start (its overflow inline, as the rail's class gives it), so the composer finds it on mount.
 * A box around the column scrolls too, and the column runs past it, as the desktop pane's lower part can run below the
 * fold: the reveal stops at the column and never moves that box or the page. `growShell` changes the shell's height,
 * its top in place, as a field that grows does.
 */
function renderInColumn({ shellTop = 420 }: { shellTop?: number } = {}) {
  const ref = createRef<CopilotComposerHandle>()
  render(
    <div data-testid="outer">
      <button type="button">elsewhere</button>
      <div data-testid="column" style={{ overflowY: 'auto' }}>
        <CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />
      </div>
    </div>,
  )
  const field = screen.getByLabelText(/ask about this filing/i)
  const box = screen.getByTestId('column')
  const column = scrollBox(box, 100, 300)
  const outer = scrollBox(screen.getByTestId('outer'), 0, 200)
  const shell = field.closest('.scroll-my-1') as HTMLElement
  let shellHeight = 50
  shell.getBoundingClientRect = () => rect(shellTop - column.scrollTop, shellHeight)
  const growShell = (height: number) => {
    shellHeight = height
  }
  return { ref, field, send: screen.getByRole('button', { name: /^send$/i }), shell, box, column, outer, growShell }
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
      const { ref, column, outer } = renderInColumn({ shellTop: 140 })
      // The column scrolled 100px down: the shell, 140px into its content, shows at 40px, above the column's top (100px).
      column.set(100)
      ref.current?.focus()
      expect(column.writes).toEqual([40])
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })

  it("prefill: a long excerpt shows its end, the caret's place, inside the field's own scroll", () => {
    const page = watchThePage()
    try {
      const { ref, field } = renderInColumn({ shellTop: 300 })
      // The field caps at 120px and scrolls its own text: 600px of excerpt.
      let fieldTop = 0
      Object.defineProperty(field, 'scrollHeight', { configurable: true, get: () => 600 })
      Object.defineProperty(field, 'scrollTop', {
        configurable: true,
        get: () => fieldTop,
        set: (value: number) => {
          fieldTop = value
        },
      })
      act(() => ref.current?.prefill('A long excerpt '.repeat(80)))
      expect(fieldTop).toBe(600)
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })

  it("counts the column's border and scroll padding and the shell's scroll margins, at either edge", () => {
    const page = watchThePage()
    try {
      const { ref, shell, box, column } = renderInColumn()
      // A 2px border (clientTop, the content 296px tall), 6px and 8px of scroll padding, and the shell's own margins
      // (scroll-my-1 gives it 4px each side, for the focus ring; 3px and 4px here, to tell the two apart).
      Object.defineProperty(box, 'clientTop', { configurable: true, get: () => 2 })
      column.resize(296)
      box.style.setProperty('scroll-padding-top', '6px')
      box.style.setProperty('scroll-padding-bottom', '8px')
      shell.style.setProperty('scroll-margin-top', '3px')
      shell.style.setProperty('scroll-margin-bottom', '4px')
      // Below: the shell's foot and margin (474px) to the padding's edge (100 + 2 + 296 - 8 = 390px).
      ref.current?.focus()
      expect(column.writes).toEqual([84])
      // Above: scrolled to 400px, the shell's top less its margin (17px) to the padding's edge (100 + 2 + 6 = 108px).
      column.set(400)
      ref.current?.focus()
      expect(column.writes).toEqual([84, 309])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
  })
})

describe('CopilotComposer keeps a focused composer in view as its column settles (E248)', () => {
  it('a column that shrinks under the focused composer brings it back to its foot, never the page', () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, field, box, column, outer } = renderInColumn()
      ref.current?.focus()
      expect(column.writes).toEqual([70])
      // The pane settles 100px shorter: the column now ends at 300px, the shell's foot still at 400px.
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70, 170])
      // Settled: another report moves nothing.
      resizes.resize(box)
      expect(column.writes).toEqual([70, 170])
      expect(document.activeElement).toBe(field)
      expect(outer.writes).toEqual([])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it("a pre-fill whose field grows after it takes focus keeps the shell's foot in view", () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, shell, column, growShell } = renderInColumn()
      act(() => ref.current?.prefill('A long excerpt '.repeat(20)))
      expect(column.writes).toEqual([70])
      // The field grows to its 120px cap on the next layout: the shell, 50px tall when revealed, is now 126px.
      growShell(126)
      resizes.resize(shell)
      expect(column.writes).toEqual([70, 146])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it('a composer the reader scrolled away stays where they put it, until they scroll it back into view', () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, box, column } = renderInColumn()
      ref.current?.focus()
      expect(column.writes).toEqual([70])
      // The reader scrolls the column back up to read, focus still in the field: the shell below its foot again.
      column.set(0)
      fireEvent.scroll(box)
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70])
      expect(column.scrollTop).toBe(0)
      // They scroll down to the composer (its shell at 200 to 250px, inside the column), and the next resize keeps it
      // in view: the column, now ending at 200px, comes 50px further.
      column.set(220)
      fireEvent.scroll(box)
      column.resize(100)
      resizes.resize(box)
      expect(column.writes).toEqual([70, 270])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it("a focus that brings the shell back counts it in view before the column's scroll event arrives", () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, box, column } = renderInColumn()
      ref.current?.focus()
      column.set(0)
      fireEvent.scroll(box)
      // ⌘K brings the shell back to the column's foot; the pane settles before the browser reports that scroll.
      ref.current?.focus()
      expect(column.writes).toEqual([70, 70])
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70, 70, 170])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it("a field that grows before the column reports the reveal's own scroll keeps following, in the browser's order", () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, shell, box, column, growShell } = renderInColumn()
      act(() => ref.current?.prefill('A long excerpt '.repeat(20)))
      expect(column.writes).toEqual([70])
      // React grows the field in a task after the frame; the next frame reports the reveal's scroll, then the resize.
      growShell(126)
      fireEvent.scroll(box)
      resizes.resize(shell)
      expect(column.writes).toEqual([70, 146])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it("a resize's own reveal counts its late scroll as its own too", () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, shell, box, column, growShell } = renderInColumn()
      ref.current?.focus()
      // The pane settles shorter and the column follows; then the field grows before that scroll is reported.
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70, 170])
      growShell(126)
      fireEvent.scroll(box)
      resizes.resize(shell)
      expect(column.writes).toEqual([70, 170, 246])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it('a resize that uncovers a composer the reader scrolled away leaves it where they put it', () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, box, column } = renderInColumn()
      ref.current?.focus()
      column.set(0)
      fireEvent.scroll(box)
      // The page scrolls and the unstuck pane grows to show the shell, then shrinks back: the column stays at the top.
      column.resize(400)
      resizes.resize(box)
      column.resize(300)
      resizes.resize(box)
      expect(column.writes).toEqual([70])
      expect(column.scrollTop).toBe(0)
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it('focus moving into a shell in view starts the follow again', () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { field, box, column } = renderInColumn()
      screen.getByRole('button', { name: 'elsewhere' }).focus()
      // Scrolled away, then uncovered by a taller column: the reader clicks into the field and types.
      column.set(0)
      fireEvent.scroll(box)
      column.resize(400)
      resizes.resize(box)
      field.focus()
      column.resize(300)
      resizes.resize(box)
      expect(column.writes).toEqual([70])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
    }
  })

  it('with focus elsewhere, a resize moves nothing', () => {
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, box, column } = renderInColumn()
      ref.current?.focus()
      screen.getByRole('button', { name: 'elsewhere' }).focus()
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      resizes.restore()
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
      // whose privacy note would push the conversation off a short sheet; scroll-my-1 leaves room around the shell for
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

/**
 * The window a reveal lands in: its height, and the page's scroll padding, which holds the site header's height at the
 * top and the consent bar's at the foot (globals.css). jsdom's window is 768px tall with no padding.
 */
function withWindow({ height, paddingTop, paddingBottom }: { height?: number; paddingTop?: number; paddingBottom?: number }) {
  const win = window as { innerHeight: number }
  const was = win.innerHeight
  if (height !== undefined) win.innerHeight = height
  const html = document.documentElement.style
  if (paddingTop !== undefined) html.setProperty('scroll-padding-top', `${paddingTop}px`)
  if (paddingBottom !== undefined) html.setProperty('scroll-padding-bottom', `${paddingBottom}px`)
  return () => {
    win.innerHeight = was
    html.removeProperty('scroll-padding-top')
    html.removeProperty('scroll-padding-bottom')
  }
}

describe("CopilotComposer's column reveal aims at the column's part on screen (E252)", () => {
  // Chief design on #1845: "The column's reveal aims at its visible part: its box clipped to the window, below the site
  // header, not its whole box." The column is on screen from 100 to 400px, the shell 420 to 470px into its content.
  it("a column that runs past the window's foot brings the shell to the window's foot, not the column's", () => {
    const restore = withWindow({ height: 350 })
    const page = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      ref.current?.focus()
      // The shell's foot (470px) to the window's (350px), not the column's (400px).
      expect(column.writes).toEqual([120])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      restore()
    }
  })

  it('above the consent bar the page reserves at its foot', () => {
    const restore = withWindow({ paddingBottom: 500 })
    const page = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      ref.current?.focus()
      // The band ends at 768 - 500 = 268px.
      expect(column.writes).toEqual([202])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      restore()
    }
  })

  it('below the site header the page reserves at its top', () => {
    const restore = withWindow({ paddingTop: 150 })
    const page = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      // Scrolled 400px: the shell at 20 to 70px, above the column's top (100px) and under the header (150px).
      column.set(400)
      ref.current?.focus()
      // To the header's foot: 400 - 130, where the column's own top would have stopped at 400 - 80.
      expect(column.writes).toEqual([270])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      restore()
    }
  })

  it("in a fixed layer the whole window, which the layer covers the page's bars in", () => {
    const restore = withWindow({ paddingTop: 150 })
    const page = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      // The phone's sheet: fixed, over the site header.
      screen.getByTestId('outer').style.position = 'fixed'
      column.set(400)
      ref.current?.focus()
      expect(column.writes).toEqual([320])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
      restore()
    }
  })

  it('a column with none of it on screen, or too little for the shell, aims at its own box', () => {
    for (const height of [80, 130]) {
      const restore = withWindow({ height })
      const page = watchThePage()
      try {
        // At 80px the column starts below the window; at 130px 30px of it shows, the shell 50px tall.
        const { ref, column } = renderInColumn()
        ref.current?.focus()
        expect(column.writes, `a ${height}px window`).toEqual([70])
        expect(page.moves).toEqual([])
      } finally {
        cleanup()
        page.restore()
        restore()
      }
    }
  })
})

describe('CopilotComposer: a press moves the page once the pane settles, when the composer is still out of view (E252)', () => {
  // Chief design on #1845: "Once the pane has settled after the press, ... the shell may still not be wholly in view
  // below the site header, ring and scroll margins included. Then move the page by the least distance that brings it
  // there. Move it once per press or ⌘K. Never move it from a resize or the follow." Animation frames are faked: the
  // composer waits for its shell and column to hold still for two frames before it reads them.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame'] })
  })
  afterEach(() => {
    vi.useRealTimers()
  })
  const frames = (count: number) => {
    for (let i = 0; i < count; i++) vi.advanceTimersToNextFrame()
  }

  // A 130px window: 30px of the column shows, too little for the 50px shell, so the column brings the shell to its own
  // foot (350 to 400px), below the window's. The page then moves it there: 400 - 130 = 270px, less than its top's 350.
  it('moves the page by the least distance, once, after the shell and its column hold still for two frames', () => {
    const restore = withWindow({ height: 130 })
    const page = watchThePage()
    try {
      const { ref, field, column } = renderInColumn()
      ref.current?.focus({ revealOnPage: true })
      expect(page.focusOptions(field)).toEqual([{ preventScroll: true }])
      expect(column.writes).toEqual([70])
      frames(2)
      expect(page.scrollBys, 'still waiting').toEqual([])
      frames(1)
      expect(page.scrollBys).toEqual([{ top: 270, behavior: 'smooth' }])
      expect(page.moves).toEqual(['scrollBy'])
      frames(30)
      expect(page.moves, 'once').toEqual(['scrollBy'])
      expect(column.writes).toEqual([70])
    } finally {
      page.restore()
      restore()
    }
  })

  it('reads the layout the pane settles in, however it moved before', () => {
    const page = watchThePage()
    try {
      const { ref, box, shell, column } = renderInColumn()
      // The column moves as the pane settles, the shell 320px into its content: from 100px, where the shell shows once
      // the column brings it up, to 740px, below the 768px window but for 28px, too few for the shell.
      let top = 100
      box.getBoundingClientRect = () => rect(top, 300)
      shell.getBoundingClientRect = () => rect(top + 320 - column.scrollTop, 50)
      ref.current?.focus({ revealOnPage: true })
      expect(column.writes).toEqual([70])
      frames(1)
      top = 400
      frames(1)
      top = 740
      frames(2)
      expect(page.scrollBys).toEqual([])
      frames(1)
      // Settled at 740px: the shell at the column's foot, 990 to 1040px, to the window's foot.
      expect(page.scrollBys).toEqual([{ top: 272, behavior: 'smooth' }])
    } finally {
      page.restore()
    }
  })

  it("a shell above the screen comes down below the site header, its scroll margin's room for the ring included", () => {
    const restore = withWindow({ paddingTop: 64 })
    const page = watchThePage()
    try {
      const { ref, box, shell, column } = renderInColumn()
      // The pane's sticky cell scrolled up with the workspace's end: the column at -500 to -200px.
      box.getBoundingClientRect = () => rect(-500, 300)
      shell.getBoundingClientRect = () => rect(-500 + 320 - column.scrollTop, 50)
      shell.style.setProperty('scroll-margin-top', '4px')
      ref.current?.focus({ revealOnPage: true })
      // None of the column on screen: its own foot, the shell at -250 to -200px.
      expect(column.writes).toEqual([70])
      frames(3)
      // Its top, less 4px, to the header's foot at 64px.
      expect(page.scrollBys).toEqual([{ top: -318, behavior: 'smooth' }])
    } finally {
      page.restore()
      restore()
    }
  })

  it('a pre-fill asks the same; one jump under prefers-reduced-motion', () => {
    const restore = withWindow({ height: 130 })
    const page = watchThePage()
    const reduce = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) => ({ matches: query === '(prefers-reduced-motion: reduce)', media: query }) as MediaQueryList,
    )
    try {
      const { ref } = renderInColumn()
      act(() => ref.current?.prefill('Explain this excerpt', { revealOnPage: true }))
      frames(3)
      expect(page.scrollBys).toEqual([{ top: 270, behavior: 'auto' }])
    } finally {
      reduce.mockRestore()
      page.restore()
      restore()
    }
  })

  it('no move when the shell shows once the pane settles, or in a fixed layer', () => {
    const page = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      ref.current?.focus({ revealOnPage: true })
      frames(30)
      expect(column.writes).toEqual([70])
      expect(page.moves).toEqual([])
    } finally {
      page.restore()
    }
    cleanup()
    const restore = withWindow({ height: 130 })
    const sheet = watchThePage()
    try {
      const { ref, column } = renderInColumn()
      // The phone's sheet: no page scroll moves it.
      screen.getByTestId('outer').style.position = 'fixed'
      ref.current?.focus({ revealOnPage: true })
      frames(30)
      expect(column.writes).toEqual([70])
      expect(sheet.moves).toEqual([])
    } finally {
      sheet.restore()
      restore()
    }
  })

  it('never from a focus no press asked it for, a resize, the follow or revealFocus', () => {
    const restore = withWindow({ height: 130 })
    const resizes = watchResizes()
    const page = watchThePage()
    try {
      const { ref, box, column } = renderInColumn()
      ref.current?.focus()
      frames(30)
      expect(page.moves).toEqual([])
      // The pane settles shorter: the follow brings the shell to the column's foot, the page still.
      column.resize(200)
      resizes.resize(box)
      expect(column.writes).toEqual([70, 170])
      ref.current?.revealFocus()
      frames(30)
      expect(page.moves).toEqual([])
      // A press then moves it, once; the follow after it does not again.
      ref.current?.focus({ revealOnPage: true })
      frames(3)
      expect(page.moves).toEqual(['scrollBy'])
      column.resize(150)
      resizes.resize(box)
      frames(30)
      expect(page.moves).toEqual(['scrollBy'])
    } finally {
      page.restore()
      resizes.restore()
      restore()
    }
  })

  it("the reader's wheel, touch or press while it waits, or focus leaving the composer, drops it", () => {
    const leave = [
      () => fireEvent.wheel(document.body),
      () => fireEvent.touchStart(document.body),
      () => fireEvent.pointerDown(document.body),
      () => screen.getByRole('button', { name: 'elsewhere' }).focus(),
    ]
    for (const [i, act] of leave.entries()) {
      const restore = withWindow({ height: 130 })
      const page = watchThePage()
      try {
        const { ref } = renderInColumn()
        ref.current?.focus({ revealOnPage: true })
        frames(1)
        act()
        frames(30)
        expect(page.moves, `leave ${i}`).toEqual([])
      } finally {
        cleanup()
        page.restore()
        restore()
      }
    }
  })

  it('a newer press waits afresh and moves the page once; the composer leaving drops the wait', () => {
    const restore = withWindow({ height: 130 })
    const page = watchThePage()
    try {
      const { ref } = renderInColumn()
      ref.current?.focus({ revealOnPage: true })
      frames(2)
      ref.current?.focus({ revealOnPage: true })
      frames(2)
      expect(page.moves).toEqual([])
      frames(1)
      expect(page.moves).toEqual(['scrollBy'])
      frames(30)
      expect(page.moves).toEqual(['scrollBy'])
    } finally {
      page.restore()
      restore()
    }
    const again = withWindow({ height: 130 })
    const gone = watchThePage()
    try {
      const ref = createRef<CopilotComposerHandle>()
      const view = render(
        <div style={{ overflowY: 'auto' }}>
          <CopilotComposer ref={ref} onSubmit={() => {}} locked={false} />
        </div>,
      )
      ref.current?.focus({ revealOnPage: true })
      view.unmount()
      frames(30)
      expect(gone.moves).toEqual([])
    } finally {
      gone.restore()
      again()
    }
  })

  it('a pane that never holds still is read at its twelfth frame', () => {
    const page = watchThePage()
    try {
      const { ref, box, shell, column } = renderInColumn()
      let top = 740
      box.getBoundingClientRect = () => rect(top, 300)
      shell.getBoundingClientRect = () => rect(top + 320 - column.scrollTop, 50)
      ref.current?.focus({ revealOnPage: true })
      for (let frame = 1; frame < 12; frame++) {
        top += 1
        frames(1)
      }
      expect(page.moves).toEqual([])
      frames(1)
      // Read at 751px: the shell at the column's foot, 1001 to 1051px, to the window's foot.
      expect(page.scrollBys).toEqual([{ top: 283, behavior: 'smooth' }])
    } finally {
      page.restore()
    }
  })
})

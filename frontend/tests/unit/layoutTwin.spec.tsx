import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { useEffect } from 'react'
import { renderedCopy, shownTwin } from '@/features/filings/lib/layoutTwin'
import { FilingViewerProvider, useFilingViewer } from '@/features/filings/components/copilot/FilingViewerContext'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

/**
 * features/filings/lib/layoutTwin.ts: a chip rendered in two responsive layouts (EN-03's metric cards
 * and table) resolves to the copy now shown, wherever it is remembered as a focus target. jsdom has no
 * layout, so "rendered" is modelled with a getClientRects spy: a copy inside `[data-hidden]` has no
 * client rects, as a display:none element has none in a browser.
 */

let rects: ReturnType<typeof vi.spyOn> | null = null
afterEach(() => {
  rects?.mockRestore()
  rects = null
})
function modelLayout() {
  rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function (this: HTMLElement) {
    return (this.closest('[data-hidden]') ? [] : [{}]) as unknown as DOMRectList
  })
}

/** Two layouts of the same two chips, the cards hidden (a desktop width) unless `cardsShown`. */
function Layouts({ cardsShown = false }: { cardsShown?: boolean }) {
  return (
    <>
      <div data-layout="cards" {...(cardsShown ? {} : { 'data-hidden': '' })}>
        <button data-layout-twin="t0-name">card row 0</button>
        <button data-layout-twin="t1-name">card row 1</button>
      </div>
      <div data-layout="table" {...(cardsShown ? { 'data-hidden': '' } : {})}>
        <button data-layout-twin="t0-name">table row 0</button>
        <button data-layout-twin="t1-name">table row 1</button>
      </div>
      <button>plain chip</button>
    </>
  )
}
const chip = (name: string) => screen.getByRole('button', { name })

describe('shownTwin', () => {
  it('finds the rendered copy with the same key, never the element itself, a hidden copy or another key', () => {
    modelLayout()
    render(<Layouts />)
    expect(shownTwin(chip('card row 1'))).toBe(chip('table row 1'))
    expect(shownTwin(chip('table row 1'))).toBeNull() // its only twin is hidden
    expect(shownTwin(chip('plain chip'))).toBeNull() // no key
    expect(shownTwin(chip('card row 0'), 't1-name')).toBe(chip('table row 1')) // an explicit key wins
  })
})

describe('renderedCopy', () => {
  it('keeps a rendered element, resolves a hidden one to its shown twin, and leaves anything else as it is', () => {
    modelLayout()
    render(<Layouts />)
    expect(renderedCopy(chip('table row 1'))).toBe(chip('table row 1'))
    expect(renderedCopy(chip('card row 1'))).toBe(chip('table row 1'))
    expect(renderedCopy(chip('plain chip'))).toBe(chip('plain chip'))
    expect(renderedCopy(null)).toBeNull()
  })

  it('a hidden copy with no rendered twin stays itself (nothing better to return)', () => {
    rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([] as unknown as DOMRectList)
    render(<Layouts />)
    expect(renderedCopy(chip('card row 0'))).toBe(chip('card row 0'))
  })
})

describe("the research pane's opener (FilingViewerContext)", () => {
  const CITATION = { n: 0, excerpt: 'Total net sales', section_ref: 'Item 8', verified: true } as unknown as CopilotCitation
  let viewer: ReturnType<typeof useFilingViewer> = null
  function Capture() {
    const v = useFilingViewer()
    useEffect(() => {
      viewer = v
    })
    return null
  }

  it('a chip that opened the pane and was hidden by a breakpoint since is read as its copy now shown', () => {
    modelLayout()
    const { rerender } = render(
      <FilingViewerProvider>
        <Capture />
        <Layouts cardsShown />
      </FilingViewerProvider>,
    )
    // Opened from a card chip on a phone...
    act(() => viewer!.requestHighlight(CITATION, chip('card row 1')))
    expect(viewer!.peekOpener()).toBe(chip('card row 1'))
    // ...then rotated: the cards are hidden and the table is shown.
    rerender(
      <FilingViewerProvider>
        <Capture />
        <Layouts />
      </FilingViewerProvider>,
    )
    expect(viewer!.peekOpener()).toBe(chip('table row 1'))
    expect(viewer!.takeOpener()).toBe(chip('table row 1'))
    expect(viewer!.takeOpener()).toBeNull() // taken: forgotten
  })
})

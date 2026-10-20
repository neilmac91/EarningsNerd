import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import postcss from 'postcss'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  CITATION_HIGHLIGHT_CSS,
  FIND_HIGHLIGHT_CSS,
  __resetCitationHighlightStyleForTests,
  clearCitationHighlight,
  highlightExcerptInDom,
} from '@/features/filings/components/copilot/highlightInDom'

interface Geometry {
  left?: number
  top?: number
  width?: number
  height?: number
  clientWidth?: number
  clientHeight?: number
  scrollWidth?: number
  scrollHeight?: number
  /** A scroll box's computed overflow on each axis (the helper scrolls only boxes that can scroll). */
  overflowX?: string
  overflowY?: string
}

/** jsdom has no layout: give one element a viewport rectangle, its scroll metrics and its overflow. */
function place(el: HTMLElement, g: Geometry) {
  const { left = 0, top = 0, width = 0, height = 0 } = g
  if (g.overflowX) el.style.overflowX = g.overflowX
  if (g.overflowY) el.style.overflowY = g.overflowY
  vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
    x: left, y: top, left, top, width, height, right: left + width, bottom: top + height, toJSON: () => ({}),
  } as DOMRect)
  for (const key of ['clientWidth', 'clientHeight', 'scrollWidth', 'scrollHeight'] as const) {
    if (g[key] !== undefined) Object.defineProperty(el, key, { configurable: true, value: g[key] })
  }
}

/** jsdom has no Element.scrollTo either; a spec that wants the smooth call gives the element one. */
function stubScrollTo(el: HTMLElement) {
  const scrollTo = vi.fn()
  Object.defineProperty(el, 'scrollTo', { configurable: true, value: scrollTo })
  return scrollTo
}

// jsdom supports TreeWalker + Range but has no layout, no Element.scrollTo, no scrollIntoView and no
// CSS Custom Highlight API; the helper feature-detects them, so here the geometry is stubbed per
// element and we verify location, the block flash and the scroll. The scroll moves the container it
// is given and the scroll boxes inside it, never anything outside it: scrollIntoView also scrolled
// the page, which slid the whole filing page sideways when the reader overflowed its pane (EN-04).
describe('highlightExcerptInDom', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    // The adopted-sheet memo is module-level; start every spec from a fresh document.
    __resetCitationHighlightStyleForTests()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('locates an excerpt spanning multiple inline elements, flashes the enclosing block and centres it in the container', () => {
    const container = document.createElement('div')
    container.innerHTML =
      '<p>Some intro.</p><p>Revenue <strong>increased</strong> to $391.0B this year.</p>'
    document.body.appendChild(container)
    const [intro, passage] = container.querySelectorAll('p')
    place(container, { top: 100, height: 400, clientHeight: 400, scrollHeight: 2000, overflowY: 'auto' })
    place(intro, { top: 120, height: 40 })
    place(passage, { top: 900, height: 40 })
    const scrollTo = stubScrollTo(container)

    const found = highlightExcerptInDom(container, 'Revenue increased to $391.0B this year')

    expect(found).toBe(true)
    expect(intro).not.toHaveClass('citation-flash')
    expect(passage).toHaveClass('citation-flash')
    // The passage's offset in the container (900 - 100), less half the free height ((400 - 40) / 2).
    expect(scrollTo.mock.calls).toEqual([[{ top: 620, behavior: 'smooth' }]])
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
    expect(window.scrollTo).not.toHaveBeenCalled()

    document.body.removeChild(container)
  })

  describe('scrolls inside the container only (EN-04)', () => {
    it('a cited cell in a wide table scrolls its own box sideways to the nearest edge and the container down to it', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<p>The following table shows net sales by reportable segment.</p>' +
        '<div class="box"><table><tbody><tr><td>Americas</td><td>Reportable since fiscal 2013 after the segment change</td></tr></tbody></table></div>'
      document.body.appendChild(container)
      const box = container.querySelector<HTMLElement>('.box')!
      const cell = container.querySelectorAll('td')[1]
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 400, scrollHeight: 1000, overflowX: 'auto', overflowY: 'auto' })
      place(box, { left: 16, top: 400, width: 368, height: 60, clientWidth: 368, clientHeight: 60, scrollWidth: 1200, scrollHeight: 60, overflowX: 'auto', overflowY: 'auto' })
      place(cell, { left: 900, top: 410, width: 100, height: 30 })
      const containerScroll = stubScrollTo(container)
      const boxScroll = stubScrollTo(box)

      expect(highlightExcerptInDom(container, 'Reportable since fiscal 2013 after the segment change')).toBe(true)

      // Sideways: the cell's right edge (1000) to the box's right edge (16 + 368).
      expect(boxScroll.mock.calls).toEqual([[{ left: 616, behavior: 'smooth' }]])
      // Down: the cell's offset (410) less half the free height ((300 - 30) / 2).
      expect(containerScroll.mock.calls).toEqual([[{ top: 275, behavior: 'smooth' }]])
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
      expect(window.scrollTo).not.toHaveBeenCalled()
      container.remove()
    })

    it('under prefers-reduced-motion both boxes jump straight there: no smooth scroll', () => {
      vi.spyOn(window, 'matchMedia').mockImplementation(
        (query: string) => ({ matches: query === '(prefers-reduced-motion: reduce)', media: query }) as MediaQueryList,
      )
      const container = document.createElement('div')
      container.innerHTML =
        '<div class="box"><table><tbody><tr><td>Americas</td><td>Reportable since fiscal 2013 after the segment change</td></tr></tbody></table></div>'
      document.body.appendChild(container)
      const box = container.querySelector<HTMLElement>('.box')!
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 400, scrollHeight: 1000, overflowX: 'auto', overflowY: 'auto' })
      place(box, { left: 16, top: 400, width: 368, height: 60, clientWidth: 368, clientHeight: 60, scrollWidth: 1200, scrollHeight: 60, overflowX: 'auto', overflowY: 'auto' })
      place(container.querySelectorAll('td')[1], { left: 900, top: 410, width: 100, height: 30 })
      const containerScroll = stubScrollTo(container)
      const boxScroll = stubScrollTo(box)

      expect(highlightExcerptInDom(container, 'Reportable since fiscal 2013 after the segment change')).toBe(true)

      // 'auto' follows the box's own scroll-behavior, which neither the reader nor a table box sets: a jump.
      expect(boxScroll.mock.calls).toEqual([[{ left: 616, behavior: 'auto' }]])
      expect(containerScroll.mock.calls).toEqual([[{ top: 275, behavior: 'auto' }]])
      container.remove()
    })

    it('a cell wider than its box shows its start, and a passage near the end stops at the last scroll position', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<div class="box"><table><tbody><tr><td>Americas</td><td>Reportable since fiscal 2013 after the segment change</td></tr></tbody></table></div>'
      document.body.appendChild(container)
      const box = container.querySelector<HTMLElement>('.box')!
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 400, scrollHeight: 1000, overflowX: 'auto', overflowY: 'auto' })
      place(box, { left: 16, top: 950, width: 368, height: 40, clientWidth: 368, clientHeight: 40, scrollWidth: 1200, scrollHeight: 40, overflowX: 'auto', overflowY: 'auto' })
      // The cell (500 to 900) is wider than the 368px box: its start goes to the box's left edge, not its
      // end to the right one, which would hide where the cited text begins.
      place(container.querySelectorAll('td')[1], { left: 500, top: 955, width: 400, height: 30 })
      const containerScroll = stubScrollTo(container)
      const boxScroll = stubScrollTo(box)

      expect(highlightExcerptInDom(container, 'Reportable since fiscal 2013 after the segment change')).toBe(true)

      expect(boxScroll.mock.calls).toEqual([[{ left: 484, behavior: 'smooth' }]])
      // Centring (955 - 135 = 820) would scroll past the end: the reader stops at 1000 - 300.
      expect(containerScroll.mock.calls).toEqual([[{ top: 700, behavior: 'smooth' }]])
      container.remove()
    })

    it('a cell left of the box\'s view scrolls the box back to the cell\'s start', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<div class="box"><table><tbody><tr><td>Net sales by reportable segment for the year</td><td>Total</td></tr></tbody></table></div>'
      document.body.appendChild(container)
      const box = container.querySelector<HTMLElement>('.box')!
      box.scrollLeft = 500
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 400, scrollHeight: 300, overflowX: 'auto', overflowY: 'auto' })
      place(box, { left: 16, top: 0, width: 368, height: 60, clientWidth: 368, clientHeight: 60, scrollWidth: 1200, scrollHeight: 60, overflowX: 'auto', overflowY: 'auto' })
      place(container.querySelector('td')!, { left: -100, top: 10, width: 200, height: 30 })

      expect(highlightExcerptInDom(container, 'Net sales by reportable segment for the year')).toBe(true)

      // Without Element.scrollTo (jsdom, old engines) the offsets are assigned: 500 + (-100 - 16).
      expect(box.scrollLeft).toBe(384)
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
      container.remove()
    })

    it('centres the passage in the part of the container on screen, above the fold and the consent bar', () => {
      // Before the desktop pane sticks, the reader starts at 400 and runs to 1240, past the 768px fold:
      // the passage is centred in 400 to 768, not in the reader's whole 840px, which would leave it
      // below the fold (this helper never scrolls the page to make up for it).
      const container = document.createElement('div')
      container.innerHTML = '<p>Revenue increased to $391.0B this year.</p>'
      document.body.appendChild(container)
      const passage = container.querySelector('p')!
      place(container, { top: 400, height: 840, clientHeight: 840, scrollHeight: 3000, overflowY: 'auto' })
      place(passage, { top: 1600, height: 80 })
      const scrollTo = stubScrollTo(container)
      expect(window.innerHeight).toBe(768)

      highlightExcerptInDom(container, 'Revenue increased to $391.0B this year')
      // 1600 - 400, less half the on-screen free height ((768 - 400 - 80) / 2).
      expect(scrollTo.mock.calls).toEqual([[{ top: 1056, behavior: 'smooth' }]])

      // The consent bar covers the bottom 100px while it shows: the on-screen part ends at 668.
      document.documentElement.style.setProperty('--consent-inset', '100px')
      scrollTo.mockClear()
      highlightExcerptInDom(container, 'Revenue increased to $391.0B this year')
      expect(scrollTo.mock.calls).toEqual([[{ top: 1106, behavior: 'smooth' }]])
      document.documentElement.style.removeProperty('--consent-inset')

      document.body.removeChild(container)
    })

    it('a passage taller than the container is aligned to its start, not centred past it', () => {
      const container = document.createElement('div')
      container.innerHTML = '<p>Intro.</p><p>Gross margin expanded on a favourable product mix this quarter.</p>'
      document.body.appendChild(container)
      const passage = container.querySelectorAll('p')[1]
      place(container, { top: 50, height: 300, clientHeight: 300, scrollHeight: 3000, overflowY: 'auto' })
      place(passage, { top: 850, height: 500 })
      const scrollTo = stubScrollTo(container)

      expect(highlightExcerptInDom(container, 'Gross margin expanded on a favourable product mix')).toBe(true)

      expect(scrollTo.mock.calls).toEqual([[{ top: 800, behavior: 'smooth' }]])
      container.remove()
    })

    it('each box sees the cell where the box inside it moved it: the container does not also scroll sideways', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<div class="box"><table><tbody><tr><td>Americas</td><td>Reportable since fiscal 2013 after the segment change</td></tr></tbody></table></div>'
      document.body.appendChild(container)
      const box = container.querySelector<HTMLElement>('.box')!
      // The container itself can scroll sideways too (something else in it is wider than it).
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 600, scrollHeight: 1000, overflowX: 'auto', overflowY: 'auto' })
      place(box, { left: 16, top: 400, width: 368, height: 60, clientWidth: 368, clientHeight: 60, scrollWidth: 1200, scrollHeight: 60, overflowX: 'auto', overflowY: 'auto' })
      place(container.querySelectorAll('td')[1], { left: 900, top: 410, width: 100, height: 30 })
      const containerScroll = stubScrollTo(container)
      const boxScroll = stubScrollTo(box)

      expect(highlightExcerptInDom(container, 'Reportable since fiscal 2013 after the segment change')).toBe(true)

      // The box brings the cell to its right edge (384), inside the container's 400px view, so the
      // container only scrolls down; read from the cell's first position, it would scroll right too.
      expect(boxScroll.mock.calls).toEqual([[{ left: 616, behavior: 'smooth' }]])
      expect(containerScroll.mock.calls).toEqual([[{ top: 275, behavior: 'smooth' }]])
      container.remove()
    })

    it('leaves a box that cannot scroll alone, even when its content overflows it', () => {
      const container = document.createElement('div')
      container.innerHTML = '<p>Intro.</p><blockquote><p>Operating expenses declined as headcount stayed flat.</p></blockquote>'
      document.body.appendChild(container)
      const quote = container.querySelector('blockquote')!
      place(container, { left: 0, top: 0, width: 400, height: 300, clientWidth: 400, clientHeight: 300, scrollWidth: 400, scrollHeight: 1000, overflowY: 'auto' })
      // overflow: visible (unset): wider content spills out of it, but it is not a scroll box.
      place(quote, { left: 16, top: 400, width: 368, height: 60, clientWidth: 368, clientHeight: 60, scrollWidth: 900, scrollHeight: 120 })
      place(quote.querySelector('p')!, { left: 116, top: 440, width: 900, height: 30 })
      const containerScroll = stubScrollTo(container)
      const quoteScroll = stubScrollTo(quote)

      expect(highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat')).toBe(true)

      // Were it a scroll box, it would move 100 right and 25 down to show the passage.
      expect(quoteScroll).not.toHaveBeenCalled()
      expect(containerScroll.mock.calls).toEqual([[{ top: 305, behavior: 'smooth' }]])
      container.remove()
    })

    it('scrolls nothing outside the container, even an ancestor that could scroll to the passage', () => {
      const page = document.createElement('div')
      const container = document.createElement('div')
      container.innerHTML = '<p>Intro.</p><p>Operating expenses declined as headcount stayed flat.</p>'
      page.appendChild(container)
      document.body.appendChild(page)
      const passage = container.querySelectorAll('p')[1]
      place(page, { left: 0, top: 0, width: 1440, height: 900, clientWidth: 1440, clientHeight: 900, scrollWidth: 1793, scrollHeight: 4000, overflowX: 'auto', overflowY: 'auto' })
      place(container, { left: 1020, top: 64, width: 772, height: 800, clientWidth: 772, clientHeight: 800, scrollWidth: 772, scrollHeight: 5000, overflowX: 'auto', overflowY: 'auto' })
      place(passage, { left: 1036, top: 2000, width: 740, height: 60 })
      const pageScroll = stubScrollTo(page)
      const containerScroll = stubScrollTo(container)

      expect(highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat')).toBe(true)

      expect(containerScroll).toHaveBeenCalledTimes(1)
      expect(pageScroll).not.toHaveBeenCalled()
      expect(window.scrollTo).not.toHaveBeenCalled()
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
      page.remove()
    })
  })

  it('returns false when the passage is not present', () => {
    const container = document.createElement('div')
    container.innerHTML = '<p>Revenue increased to $391.0B this year.</p>'
    document.body.appendChild(container)

    const found = highlightExcerptInDom(
      container,
      'The company declared a special dividend of $5 per share today.',
    )

    expect(found).toBe(false)
    document.body.removeChild(container)
  })

  // The `::highlight(copilot-citation)` paint lives in a constructed stylesheet adopted on first use
  // (lightningcss in Next 16.3 does not know the pseudo-element: it emits a SelectorError warning and,
  // with error recovery, keeps the rule, but Next's build surfaces that as "Parsing CSS source code
  // failed"). jsdom has neither the Highlight API nor constructable stylesheets, so stub both and
  // check the wiring: the rule is adopted exactly once, before the highlight is registered.
  describe('with a stubbed Highlight API', () => {
    const replaceSync = vi.fn()
    class FakeSheet {
      replaceSync = replaceSync
    }
    const highlights = new Map<string, unknown>()
    const g = globalThis as unknown as {
      CSSStyleSheet: unknown
      Highlight?: unknown
      CSS: { highlights?: Map<string, unknown> }
    }
    const doc = document as unknown as { adoptedStyleSheets?: unknown[] }
    let saved: { CSSStyleSheet: unknown; Highlight: unknown; highlights: unknown; adopted: unknown[] | undefined }

    beforeEach(() => {
      saved = {
        CSSStyleSheet: g.CSSStyleSheet,
        Highlight: g.Highlight,
        highlights: g.CSS.highlights,
        adopted: doc.adoptedStyleSheets,
      }
      replaceSync.mockClear()
      highlights.clear()
      g.CSSStyleSheet = FakeSheet
      g.Highlight = class {
        constructor(public range: Range) {}
      }
      g.CSS.highlights = highlights
      doc.adoptedStyleSheets = []
    })

    afterEach(() => {
      g.CSSStyleSheet = saved.CSSStyleSheet
      g.Highlight = saved.Highlight
      g.CSS.highlights = saved.highlights as Map<string, unknown> | undefined
      if (saved.adopted === undefined) delete doc.adoptedStyleSheets
      else doc.adoptedStyleSheets = saved.adopted
    })

    it.each(['following paragraph', 'empty boundary nodes', 'document end'] as const)(
      'maps the exact range and scroll target at a %s',
      (scenario) => {
        const container = document.createElement('div')
        const excerpt = 'Operating expenses declined as headcount stayed flat'
        container.innerHTML = `<p>Some intro.</p><p>${excerpt}</p>`
        const [intro, passage] = container.querySelectorAll('p')
        const text = passage.firstChild as Text
        if (scenario !== 'document end') {
          const following = document.createElement('p')
          following.textContent = 'The next disclosure begins here'
          container.appendChild(following)
        }
        if (scenario === 'empty boundary nodes') {
          intro.appendChild(document.createTextNode(''))
          passage.insertBefore(document.createTextNode(''), text)
          passage.appendChild(document.createTextNode(''))
        }
        document.body.appendChild(container)
        // The scroll target is the passage itself: it alone sits at 600, so only it yields this offset.
        place(container, { top: 0, height: 300, clientHeight: 300, scrollHeight: 3000, overflowY: 'auto' })
        place(intro, { top: 200, height: 30 })
        place(passage, { top: 600, height: 30 })
        try {
          expect(highlightExcerptInDom(container, excerpt, { located: true })).toBe(true)
          const highlight = highlights.get('copilot-citation') as { range: Range }
          expect(highlight.range.startContainer).toBe(text)
          expect(highlight.range.startOffset).toBe(0)
          expect(highlight.range.endContainer).toBe(text)
          expect(highlight.range.endOffset).toBe(excerpt.length)
          expect(highlight.range.toString()).toBe(excerpt)
          expect(container.querySelectorAll('.citation-flash')).toHaveLength(1)
          expect(passage).toHaveClass('citation-flash')
          expect(intro).not.toHaveClass('citation-flash')
          // No Element.scrollTo in jsdom: the offset is assigned, 600 - (300 - 30) / 2.
          expect(container.scrollTop).toBe(465)
          expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
        } finally {
          container.remove()
        }
      },
    )

    it('adopts both highlights in one sheet once, and registers one of the two at a time', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<p>Net income rose on higher services revenue during the quarter.</p>' +
        '<p>Operating expenses declined as headcount stayed flat through the period.</p>'
      document.body.appendChild(container)
      try {
        // A passage the server located takes the device's highlight.
        expect(
          highlightExcerptInDom(container, 'Net income rose on higher services revenue during the quarter', { located: true }),
        ).toBe(true)
        expect(replaceSync).toHaveBeenCalledWith(`${CITATION_HIGHLIGHT_CSS}\n${FIND_HIGHLIGHT_CSS}`)
        expect(CITATION_HIGHLIGHT_CSS).toMatch(/^::highlight\(copilot-citation\) \{/)
        expect(FIND_HIGHLIGHT_CSS).toMatch(/^::highlight\(copilot-find\) \{/)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
        expect(doc.adoptedStyleSheets?.[0]).toBeInstanceOf(FakeSheet)
        expect([...highlights.keys()]).toEqual(['copilot-citation'])

        // Second highlight: same document, no second stylesheet. A caller that does not say the server located
        // the passage gets the neutral find highlight, which replaces the device's.
        expect(
          highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat through the period'),
        ).toBe(true)
        expect(replaceSync).toHaveBeenCalledTimes(1)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
        expect([...highlights.keys()]).toEqual(['copilot-find'])

        // Closing the reader clears whichever is registered.
        clearCitationHighlight()
        expect(highlights.size).toBe(0)
      } finally {
        document.body.removeChild(container)
      }
    })

    it("a jump that finds nothing clears the last jump's paint, so no passage beside the banner reads as this one (D-044)", () => {
      const container = document.createElement('div')
      container.innerHTML = '<p>Net income rose on higher services revenue during the quarter.</p>'
      document.body.appendChild(container)
      const found = 'Net income rose on higher services revenue during the quarter'
      const absent = 'The company declared a special dividend of $5 per share today'
      try {
        // A located jump, then a chip whose passage the reader does not hold: the reader shows its
        // "Couldn't pinpoint" banner, and the device must not stay on the last passage.
        expect(highlightExcerptInDom(container, found, { located: true })).toBe(true)
        expect([...highlights.keys()]).toEqual(['copilot-citation'])
        expect(highlightExcerptInDom(container, absent, { located: true })).toBe(false)
        expect(highlights.size).toBe(0)
        // The same after the find paint.
        expect(highlightExcerptInDom(container, found)).toBe(true)
        expect([...highlights.keys()]).toEqual(['copilot-find'])
        expect(highlightExcerptInDom(container, absent)).toBe(false)
        expect(highlights.size).toBe(0)
      } finally {
        document.body.removeChild(container)
      }
    })

    it('re-adopts the same sheet if something replaced document.adoptedStyleSheets without spreading', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<p>Net income rose on higher services revenue during the quarter.</p>' +
        '<p>Operating expenses declined as headcount stayed flat through the period.</p>'
      document.body.appendChild(container)
      try {
        expect(
          highlightExcerptInDom(container, 'Net income rose on higher services revenue during the quarter'),
        ).toBe(true)
        const adopted = doc.adoptedStyleSheets?.[0]
        expect(adopted).toBeInstanceOf(FakeSheet)

        // Third-party code clobbers the list (no spread) — our sheet is dropped, memo still set.
        doc.adoptedStyleSheets = []

        expect(
          highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat through the period'),
        ).toBe(true)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
        // Re-adopted, and it is the SAME sheet object — the CSS text is not re-parsed.
        expect(doc.adoptedStyleSheets?.[0]).toBe(adopted)
        expect(replaceSync).toHaveBeenCalledTimes(1)
      } finally {
        document.body.removeChild(container)
      }
    })

    it('re-adopts after the memo is reset (fresh document semantics)', () => {
      const container = document.createElement('div')
      container.innerHTML = '<p>Gross margin expanded on a favourable product mix this quarter.</p>'
      document.body.appendChild(container)
      try {
        expect(highlightExcerptInDom(container, 'Gross margin expanded on a favourable product mix')).toBe(true)
        expect(replaceSync).toHaveBeenCalledTimes(1)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
      } finally {
        document.body.removeChild(container)
      }
    })
  })
})

/**
 * The reader's two paints (D-044). A passage the server located wears the brand device's mark: the tint and
 * the 2px hairline of `.en-mark` in app/globals.css, light and dark, so it looks the same in the reader as on
 * the landing page, and the passage in the primary ink (tailwind.config.js), as the landing's marked block
 * sets it. Any other jump lands in the neutral find paint, which never takes the device. The paints are a
 * constructed sheet the stylesheet cannot hold (see CITATION_HIGHLIGHT_CSS), so this reads both and holds
 * each to its source; which one a jump registers is tests/unit/sourcePanePaint.spec.tsx's, and
 * tests/e2e/copilot-highlight-css.spec.ts reads what Chromium computes.
 */
describe("the reader's two paints (D-044)", () => {
  const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  const tokens = createRequire(import.meta.url)('../../tailwind.config.js').theme.extend.colors as { brand: { DEFAULT: string }; text: { primary: { light: string; dark: string } } }
  const colour = (value = '') => value.replace(/\s+/g, '').toLowerCase()
  /** A rule's declarations by property, the rule found by its whole selector. */
  const rule = (css: string, selector: string): Record<string, string> => {
    const out: Record<string, string> = {}
    postcss.parse(css).walkRules((r) => {
      if (r.selector.replace(/\s+/g, ' ').trim() === selector) r.walkDecls((d) => { out[d.prop] = d.value })
    })
    return out
  }
  const globals = readFileSync(path.join(FRONTEND, 'app/globals.css'), 'utf8')
  /** `.en-mark`'s tint (the gradient's stop from 62%) and hairline (the inset shadow at its foot). */
  const device = (selector: string) => {
    const d = rule(globals, selector)
    const shadow = /^inset 0 -(\d+px) 0 (.+)$/.exec(d['box-shadow'] ?? '')
    return { tint: colour(/62%,\s*(.+?)\s+62%\)$/.exec(d.background ?? '')?.[1]), hairline: colour(shadow?.[2]), width: shadow?.[1] }
  }

  it('reads the device from the stylesheet (anti-vacuity)', () => {
    expect(device('.en-mark')).toEqual({ tint: '#ecf2ee', hairline: '#cfe0d6', width: '2px' })
    expect(device('.dark .en-mark')).toEqual({ tint: 'rgba(127,178,149,0.14)', hairline: 'rgba(127,178,149,0.28)', width: '2px' })
  })

  /** Where a paint departs from the running-text form of the device: `.en-mark`'s tint and 2px hairline, unbroken, on
      the primary ink, with `.dark`'s pair. The other form, the marked block's bar (a border) or its class, is never
      the reader's: a located passage inside running text is marked, not set as a block. */
  const departures = (css: string): string[] => {
    const light = rule(css, '::highlight(copilot-citation)')
    const dark = rule(css, '.dark ::highlight(copilot-citation)')
    const line = /^underline (\d+px) (.+)$/.exec(light['text-decoration'] ?? '')
    const [mark, markDark] = [device('.en-mark'), device('.dark .en-mark')]
    const out: string[] = []
    if (colour(light['background-color']) !== mark.tint) out.push('the tint')
    if (colour(line?.[2]) !== mark.hairline || line?.[1] !== mark.width) out.push('the 2px hairline')
    if (light['text-decoration-skip-ink'] !== 'none') out.push('the unbroken hairline')
    if (colour(light.color) !== colour(tokens.text.primary.light)) out.push('the primary ink')
    if (colour(dark['background-color']) !== markDark.tint || colour(dark['text-decoration-color']) !== markDark.hairline) out.push("the dark pair")
    if (colour(dark.color) !== colour(tokens.text.primary.dark)) out.push('the dark primary ink')
    if (Object.keys({ ...light, ...dark }).some((prop) => prop.startsWith('border')) || /en-marked/.test(css)) out.push("the marked block's bar")
    return out
  }

  it("paints .en-mark's tint and 2px hairline, unbroken, on the primary ink, light and dark", () => {
    expect(departures(CITATION_HIGHLIGHT_CSS)).toEqual([])
  })

  // Planted paints, each departing in one way (the first is the 22% sage it replaced, the second the block form).
  it.each([
    ['the 22% sage it replaced', CITATION_HIGHLIGHT_CSS.replace('background-color: #ECF2EE; color: #1A1A17; text-decoration: underline 2px #CFE0D6; text-decoration-skip-ink: none; text-underline-offset: calc(0.2632em - 2px);', 'background-color: rgba(79, 122, 99, 0.22); color: #1A1A17;'), ['the tint', 'the 2px hairline', 'the unbroken hairline']],
    ["the marked block's form, the bar beside the tint", CITATION_HIGHLIGHT_CSS.replace('text-decoration: underline 2px #CFE0D6; text-decoration-skip-ink: none; text-underline-offset: calc(0.2632em - 2px);', 'border-left: 3px solid #4F7A63;'), ['the 2px hairline', 'the unbroken hairline', "the marked block's bar"]],
    ['the secondary ink', CITATION_HIGHLIGHT_CSS.replace('color: #1A1A17;', 'color: inherit;'), ['the primary ink']],
    ['no dark pair', CITATION_HIGHLIGHT_CSS.split('\n')[0], ['the dark pair', 'the dark primary ink']],
  ])('names a paint with %s', (_name, css, expected) => {
    expect(css).not.toBe(CITATION_HIGHLIGHT_CSS)
    expect(departures(css)).toEqual(expected)
  })

  /** The reader's neutral sage from before D-044: the brand fill (tailwind.config.js) at 22%. */
  const sage = `rgba(${[1, 3, 5].map((i) => parseInt(tokens.brand.DEFAULT.slice(i, i + 2), 16)).join(',')},0.22)`
  /** Where the find paint departs from that sage: in the reader's own ink, with no hairline (a text decoration) and no
      bar (a border, or the marked block's class); in neither theme does it take the device's tint. */
  const findDepartures = (css: string): string[] => {
    const light = rule(css, '::highlight(copilot-find)')
    const dark = rule(css, '.dark ::highlight(copilot-find)')
    const tints = [device('.en-mark').tint, device('.dark .en-mark').tint]
    const props = Object.keys({ ...light, ...dark })
    const out: string[] = []
    if (colour(light['background-color']) !== sage) out.push('the neutral sage')
    if ([light, dark].some((paint) => tints.includes(colour(paint['background-color'])))) out.push("the device's tint")
    if (light.color !== 'inherit') out.push("the reader's own ink")
    if (props.some((prop) => /^text-(decoration|underline)/.test(prop))) out.push('no hairline')
    if (props.some((prop) => prop.startsWith('border')) || /en-marked/.test(css)) out.push('no bar')
    return out
  }

  it("a passage the server did not locate: the brand sage at 22% in the reader's own ink, no hairline, no bar", () => {
    expect(sage, 'the sage reads the brand token (anti-vacuity)').toBe('rgba(79,122,99,0.22)')
    expect(findDepartures(FIND_HIGHLIGHT_CSS)).toEqual([])
  })

  // Planted find paints, each departing in one way (the first is the device's paint under the find highlight's name).
  it.each([
    ["the device's paint", CITATION_HIGHLIGHT_CSS.replaceAll('copilot-citation', 'copilot-find'), ['the neutral sage', "the device's tint", "the reader's own ink", 'no hairline']],
    ['a hairline under the sage', FIND_HIGHLIGHT_CSS.replace('color: inherit;', 'color: inherit; text-decoration: underline 2px #CFE0D6;'), ['no hairline']],
    ["the device's dark tint in dark", `${FIND_HIGHLIGHT_CSS}\n.dark ::highlight(copilot-find) { background-color: rgba(127, 178, 149, 0.14); }`, ["the device's tint"]],
    ["the marked block's bar", FIND_HIGHLIGHT_CSS.replace('color: inherit;', 'color: inherit; border-left: 3px solid #4F7A63;'), ['no bar']],
  ])('names a find paint with %s', (_name, css, expected) => {
    expect(css).not.toBe(FIND_HIGHLIGHT_CSS)
    expect(findDepartures(css)).toEqual(expected)
  })
})


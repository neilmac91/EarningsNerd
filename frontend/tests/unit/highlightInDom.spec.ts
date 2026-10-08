import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  CITATION_HIGHLIGHT_CSS,
  __resetCitationHighlightStyleForTests,
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
          expect(highlightExcerptInDom(container, excerpt)).toBe(true)
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

    it('adopts the ::highlight stylesheet once and registers the highlight', () => {
      const container = document.createElement('div')
      container.innerHTML =
        '<p>Net income rose on higher services revenue during the quarter.</p>' +
        '<p>Operating expenses declined as headcount stayed flat through the period.</p>'
      document.body.appendChild(container)
      try {
        expect(
          highlightExcerptInDom(container, 'Net income rose on higher services revenue during the quarter'),
        ).toBe(true)
        expect(replaceSync).toHaveBeenCalledWith(CITATION_HIGHLIGHT_CSS)
        expect(CITATION_HIGHLIGHT_CSS).toMatch(/^::highlight\(copilot-citation\) \{/)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
        expect(doc.adoptedStyleSheets?.[0]).toBeInstanceOf(FakeSheet)
        expect(highlights.has('copilot-citation')).toBe(true)

        // Second highlight: same document, no second stylesheet.
        expect(
          highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat through the period'),
        ).toBe(true)
        expect(replaceSync).toHaveBeenCalledTimes(1)
        expect(doc.adoptedStyleSheets).toHaveLength(1)
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

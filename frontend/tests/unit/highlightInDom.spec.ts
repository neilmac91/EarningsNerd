import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  CITATION_HIGHLIGHT_CSS,
  highlightExcerptInDom,
} from '@/features/filings/components/copilot/highlightInDom'

// jsdom supports TreeWalker + Range but not scrollIntoView / the CSS Custom Highlight API; the
// helper feature-detects both, so here we just verify location + the block flash + scroll call.
describe('highlightExcerptInDom', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('locates an excerpt spanning multiple inline elements and flashes the enclosing block', () => {
    const container = document.createElement('div')
    container.innerHTML =
      '<p>Some intro.</p><p>Revenue <strong>increased</strong> to $391.0B this year.</p>'
    document.body.appendChild(container)

    const found = highlightExcerptInDom(container, 'Revenue increased to $391.0B this year')

    expect(found).toBe(true)
    expect(container.querySelectorAll('.citation-flash').length).toBe(1)
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()

    document.body.removeChild(container)
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

  // The `::highlight(copilot-citation)` paint lives in a constructed stylesheet adopted on first
  // use (Next 16.3's CSS pipeline rejects the pseudo-element in globals.css). jsdom has neither the
  // Highlight API nor constructable stylesheets, so stub both and check the wiring: the rule is
  // adopted exactly once, before the highlight is registered.
  it('adopts the ::highlight stylesheet once and registers the highlight when the API exists', () => {
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
    const saved = { CSSStyleSheet: g.CSSStyleSheet, Highlight: g.Highlight, highlights: g.CSS.highlights }
    g.CSSStyleSheet = FakeSheet
    g.Highlight = class {
      constructor(public range: Range) {}
    }
    g.CSS.highlights = highlights
    const doc = document as unknown as { adoptedStyleSheets: unknown[] }
    doc.adoptedStyleSheets = []

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
      expect(doc.adoptedStyleSheets[0]).toBeInstanceOf(FakeSheet)
      expect(highlights.has('copilot-citation')).toBe(true)

      // Second highlight: same document, no second stylesheet.
      expect(
        highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat through the period'),
      ).toBe(true)
      expect(replaceSync).toHaveBeenCalledTimes(1)
      expect(doc.adoptedStyleSheets).toHaveLength(1)
    } finally {
      document.body.removeChild(container)
      g.CSSStyleSheet = saved.CSSStyleSheet
      g.Highlight = saved.Highlight
      g.CSS.highlights = saved.highlights
    }
  })
})

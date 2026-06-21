import { describe, it, expect, vi, beforeEach } from 'vitest'
import { highlightExcerptInDom } from '@/features/filings/components/copilot/highlightInDom'

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
})

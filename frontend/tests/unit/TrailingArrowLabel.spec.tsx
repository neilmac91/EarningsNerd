/* =============================================================================
   TrailingArrowLabel.spec.tsx: the run holds the glyph with the last letter
   -----------------------------------------------------------------------------
   TrailingArrowLabel's no-wrap run holds its glyph with the label's last letter
   (and the marks that combine with it), not the whole last word (DESIGN_SYSTEM.md
   §4, Trailing arrow; E279). A word has no break inside it, so where the last
   word fits its line the result is the whole word with the glyph after it, as
   before; where the word alone is wider than its line, it can still break inside
   as its control lets a word break. A run that held the whole word ran a Copilot
   source's "Performance" 70px past its 110px row at 320px under 200% text
   (tests/e2e/reflow-200.spec.ts holds that row side to side). This spec holds
   the split itself, with no build: the words before the run, the run's letter,
   the glyph each `glyph` draws, and the label's words read whole.
============================================================================= */

import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TrailingArrowLabel } from '@/components/ui/TrailingArrowLabel'
import { ArrowRightIcon, ArrowSquareOutIcon } from '@/lib/icons'

function rendered(label: string, glyph?: 'arrow' | 'external') {
  const { container } = render(
    <a href="https://www.sec.gov/">
      <TrailingArrowLabel glyph={glyph} arrowClassName="ml-1 h-3 w-3">
        {label}
      </TrailingArrowLabel>
    </a>,
  )
  const link = container.querySelector('a')!
  const run = link.querySelector('span.whitespace-nowrap')!
  const glyphs = link.querySelectorAll('svg')
  return {
    // The text the link holds before the run: every node but the run.
    before: [...link.childNodes].filter((node) => node !== run).map((node) => node.textContent).join(''),
    letter: [...run.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE).map((node) => node.textContent).join(''),
    glyphs,
    words: link.textContent,
  }
}

/** The markup an icon draws alone, so a glyph can be named by what it draws. */
function drawn(Icon: typeof ArrowRightIcon) {
  const { container } = render(<Icon />)
  return container.querySelector('svg')!.innerHTML
}

describe('TrailingArrowLabel holds its glyph with the last letter (DESIGN_SYSTEM.md §4, Trailing arrow)', () => {
  it('holds the last letter alone in the run, the rest of the last word outside it', () => {
    const r = rendered('Item 7. MD&A – Products and Services Performance', 'external')
    expect(r.before).toBe('Item 7. MD&A – Products and Services Performanc')
    expect(r.letter).toBe('e')
    expect(r.words).toBe('Item 7. MD&A – Products and Services Performance')
  })

  it('holds a one-word label the same way, and a label ending in a stop or a space', () => {
    expect(rendered('Open').letter).toBe('n')
    expect(rendered('Open').before).toBe('Ope')
    expect(rendered('Original on SEC.gov').letter).toBe('v')
    expect(rendered('Item 7. MD&A.').letter).toBe('.')
    // A trailing space stays in the run, so the glyph never stands alone past a break after it.
    expect(rendered('Item 7. MD&A ').before).toBe('Item 7. MD&A')
    expect(rendered('Item 7. MD&A ').letter).toBe(' ')
  })

  it('keeps a combining mark with its letter', () => {
    // A plain e with a combining acute after it (U+0301): the two are one letter on screen.
    const r = rendered('Le caf' + 'e\u0301')
    expect(r.letter).toBe('e\u0301')
    expect(r.before).toBe('Le caf')
  })

  it('draws the arrow by default and the square for glyph="external", one glyph, aria-hidden, in the run', () => {
    const arrow = rendered('See all')
    const square = rendered('Original on SEC.gov', 'external')
    for (const r of [arrow, square]) {
      expect(r.glyphs).toHaveLength(1)
      expect(r.glyphs[0].getAttribute('aria-hidden')).toBe('true')
      expect(r.glyphs[0].closest('span.whitespace-nowrap')).not.toBeNull()
    }
    expect(drawn(ArrowRightIcon)).not.toBe(drawn(ArrowSquareOutIcon))
    expect(arrow.glyphs[0].innerHTML).toBe(drawn(ArrowRightIcon))
    expect(square.glyphs[0].innerHTML).toBe(drawn(ArrowSquareOutIcon))
  })
})

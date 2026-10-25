import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import DataNoteMark from '@/features/analysis/components/DataNoteMark'
import type { DataNote } from '@/features/analysis/lib/dataNotes'

const note = (kind: DataNote['kind'], letter = 'a') => ({ key: `${kind}-${letter}`, letter, kind, id: `analysis-data-note-${letter}` }) as unknown as DataNote

const marks = (container: HTMLElement) => [...container.querySelectorAll('[aria-hidden="true"]')] as HTMLElement[]

/**
 * The footnote system (DESIGN_SYSTEM.md, Data note mark): † and every note letter are one mark type, 11px figure face
 * at zero line-height, raised in their own ink, hidden from the accessibility tree (the figure's control names them in
 * words). A letter after † keeps a 2px gap: set flush, "†a" read as one cluster at 1x in dark, and two independent
 * readers dropped the letter (the metrics-table study's readout, 9e). In the table the marks hang in a gutter one mark
 * wide that a figure with no mark keeps as a spacer with no declared width.
 */
describe('DataNoteMark', () => {
  it('sets † and a letter as raised 11px marks in their own inks, hidden from screen readers', () => {
    const { container } = render(<DataNoteMark calculated note={note('review')} compact />)
    const [dagger, letter] = marks(container)
    for (const mark of [dagger, letter]) expect(mark).toHaveClass('relative', 'inline-block', 'font-figure', 'text-data-xs', 'leading-[0]', 'tracking-normal', '-top-[0.35em]')
    expect(dagger).toHaveTextContent('†')
    expect(dagger).toHaveClass('text-note-light', 'dark:text-note-dark')
    expect(letter).toHaveTextContent('a')
    expect(letter).toHaveClass('text-warning-light', 'dark:text-warning-data-dark')
    expect(container.textContent).toBe('†a')
  })

  it('keeps 2px between † and a following letter, in the table and beside a large figure', () => {
    for (const compact of [true, false]) {
      const { container, unmount } = render(<DataNoteMark calculated note={note('unknown')} compact={compact} />)
      const [dagger, letter] = marks(container)
      expect(letter, `compact=${compact}`).toHaveClass('ml-0.5', 'text-note-light', 'dark:text-note-dark')
      // In the table the gutter is the first mark's gap; beside a 24px figure the first mark takes 2px.
      if (compact) expect(dagger).not.toHaveClass('ml-0.5')
      else expect(dagger).toHaveClass('ml-0.5', '-top-[0.85em]')
      unmount()
    }
  })

  it('leaves a figure with no mark a gutter spacer in the table that only fills free space, and nothing elsewhere', () => {
    const { container, rerender } = render(<DataNoteMark compact />)
    const spacer = container.querySelector('[data-mark-gutter]')!
    expect(spacer).toHaveAttribute('aria-hidden', 'true')
    expect(spacer).toHaveClass('max-w-[var(--mark-gutter)]', 'grow', 'basis-0')
    // A declared width counts toward the line's minimum width and pushed a nine-glyph figure past its cell.
    expect(spacer.className).not.toMatch(/(?:^|\s)(?:min-)?w-/)
    rerender(<DataNoteMark />)
    expect(container.innerHTML).toBe('')
  })
})

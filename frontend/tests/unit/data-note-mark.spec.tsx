import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import DataNoteMark from '@/features/analysis/components/DataNoteMark'
import type { DataNote } from '@/features/analysis/lib/dataNotes'

const note = (kind: DataNote['kind'], letter = 'a') => ({ key: `${kind}-${letter}`, letter, kind, id: `analysis-data-note-${letter}` }) as unknown as DataNote

const marks = (container: HTMLElement) => [...container.querySelectorAll('[aria-hidden="true"]')] as HTMLElement[]

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const sources = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
  const full = path.join(dir, entry.name)
  if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sources(full)
  return /\.tsx$/.test(entry.name) ? [full] : []
})

/**
 * The footnote system (DESIGN_SYSTEM.md, Data note mark): † and every note letter are one mark type, 11px figure face
 * at zero line-height, raised in their own ink, hidden from the accessibility tree (the figure's control names them in
 * words). They stand as a staircase, the dagger low and the letter above it: raised level, "†a" read as one mark at 1x
 * in dark and five of six readers dropped the letter, where stepped, six of six read both (the metrics-table readout).
 * A letter after † keeps a 2px gap: set flush, two readers dropped it. In the table the marks hang in a gutter one mark
 * wide that a figure with no mark keeps as a spacer with no declared width. The large raise belongs to the 24px figures
 * alone: as the default it lifted the narrative's marks a full mark above their 12px line.
 */
describe('DataNoteMark', () => {
  it('sets † and a letter as raised 11px marks in their own inks, hidden from screen readers', () => {
    const { container } = render(<DataNoteMark calculated note={note('review')} compact />)
    const [dagger, letter] = marks(container)
    for (const mark of [dagger, letter]) expect(mark).toHaveClass('relative', 'inline-block', 'font-figure', 'text-data-xs', 'leading-[0]', 'tracking-normal')
    expect(dagger).toHaveTextContent('†')
    expect(dagger).toHaveClass('text-note-light', 'dark:text-note-dark')
    expect(letter).toHaveTextContent('a')
    expect(letter).toHaveClass('text-warning-light', 'dark:text-warning-data-dark')
    expect(container.textContent).toBe('†a')
  })

  it('stands the letter above the dagger: 0.2em and 0.5em beside 12-14px text, 0.55em and 0.85em beside a 24px figure', () => {
    for (const [props, daggerRaise, letterRaise] of [
      [{ compact: true }, '-top-[0.2em]', '-top-[0.5em]'],
      [{}, '-top-[0.2em]', '-top-[0.5em]'],
      [{ large: true }, '-top-[0.55em]', '-top-[0.85em]'],
    ] as const) {
      const { container, unmount } = render(<DataNoteMark calculated note={note('unknown')} {...props} />)
      const [dagger, letter] = marks(container)
      expect(dagger, JSON.stringify(props)).toHaveClass(daggerRaise)
      expect(letter, JSON.stringify(props)).toHaveClass(letterRaise)
      unmount()
    }
  })

  it('keeps 2px between † and a following letter, and 2px before the first mark outside the table', () => {
    for (const props of [{ compact: true }, {}, { large: true }]) {
      const { container, unmount } = render(<DataNoteMark calculated note={note('unknown')} {...props} />)
      const [dagger, letter] = marks(container)
      expect(letter, JSON.stringify(props)).toHaveClass('ml-0.5', 'text-note-light', 'dark:text-note-dark')
      // In the table the gutter is the first mark's gap; elsewhere the first mark takes 2px.
      if ('compact' in props) expect(dagger).not.toHaveClass('ml-0.5')
      else expect(dagger, JSON.stringify(props)).toHaveClass('ml-0.5')
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

  it('gives the large raise only to the 24px figures: the KPI value and the evidence dialog figure', () => {
    // Each place that asks for it, by file: DataNoteMark's own `large`, and SourceValue's `largeMarks`, which passes it on.
    const ask = /<DataNoteMark\b[^>]*\blarge\b(?!Marks)[^>]*\/>|<SourceValue\b[^>]*\blargeMarks\b/g
    const asks = ['features', 'components', 'app'].flatMap((dir) => sources(path.join(FRONTEND, dir)))
      .flatMap((file) => [...readFileSync(file, 'utf8').matchAll(ask)].map((match) => {
        const kind = match[0].startsWith('<SourceValue') ? 'largeMarks' : /\blarge=\{largeMarks\}/.test(match[0]) ? 'passes largeMarks on' : 'large'
        return `${path.relative(FRONTEND, file)}: ${kind}`
      }))
      .sort()
    expect(asks).toEqual([
      'features/analysis/components/KpiStrip.tsx: largeMarks', // the KPI value
      'features/analysis/components/SourceValue.tsx: large', // the evidence dialog's figure
      'features/analysis/components/SourceValue.tsx: passes largeMarks on',
    ])
    // Anti-vacuity: the scan sees a planted ask of each kind.
    expect('<DataNoteMark note={n} large /> <SourceValue largeMarks point={p}>'.match(ask)).toHaveLength(2)
  })
})

import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import DataNoteMark from '@/features/analysis/components/DataNoteMark'
import type { DataNote } from '@/features/analysis/lib/dataNotes'

const note = (kind: DataNote['kind'], reasons: string[] = kind === 'review' ? ['source_conflict'] : kind === 'unknown' ? ['legacy_unknown'] : ['not_in_dataset'], letter = 'a') =>
  ({ key: `${kind}-${reasons.join()}`, letter, kind, reasons, id: `analysis-data-note-${letter}` }) as unknown as DataNote

const marks = (container: HTMLElement) => [...container.querySelectorAll('[aria-hidden="true"]')] as HTMLElement[]

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const sources = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
  const full = path.join(dir, entry.name)
  if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sources(full)
  return /\.tsx$/.test(entry.name) ? [full] : []
})

const SURFACES = [{ compact: true }, {}, { large: true }] as const

/**
 * The footnote system (DESIGN_SYSTEM.md, Data note mark; D-061): a figure carries a mark only where its note questions
 * the number, a review note with a reason other than the record-only legacy_calculation. The mark is one type, an 11px
 * letter in the figure face at zero line-height, raised in the neutral note ink and never warning ink, hidden from the
 * accessibility tree (the figure's control names it in words). A calculated figure carries no dagger: its control says
 * "calculated". The mark keeps 2px from its figure on every surface: set flush, readers dropped marks at 1x in dark. In
 * the table it hangs in a gutter one mark and its gap wide that a figure with no mark keeps as a spacer with no
 * declared width. The large raise belongs to the 24px figures alone: as the default it lifted the narrative's marks a
 * full mark above their 12px line.
 */
describe('DataNoteMark', () => {
  it('sets a marked letter as a raised 11px mark in the note ink, never warning ink, and no dagger, hidden from screen readers', () => {
    for (const props of SURFACES) {
      const { container, unmount } = render(<DataNoteMark calculated note={note('review')} {...props} />)
      const [letter, ...rest] = marks(container)
      expect(rest, JSON.stringify(props)).toEqual([])
      expect(letter).toHaveClass('relative', 'inline-block', 'font-figure', 'text-data-xs', 'leading-[0]', 'tracking-normal')
      expect(letter).toHaveClass('text-note-light', 'dark:text-note-dark')
      expect(letter.className).not.toMatch(/warning/)
      expect(letter).toHaveAttribute('data-note-letter', 'a')
      expect(letter).toHaveAttribute('data-note-kind', 'review')
      expect(container.textContent).toBe('a')
      unmount()
    }
  })

  it('raises the letter 0.5em beside 12-14px text and 0.85em beside a 24px figure', () => {
    for (const [props, raise] of [[{ compact: true }, '-top-[0.5em]'], [{}, '-top-[0.5em]'], [{ large: true }, '-top-[0.85em]']] as const) {
      const { container, unmount } = render(<DataNoteMark note={note('review')} {...props} />)
      expect(marks(container)[0], JSON.stringify(props)).toHaveClass(raise)
      unmount()
    }
  })

  it('keeps 2px before the mark on every surface, the table included', () => {
    for (const props of SURFACES) {
      const { container, unmount } = render(<DataNoteMark note={note('review')} {...props} />)
      expect(marks(container)[0], JSON.stringify(props)).toHaveClass('ml-0.5')
      unmount()
    }
  })

  it('draws no mark for a note that does not question the number, and draws one for a mixed note', () => {
    const unmarked = [note('review', ['legacy_calculation']), note('unknown'), note('unavailable')]
    for (const quiet of unmarked) {
      for (const props of SURFACES) {
        const { container, unmount } = render(<DataNoteMark calculated note={quiet} {...props} />)
        // The table keeps its gutter as the spacer; elsewhere nothing renders, a dagger least of all.
        if ('compact' in props) expect(container.querySelector('[data-mark-gutter]'), quiet.key).not.toBeNull()
        else expect(container.innerHTML, quiet.key).toBe('')
        expect(container.querySelector('[data-note-letter]')).toBeNull()
        expect(container.textContent).toBe('')
        unmount()
      }
    }
    const { container } = render(<DataNoteMark note={note('review', ['legacy_calculation', 'source_check_needed'])} />)
    expect(container.querySelector('[data-note-letter="a"]')).not.toBeNull()
  })

  it('announces "calculated" in words with no glyph, and names only a marked note', () => {
    for (const [props, spoken, visible] of [
      [{ calculated: true }, ', calculated', ''],
      [{ calculated: true, note: note('review', ['legacy_calculation']) }, ', calculated', ''],
      [{ calculated: true, note: note('review') }, ', calculated, data note a', 'a'],
      [{ note: note('unknown') }, null, ''],
    ] as const) {
      const { container, unmount } = render(<DataNoteMark announce {...props} />)
      expect(container.querySelector('.sr-only')?.textContent ?? null, JSON.stringify(props)).toBe(spoken)
      expect(marks(container).map((mark) => mark.textContent).join(''), JSON.stringify(props)).toBe(visible)
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

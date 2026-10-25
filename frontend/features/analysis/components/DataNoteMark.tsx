import type { DataNote } from '@/features/analysis/lib/dataNotes'

export function dataNoteDescription(note?: DataNote | null) {
  return note ? `data note ${note.letter}` : ''
}

// Every mark, † and letter alike, is one footnote type: 11px data face, zero line-height (a mark never sizes its row),
// raised as a superscript in its own ink, and inline-block, so the source button's dotted underline stops at the figure
// (in the table, inside one wrapper: see below).
// Smaller, raised and differently inked, a mark can no longer read as the figure's last glyph ("$4.1B†a").
const MARK = 'relative inline-block font-figure text-data-xs leading-[0] tracking-normal'

/** The enclosing figure/control owns the accessible name; marks never add a Tab stop. */
export default function DataNoteMark({ note, calculated = false, announce = false, compact = false, small = false }: {
  note?: DataNote | null
  calculated?: boolean
  announce?: boolean
  /** The metrics table: marks hang in a gutter one mark wide (--mark-gutter, set by the table) that every figure in a
   *  column keeps, so a marked and an unmarked figure share one right edge. With no mark the gutter is an empty spacer
   *  that grows from nothing up to one mark into free space only (a declared width would count toward the line's
   *  minimum width and push a full nine-glyph figure past its cell). Other surfaces set the marks after a gap. */
  compact?: boolean
  /** Beside a 12px line outside the table (the KPI change line): the table's raise, with the first mark's 2px gap. */
  small?: boolean
}) {
  if (!note && !calculated) return compact ? <span aria-hidden="true" data-mark-gutter className="max-w-[var(--mark-gutter)] grow basis-0" /> : null
  // Superscript height: a mark's top at about the figure's cap height (Geist Mono caps are 0.71em), so a 12px figure or
  // line (the table's, the KPI change line) raises it 0.35em and the 24px KPI and dialog figures 0.85em. Outside the
  // table the first mark keeps a gap;
  // in the table the gutter is the gap. A letter after † keeps a 2px gap everywhere: set flush, "†a" read as one
  // cluster at 1x in dark, and two independent readers dropped the letter (the study's 1x readout).
  const raise = compact || small ? '-top-[0.35em]' : '-top-[0.85em]'
  const gap = compact ? '' : 'ml-0.5'
  const marks = (
    <>
      {calculated && <span aria-hidden="true" className={`${MARK} ${raise} ${gap} text-note-light dark:text-note-dark`}>†</span>}
      {note && <sup aria-hidden="true" data-note-letter={note.letter} data-note-kind={note.kind} className={`${MARK} ${raise} ${calculated ? 'ml-0.5' : gap} ${note.kind === 'review' ? 'text-warning-light dark:text-warning-data-dark' : 'text-note-light dark:text-note-dark'}`}>{note.letter}</sup>}
    </>
  )
  return (
    <>
      {/* In the table the figure's line is a flex row, which blockifies its children, and a parent's text decoration
          reaches every in-flow flex item, inline-block or not: the source button's dotted underline ran again under
          each mark, raised with it. One wrapper is the flex item instead, so the marks inside it stay inline-blocks,
          which a decoration skips. */}
      {compact ? <span data-marks>{marks}</span> : marks}
      {/* Anchor the absolute sr-only box inside the table's scroll boundary. Without this
          containing block, an off-screen comparison can extend the document's scroll width. */}
      {announce && <span className="relative"><span className="sr-only">{`, ${[calculated ? 'calculated' : '', dataNoteDescription(note)].filter(Boolean).join(', ')}`}</span></span>}
    </>
  )
}

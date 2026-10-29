import { markedNote, type DataNote } from '@/features/analysis/lib/dataNotes'

/** A figure's note in words, for its control's accessible name: only a note that puts a mark beside the figure
 *  (noteMarksFigure, D-061). A record-only, unknown or unavailable note is read in the evidence dialog instead. */
export function dataNoteDescription(note?: DataNote | null) {
  const marked = markedNote(note)
  return marked ? `data note ${marked.letter}` : ''
}

// A note mark is one footnote type: an 11px letter in the figure face at zero line-height (a mark never sizes its row),
// raised as a superscript in the neutral note ink, and inline-block, so the KPI value's dotted underline stops at the
// figure. Smaller, raised and differently inked, it cannot read as the figure's last glyph.
const MARK = 'relative inline-block font-figure text-data-xs leading-[0] tracking-normal'
/** The mark's classes, for KpiStrip's hidden probe of a mark's advance (a letter in them, with no data-note-letter). */
export const NOTE_MARK = MARK

/** The enclosing figure/control owns the accessible name; marks never add a Tab stop. A figure carries a letter only
 *  where its note questions the number (noteMarksFigure): unknown, unavailable and record-only notes draw nothing here,
 *  and a calculated figure carries no glyph at all (the sentence above the table names the calculated metrics). */
export default function DataNoteMark({ note, calculated = false, announce = false, compact = false, large = false }: {
  note?: DataNote | null
  /** Read only with `announce`: a calculated figure is named "calculated" in words and draws no mark. */
  calculated?: boolean
  announce?: boolean
  /** The metrics table: the mark hangs in a gutter one mark and its gap wide (--mark-gutter, set by the table) that
   *  every figure in a column keeps, so a marked and an unmarked figure share one right edge. With no mark the gutter is
   *  an empty spacer that grows from nothing up to its width into free space only (a declared width would count toward
   *  the line's minimum width and push a full nine-glyph figure past its cell). */
  compact?: boolean
  /** Beside a 24px figure (the KPI value, the evidence dialog's figure). Every other mark sits beside 12-14px text. */
  large?: boolean
}) {
  const marked = markedNote(note)
  // Raised near the figure's cap height (Geist Mono caps are 0.71em): 0.5em beside 12-14px text, 0.85em beside a 24px
  // figure. The mark keeps 2px from its figure on every surface, in the table too: set flush, readers dropped a mark at
  // 1x in dark (the metrics-table readout).
  const spoken = [calculated ? 'calculated' : '', dataNoteDescription(marked)].filter(Boolean).join(', ')
  return (
    <>
      {marked
        ? <sup aria-hidden="true" data-note-letter={marked.letter} data-note-kind={marked.kind} className={`${MARK} ${large ? '-top-[0.85em]' : '-top-[0.5em]'} ml-0.5 text-note-light dark:text-note-dark`}>{marked.letter}</sup>
        : compact ? <span aria-hidden="true" data-mark-gutter className="max-w-[var(--mark-gutter)] grow basis-0" /> : null}
      {/* Anchor the absolute sr-only box inside the table's scroll boundary. Without this
          containing block, an off-screen comparison can extend the document's scroll width. */}
      {announce && spoken && <span className="relative"><span className="sr-only">{`, ${spoken}`}</span></span>}
    </>
  )
}

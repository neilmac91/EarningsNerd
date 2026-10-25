import type { DataNote } from '@/features/analysis/lib/dataNotes'

export function dataNoteDescription(note?: DataNote | null) {
  return note ? `data note ${note.letter}` : ''
}

// Every mark, † and letter alike, is one footnote type: 11px data face, zero line-height (a mark never sizes its row),
// raised as a superscript in its own ink, and inline-block, so the KPI value's dotted underline stops at the figure.
// Smaller, raised and differently inked, a mark can no longer read as the figure's last glyph ("$4.1B†a").
const MARK = 'relative inline-block font-figure text-data-xs leading-[0] tracking-normal'

/** The enclosing figure/control owns the accessible name; marks never add a Tab stop. */
export default function DataNoteMark({ note, calculated = false, announce = false, compact = false, large = false }: {
  note?: DataNote | null
  calculated?: boolean
  announce?: boolean
  /** The metrics table: marks hang in a gutter one mark wide (--mark-gutter, set by the table) that every figure in a
   *  column keeps, so a marked and an unmarked figure share one right edge. With no mark the gutter is an empty spacer
   *  that grows from nothing up to one mark into free space only (a declared width would count toward the line's
   *  minimum width and push a full nine-glyph figure past its cell). Other surfaces set the marks after a gap. */
  compact?: boolean
  /** Beside a 24px figure (the KPI value, the evidence dialog's figure). Every other mark sits beside 12-14px text. */
  large?: boolean
}) {
  if (!note && !calculated) return compact ? <span aria-hidden="true" data-mark-gutter className="max-w-[var(--mark-gutter)] grow basis-0" /> : null
  // A staircase: the dagger low, near the figure's x-height, and the letter above it, near its cap height (Geist Mono
  // caps are 0.71em). Raised level with each other, "†a" read as one mark at 1x in dark: five of six readers dropped the
  // letter; stepped, six of six read both (the metrics-table readout). Beside 12-14px text the dagger rises 0.2em and the
  // letter 0.5em; beside a 24px figure, 0.55em and 0.85em. Outside the table the first mark keeps a gap; in the table
  // the gutter is the gap. A letter after † keeps 2px everywhere: set flush, two readers dropped it.
  const dagger = large ? '-top-[0.55em]' : '-top-[0.2em]'
  const letter = large ? '-top-[0.85em]' : '-top-[0.5em]'
  const gap = compact ? '' : 'ml-0.5'
  return (
    <>
      {calculated && <span aria-hidden="true" className={`${MARK} ${dagger} ${gap} text-note-light dark:text-note-dark`}>†</span>}
      {note && <sup aria-hidden="true" data-note-letter={note.letter} data-note-kind={note.kind} className={`${MARK} ${letter} ${calculated ? 'ml-0.5' : gap} ${note.kind === 'review' ? 'text-warning-light dark:text-warning-data-dark' : 'text-note-light dark:text-note-dark'}`}>{note.letter}</sup>}
      {/* Anchor the absolute sr-only box inside the table's scroll boundary. Without this
          containing block, an off-screen comparison can extend the document's scroll width. */}
      {announce && <span className="relative"><span className="sr-only">{`, ${[calculated ? 'calculated' : '', dataNoteDescription(note)].filter(Boolean).join(', ')}`}</span></span>}
    </>
  )
}

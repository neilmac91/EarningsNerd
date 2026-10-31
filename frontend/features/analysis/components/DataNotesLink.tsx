'use client'

import { noteMarksFigure, type DataNote } from '@/features/analysis/lib/dataNotes'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'

/** Reveal the report's note before moving focus; hidden details never receive a dead jump. */
export function openDataNote(id: string) {
  const target = document.getElementById(id)
  if (!target) return
  let ancestor = target.parentElement
  while (ancestor) {
    if (ancestor instanceof HTMLDetailsElement) ancestor.open = true
    ancestor = ancestor.parentElement
  }
  target.focus({ preventScroll: true })
  target.scrollIntoView?.({ block: 'center', behavior: 'auto' })
}

/** A surface's Notes chip lists only the letters its figures show (noteMarksFigure, D-061): the table's, a chart's and
 *  the narrative's chips all pass every note they hold and take the marked ones here. With none, there is no chip. */
export default function DataNotesLink({ notes }: { notes: DataNote[] }) {
  const marked = notes.filter(noteMarksFigure)
  if (marked.length === 0) return null
  const letters = marked.map((note) => note.letter).join(', ')
  return (
    <button type="button" className={sourceTraceChipClass(false)} onClick={() => openDataNote(marked[0].id)} aria-label={`Review data notes ${letters}`}>
      Notes {letters}
    </button>
  )
}

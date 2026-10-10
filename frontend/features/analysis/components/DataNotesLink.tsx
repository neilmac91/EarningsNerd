'use client'

import type { DataNote } from '@/features/analysis/lib/dataNotes'
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

export default function DataNotesLink({ notes }: { notes: DataNote[] }) {
  if (notes.length === 0) return null
  return (
    <button type="button" className={sourceTraceChipClass(false)} onClick={() => openDataNote(notes[0].id)} aria-label={`Review data notes ${notes.map((note) => note.letter).join(', ')}`}>
      Notes {notes.map((note) => note.letter).join(', ')}
    </button>
  )
}

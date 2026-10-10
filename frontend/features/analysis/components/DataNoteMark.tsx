import type { DataNote } from '@/features/analysis/lib/dataNotes'

export function dataNoteDescription(note?: DataNote | null) {
  return note ? `data note ${note.letter}` : ''
}

/** The enclosing figure/control owns the accessible name; marks never add a Tab stop. */
export default function DataNoteMark({ note, calculated = false, announce = false }: {
  note?: DataNote | null
  calculated?: boolean
  announce?: boolean
}) {
  if (!note && !calculated) return null
  return (
    <>
      {calculated && <span aria-hidden="true" className="ml-0.5 text-text-secondary-light dark:text-text-secondary-dark">†</span>}
      {note && <sup aria-hidden="true" data-note-letter={note.letter} data-note-kind={note.kind} className={`ml-0.5 font-data text-data-xs leading-[0] ${note.kind === 'review' ? 'text-warning-light dark:text-warning-dark' : 'text-text-tertiary-light dark:text-text-secondary-dark'}`}>{note.letter}</sup>}
      {announce && <span className="sr-only">{`, ${[calculated ? 'calculated' : '', dataNoteDescription(note)].filter(Boolean).join(', ')}`}</span>}
    </>
  )
}

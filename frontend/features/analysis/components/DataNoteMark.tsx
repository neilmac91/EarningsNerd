import type { DataNote } from '@/features/analysis/lib/dataNotes'

export function dataNoteDescription(note?: DataNote | null) {
  return note ? `data note ${note.letter}` : ''
}

/** The enclosing figure/control owns the accessible name; marks never add a Tab stop. */
export default function DataNoteMark({ note, calculated = false, announce = false, compact = false }: {
  note?: DataNote | null
  calculated?: boolean
  announce?: boolean
  /** Dense table affixes retain their type size while using half-pixel spacing at the default root size. */
  compact?: boolean
}) {
  if (!note && !calculated) return null
  const spacing = compact ? 'ml-[0.03125rem]' : 'ml-0.5'
  return (
    <>
      {calculated && <span aria-hidden="true" className={`${spacing} text-text-secondary-light dark:text-text-secondary-dark`}>†</span>}
      {note && <sup aria-hidden="true" data-note-letter={note.letter} data-note-kind={note.kind} className={`${spacing} font-data text-data-xs leading-[0] ${note.kind === 'review' ? 'text-warning-light dark:text-warning-dark' : 'text-text-tertiary-light dark:text-text-secondary-dark'}`}>{note.letter}</sup>}
      {/* Anchor the absolute sr-only box inside the table's scroll boundary. Without this
          containing block, an off-screen comparison can extend the document's scroll width. */}
      {announce && <span className="relative"><span className="sr-only">{`, ${[calculated ? 'calculated' : '', dataNoteDescription(note)].filter(Boolean).join(', ')}`}</span></span>}
    </>
  )
}

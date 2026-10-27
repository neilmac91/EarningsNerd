'use client'

import { usePublicAccess } from './PublicAccessProvider'
import { heldAccessLines, type AccessMode } from '@/features/marketing/lib/access'

/**
 * The hero's access line. The lines it keeps the height of (heldAccessLines: the checking line it opens on, the mode's
 * own and the closed one) share one grid cell, the shown one visible and the rest invisible and aria-hidden, so the
 * line keeps one height as registration readiness lands and the page under it keeps its place: as the checking line
 * became the invite line, a scrolled page moved 20px at 320px and 40 to 80px under 200% text (E220). An unconfirmed
 * read's longer line joins the cell and can still grow it.
 */
export default function PublicAccessLine({ accessMode }: { accessMode: AccessMode }) {
  const access = usePublicAccess(accessMode)
  const held = heldAccessLines(accessMode)
  const lines = held.includes(access.line) ? held : [...held, access.line]
  return (
    <p className="grid text-sm text-text-secondary-light dark:text-text-secondary-dark">
      {lines.map((line) =>
        line === access.line ? (
          <span key={line} className="col-start-1 row-start-1">
            {line}
          </span>
        ) : (
          <span key={line} aria-hidden="true" className="invisible col-start-1 row-start-1">
            {line}
          </span>
        ),
      )}
    </p>
  )
}

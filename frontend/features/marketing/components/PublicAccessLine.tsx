'use client'

import { usePublicAccess } from './PublicAccessProvider'
import { heldAccessLines, type AccessMode } from '@/features/marketing/lib/access'

/**
 * The hero's access line. The lines it keeps the height of (heldAccessLines: the checking line it opens on and the
 * mode's own) share one grid cell, the shown one visible and the rest invisible and aria-hidden, so the line keeps one
 * height as registration readiness answers open and the page under it holds still: as the checking line became the
 * invite line, the page moved up 20px at 320 and 390px and 40px under 200% text (E220). Where the checking line wraps
 * and the mode's does not, the settled line sits over an empty line, the trade chief design chose on #1686. A closed or
 * unconfirmed answer joins the cell when shown and can still grow it.
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

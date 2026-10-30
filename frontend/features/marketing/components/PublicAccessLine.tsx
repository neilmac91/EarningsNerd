'use client'

import { Fragment } from 'react'
import { usePublicAccess } from './PublicAccessProvider'
import { heldAccessLines, type AccessMode } from '@/features/marketing/lib/access'

/**
 * The hero's access line. The lines it keeps the height of (heldAccessLines: the checking line it opens on and the
 * mode's own) share one grid cell, the shown one visible and the rest invisible and aria-hidden, so the line keeps one
 * height as registration readiness answers open and the page under it holds still: as the checking line became the
 * invite line, the page moved up 20px from 320 to 460px and 40 to 120px under 200% text (E220). The checking line
 * takes no more rows than the invite line at any width, so the settled line fills the cell and leaves no empty rows
 * under it (E224); public mode's line is longer still. A closed or unconfirmed answer joins the cell when shown and can
 * still grow it. A space between the cells renders nothing in the grid and keeps the lines apart in the server HTML's
 * text.
 */
export default function PublicAccessLine({ accessMode }: { accessMode: AccessMode }) {
  const access = usePublicAccess(accessMode)
  const held = heldAccessLines(accessMode)
  const lines = held.includes(access.line) ? held : [...held, access.line]
  return (
    <p className="grid text-sm text-text-secondary-light dark:text-text-secondary-dark">
      {lines.map((line, index) => (
        <Fragment key={line}>
          {index > 0 && ' '}
          {line === access.line ? (
            <span className="col-start-1 row-start-1">{line}</span>
          ) : (
            <span aria-hidden="true" className="invisible col-start-1 row-start-1">
              {line}
            </span>
          )}
        </Fragment>
      ))}
    </p>
  )
}

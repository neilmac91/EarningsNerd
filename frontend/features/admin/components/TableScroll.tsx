'use client'

import { useId, useRef, type ReactNode } from 'react'
import { useOverflowRegion } from '@/hooks/useOverflowRegion'

/**
 * The scroll box of an admin list's table (DESIGN_SYSTEM.md §4 "Admin pages"): a table wider than its card scrolls
 * inside the card, never the page. `relative` makes the box the containing block of what its rows position
 * absolutely, the `sr-only` labels included: without it they were laid out against the page, outside the box's
 * clip, and FeedbackRow's status labels took the page to 1090px at 390. While the table is wider than the box, a
 * line above it says so and the box is a named region in the Tab order, so a keyboard user can scroll it (the
 * pattern of SummaryBlocks' GenericTable, through useOverflowRegion).
 */
export default function TableScroll({ label, children }: { label: string; children: ReactNode }) {
  const boxRef = useRef<HTMLDivElement>(null)
  const hintId = useId()
  const { overflowing, regionProps } = useOverflowRegion(boxRef, {
    label: `Scrollable table: ${label}`,
    describedBy: hintId,
  })
  return (
    <>
      {overflowing && (
        <p id={hintId} className="px-cap-6 py-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          Scroll horizontally to read all columns.
        </p>
      )}
      {/* The role is written out, not read from regionProps, so tests/unit/dialogAllowlist.spec.ts can prove it is
          no dialog's. */}
      <div
        ref={boxRef}
        role={overflowing ? 'region' : undefined}
        tabIndex={regionProps.tabIndex}
        aria-label={regionProps['aria-label']}
        aria-describedby={regionProps['aria-describedby']}
        className="relative overflow-x-auto focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      >
        {children}
      </div>
    </>
  )
}

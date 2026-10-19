// The marked copy's measure, in a module without 'use client' so a server component reads these classes as strings
// (lessons/frontend-client-exports-need-next-build.md): the landing's evidence row (HeroExample) is one.

/**
 * A marked copy (components/ui/MarkedCopy.tsx) is a query container in em, so it follows the reader's text size where
 * `sm:` or a rem column cannot. Narrower than 13em of its own width, its margin and twins give way and a row's inset
 * beside the margin goes with them; the marker in the heading stays. The one measure, written whole in each class
 * (Tailwind reads classes as written): the grid's columns, the margin's collapse, and the rows' inset.
 */
/** The margin's column (2.25rem, 2.75rem from sm) beside the copy, and the copy alone below the measure. */
export const markedCopyColumnsClass = 'grid grid-cols-[2.25rem_minmax(0,1fr)] sm:grid-cols-[2.75rem_minmax(0,1fr)] [@container(width<13em)]:grid-cols-[minmax(0,1fr)]'
/** The margin and its twins, gone below the measure. */
export const markedMarginCollapseClass = '[@container(width<13em)]:hidden'
/** A row's inset beside the margin (12px, 14px from sm), gone with it. Every row of a marked copy takes it. */
export const markedRowInsetClass = 'pl-3 sm:pl-3.5 [@container(width<13em)]:pl-0'

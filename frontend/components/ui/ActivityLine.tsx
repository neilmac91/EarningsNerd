/* =============================================================================
   ActivityLine (components/ui/ActivityLine.tsx)
   -----------------------------------------------------------------------------
   A run in progress in words beside one sage pulse dot, the words in the
   secondary ink (a run that reports how far it has got shows a bar instead, as
   the summary's generating card does). Activity is never a Notice, of any
   variant (DESIGN_SYSTEM.md §4 › Inline notice): the Copilot rail's "Reading
   the filing…" and the analysis page's history fetch are this line.

   The dot sits in a box as tall as the line's own text-sm line (h-5 and the
   line height are both 1.25rem, so the two grow together under enlarged text)
   and keeps to the first line when the words wrap; the words take their own
   min-w-0 span, so a second line starts under the first line's words, not
   under the dot. The dot is brand-strong in both themes, aria-hidden, and
   static under reduced motion. The line owns its type size, which the box is
   measured against, so it takes no className.

   The live region is the caller's: `role="status"` where the line is its own
   (the analysis page's history fetch), none where a container already is one
   (the Copilot's reading card, which keeps the region the plan card's sentence
   lands in).

   A pulsing round mark ships only here and in Badge's live dot:
   tests/unit/pulsingMarkAllowlist.spec.ts fails a class list that draws one
   anywhere else.
   ========================================================================== */
import type { ReactNode } from 'react'

export interface ActivityLineProps {
  /** What is running, in the product's words. */
  children: ReactNode
  /** `status` where the line is its own live region; omit it where a container already announces it. */
  role?: 'status'
}

export function ActivityLine({ children, role }: ActivityLineProps) {
  return (
    // The role as a literal: dialogAllowlist.spec.ts reads a role={…} it cannot prove a literal as a dialog.
    <p role={role ? 'status' : undefined} className="flex items-start gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
      <span aria-hidden="true" className="flex h-5 flex-none items-center">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong motion-reduce:animate-none dark:bg-brand-strong-dark" />
      </span>
      <span className="min-w-0 break-words">{children}</span>
    </p>
  )
}

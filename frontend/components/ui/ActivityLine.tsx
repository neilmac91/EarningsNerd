/* =============================================================================
   ActivityLine (components/ui/ActivityLine.tsx)
   -----------------------------------------------------------------------------
   A run in progress in words beside one sage pulse dot, the words in the
   secondary ink (a run that reports how far it has got shows a bar instead, as
   the summary's generating card does). Activity is never a Notice, of any
   variant (DESIGN_SYSTEM.md §4 › Inline notice): the Copilot rail's "Reading
   the filing…", the analysis page's history fetch, the trend analysis's
   "Assembling the numbers…" and "Writing…", and /delete-account's "Checking
   whether you are logged in…" are this line.

   The dot sits in a box as tall as the line's own text-sm line (h-5 and the
   line height are both 1.25rem, so the two grow together under enlarged text)
   and keeps to the first line when the words wrap; the words take their own
   min-w-0 span, so a second line starts under the first line's words, not
   under the dot. The dot is brand-strong in both themes, aria-hidden, and
   static under reduced motion. The line owns its type size, which the box is
   measured against, so it takes no className.

   The line takes no role (the type refuses one). A status region announces
   text added to it, never text it was created with. On the analysis page the
   coverage region exists before the history fetch's words arrive (it is
   mounted until the coverage answer settles, a failed read included), so they
   are heard. The Copilot's reading card is created with "Reading the filing…"
   in it, so the card does not announce that line; the rail's own sr-only
   status region, mounted before any question, says it, and the card is a
   status region for the plan card's sentence, which replaces the line in the
   same element. A caller whose words must be heard mounts its region first
   (review-checked).

   A pulsing round mark ships only here and in Badge's live dot:
   tests/unit/pulsingMarkAllowlist.spec.ts fails a class list that draws one
   anywhere else.
   ========================================================================== */
import type { ReactNode } from 'react'

export interface ActivityLineProps {
  /** What is running, in the product's words. */
  children: ReactNode
}

export function ActivityLine({ children }: ActivityLineProps) {
  return (
    <p className="flex items-start gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
      <span aria-hidden="true" className="flex h-5 flex-none items-center">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong motion-reduce:animate-none dark:bg-brand-strong-dark" />
      </span>
      <span className="min-w-0 break-words">{children}</span>
    </p>
  )
}

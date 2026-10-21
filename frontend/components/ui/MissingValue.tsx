/* =============================================================================
   MissingValue (components/ui/MissingValue.tsx)
   -----------------------------------------------------------------------------
   A value the page does not have: a figure, a date, a name, a plan line. The
   eye sees the missing-value token, the one sanctioned em-dash
   (docs/voice-and-style.md), and assistive tech hears words in its place:
   `label`, "unavailable" by default. A site where "unavailable" would claim
   more than its data says passes words of its own ("no cohort" for an invite
   with none, "Not included" for a plan without the row's feature). The token
   is aria-hidden, so a screen reader reads the words and never "em dash".

   `relative` makes the element the containing block of its sr-only words, so
   they stay inside a truncating cell or a table's scroll box instead of
   widening the page (lessons/frontend-sr-only-needs-a-positioned-clip.md). The
   ink is the caller's: the element inherits the colour around it, and
   `className` gives it a cell's muted pair.

   The token is written here and nowhere else in the app:
   tests/unit/missingValueToken.spec.ts fails it wherever else it renders.
   ========================================================================== */
import { cx } from './cx'

export interface MissingValueProps {
  /** What assistive tech reads in the token's place: words that say what is missing, never more than the data says. */
  label?: string
  className?: string
}

export function MissingValue({ label = 'unavailable', className }: MissingValueProps) {
  return (
    <span className={cx('relative', className)}>
      <span aria-hidden="true">—</span>
      <span className="sr-only">{label}</span>
    </span>
  )
}

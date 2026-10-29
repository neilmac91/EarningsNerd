/* =============================================================================
   Notice — components/ui/Notice.tsx  (v2.2)
   -----------------------------------------------------------------------------
   The compact INLINE form notice: icon + title + message + optional action in
   one hairline-tinted row — form/auth flows, inline card states. Replaces the
   app-owned StateCard (variants error/info/success). The variant is written at
   every call site: StateCard's default `info` painted guidance boxes loud blue
   (lessons/frontend-status-colors-for-status-only.md), and the generating card's
   whimsy line sat in that tint for three months. Activity (a run in progress) is
   no Notice of any variant (DESIGN_SYSTEM.md §4 › Inline notice, §9).

   Four variants are states, each in its own tint: error, warning (a limit
   near or reached, a risk the reader weighs), info and success. `neutral` is
   guidance, not a state: the hairline alone, no tint, and the info glyph in
   the brand's ink, as a dialog's neutral prompt takes the brand (E196 (2)).

   NESTING RULE (codified v2.2): GuidanceCard is a STANDALONE centered panel —
   never nest it inside a Card. Inside a Card or a form flow, this inline
   icon + message + action pattern is the right scale.

   A Notice is static — it has no interactive states of its own; the `action`
   slot takes a <Button> (usually secondary/ghost, size="sm"), which carries
   hover/active/focus-visible. role="alert" for error (interrupts the reader);
   role="status" for the others. Both themes audited: title = primary ink,
   message = secondary/secondary-dark, icons ≥3:1 inside their tints.

   The row wraps. The text column's basis is 9rem (about 20 characters), so
   where it cannot keep that beside the glyph (a card on a phone at 200%
   text) it goes under the glyph at the Notice's whole inner width: the glyph
   sits alone over the title, and the title, description and action share
   the full width. The title breaks a long word, as the description does. No
   container query: a container-type collapses a Notice wherever a parent
   sizes it to its content. Gate: tests/e2e/reflow-200.spec.ts.

   A Notice owns its alignment: its root sets text-left, so inside a column
   that centres its text (the waitlist page below lg) its title and
   description stay at the start with the glyph and the action row (E120;
   gate: tests/unit/waitlistSuccessCard.spec.tsx, through the waitlist form).
============================================================================= */

import { type ReactNode } from 'react'
import { CheckCircleIcon, InfoIcon, WarningCircleIcon, WarningIcon } from '@/lib/icons'
import { cx } from './cx'

export type NoticeVariant = 'error' | 'warning' | 'info' | 'success' | 'neutral'

const WRAP: Record<NoticeVariant, string> = {
  error: cx(
    'border-error-light/25 bg-error-light/[0.06]',
    'dark:border-error-dark/25 dark:bg-error-dark/10',
  ),
  warning: cx(
    'border-warning-light/25 bg-warning-light/[0.06]',
    'dark:border-warning-dark/25 dark:bg-warning-dark/10',
  ),
  info: cx(
    'border-info-light/25 bg-info-light/[0.06]',
    'dark:border-info-dark/25 dark:bg-info-dark/10',
  ),
  success: cx(
    'border-success-light/25 bg-success-light/[0.06]',
    'dark:border-success-dark/25 dark:bg-success-dark/10',
  ),
  // Guidance is no state, so it takes no state's tint: the hairline alone, on whatever ground it sits.
  neutral: 'border-border-light dark:border-white/10',
}

/** The variant's tint, its hairline and ground, for a surface of another shape that states the same thing: the
    Copilot's error bubble keeps the thread's tail in the error tint (E196 (3)), and the dashboard's limit banner and
    the verification banner keep a banner's shape in the warning tint (E196 (2)). The tint stays the primitive's, so a
    change to it reaches those surfaces too. Each borrower is listed, with the variant it writes, in
    tests/unit/statusTintResidue.spec.ts's TINT_BORROWED. */
export function noticeTint(variant: NoticeVariant): string {
  return WRAP[variant]
}

const ICON: Record<NoticeVariant, string> = {
  error: 'text-error-light dark:text-error-dark',
  warning: 'text-warning-light dark:text-warning-dark',
  // The glyph is a graphic (3:1 floor) — info.light holds 4.3:1 inside the
  // tint. Text at this size would need info.text (see Badge).
  info: 'text-info-light dark:text-info-dark',
  success: 'text-success-light dark:text-success-dark',
  // The brand never signals a state, so guidance's glyph takes it (a dialog's neutral prompt does too).
  neutral: 'text-brand-strong dark:text-brand-strong-dark',
}

/** The variant's glyph, Phosphor's from lib/icons at regular weight, the system's weight wherever its stroke holds a
    device pixel (DESIGN.md › Icons), 18px in the variant's ink (ICON): the warning circle for an error, the warning
    triangle for a warning, the info circle for info and for guidance, the check circle for a success. */
const GLYPH: Record<NoticeVariant, typeof InfoIcon> = {
  error: WarningCircleIcon,
  warning: WarningIcon,
  info: InfoIcon,
  success: CheckCircleIcon,
  neutral: InfoIcon,
}

function DefaultIcon({ variant }: { variant: NoticeVariant }) {
  const Glyph = GLYPH[variant]
  return <Glyph className="h-[18px] w-[18px]" aria-hidden="true" />
}

export interface NoticeProps {
  /** Written at every call site, never a default: `info` and `warning` are advisory states in their inks, guidance
   * is `neutral`, and activity is no Notice (gate: tests/unit/statusTintResidue.spec.ts). */
  variant: NoticeVariant
  /** Defaults per variant (GLYPH). Pass null to remove. */
  icon?: ReactNode
  title: ReactNode
  /** Supporting copy under the title. */
  description?: ReactNode
  /** Usually a small secondary/ghost <Button> ("Try again", "Reset password"). */
  action?: ReactNode
  className?: string
}

export function Notice({ variant, icon, title, description, action, className }: NoticeProps) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cx('flex flex-wrap items-start gap-3 rounded-lg border px-4 py-3.5 text-left', WRAP[variant], className)}
    >
      {icon === null ? null : (
        <span aria-hidden="true" className={cx('mt-px flex-none', ICON[variant])}>
          {icon ?? <DefaultIcon variant={variant} />}
        </span>
      )}
      <div className="min-w-0 flex-[1_1_9rem]">
        <p className="break-words text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{title}</p>
        {description ? (
          <p className="mt-0.5 break-words text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
            {description}
          </p>
        ) : null}
        {action ? <div className="mt-2.5 flex flex-wrap items-center gap-2">{action}</div> : null}
      </div>
    </div>
  )
}

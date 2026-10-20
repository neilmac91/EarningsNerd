/* =============================================================================
   Badge — components/ui/Badge.tsx
   -----------------------------------------------------------------------------
   Variants a filings product actually needs:
     - pro / brand:  the tint chip — brand.weak bg + brand.strong text +
                     brand.border hairline (NEVER brand.DEFAULT as text on cream).
     - solid (v2.2): the primary-button colorway as a chip — brand.strong fill +
                     white label; dark FLIPS to navy ink on brand.dark (same flip
                     as the primary button). For brand-weak TINTED grounds, where
                     the tint chips visually vanish (the "Recommended" plan chip).
     - free/neutral: quiet panel chip.
     - info (v2.2):  interim-filing tone — info tint (10-Q / 6-K type chips).
                     Light label is info.text #1D4ED8: info.light inside its own
                     10% tint is 4.3:1 — icon/graphic only there, fails AA at 12px.
     - warning (v2.2): warning-token tint — replaces raw-amber hand-rolls
                     (UnverifiedBadge).
     - the status set (BadgeStatusVariant): success, error, info-status,
                     warning-status and neutral-status are STATUS chips (a
                     summary is ready, a run failed, an invite is pending,
                     expired or revoked): the status ink on one quiet ground
                     (STATUS), white with a hairline in light and the bare
                     hairline in dark. info, warning and neutral are the tints
                     and the quiet chip, so their status forms take names of
                     their own. Not a tint: the success ink inside any tint of
                     itself falls under 4.5:1 at 12px (4.2:1 in 10% on panel);
                     on the quiet ground it holds 5.0:1, error 6.5:1. No fill
                     in dark: on a row hovered with white/5 a fill of its own
                     would take error to 3.9:1, info to 4.26:1 and neutral to
                     4.27:1; with none, error, the lowest, holds 4.6:1 there
                     (5.3:1 on the card at rest). The admin lists' status chips
                     render the set (InviteStatusBadge, FeedbackStatusBadge),
                     and tests/unit/statusChipContrast.spec.ts measures every
                     member on their rows.
                     Status is never told with beat/miss: those are data
                     colours.
     - beat / miss:  earnings surprise — gain/loss DATA colors (kept distinct
                     from the brand accent), soft tint bg, auto ▲/▼. A
                     direction only, never a status.
     - new:          new-filing pulse — the brand tint (TINT, as brand) + a
                     calm pulsing dot in its sage ink (respects
                     prefers-reduced-motion). A new filing is news, not a
                     caution, so it takes no warning tint (D-032). Its label
                     holds 5.8:1 in light, 5.9:1 on the dark card.
   Casing: `pro` UPPERCASES its label; brand and every other variant stay
   sentence case. icon={null} strips a variant's automatic affordance (the
   ▲ / ▼ glyph or the pulse dot).
   v3: pro's uppercase tracking moved off the 0.05em wider utility onto the
   one eyebrow token (`tracking-eyebrow` = --track-eyebrow 0.08em).
============================================================================= */

import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './cx'

/** Badge's status set: a status ink on the one status ground (DESIGN_SYSTEM.md §4, "Status chip"). */
export type BadgeStatusVariant = 'success' | 'error' | 'info-status' | 'warning-status' | 'neutral-status'

export type BadgeVariant =
  | 'pro'
  | 'brand'
  | 'solid'
  | 'free'
  | 'neutral'
  | 'info'
  | 'warning'
  | BadgeStatusVariant
  | 'beat'
  | 'miss'
  | 'new'

const BASE = 'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold'

const TINT = cx(
  'border border-brand-border bg-brand-weak text-brand-strong',
  'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
)
const QUIET = cx(
  'border border-border-light bg-white text-text-secondary-light',
  'dark:border-border-dark dark:bg-white/5 dark:text-text-secondary-dark',
)
/** The status set's ground: QUIET's, with no fill in dark (the header above). */
const STATUS = cx('border border-border-light bg-white', 'dark:border-border-dark dark:bg-transparent')

const VARIANT: Record<BadgeVariant, string> = {
  pro: cx(TINT, 'uppercase tracking-eyebrow'),
  brand: TINT,
  // border-transparent keeps solid metric-identical to the bordered tint chips
  // it replaces on tinted grounds.
  solid: cx('border border-transparent bg-brand-strong text-white', 'dark:bg-brand-dark dark:text-background-dark'),
  free: QUIET,
  neutral: QUIET,
  info: 'bg-info-light/10 text-info-text dark:bg-info-dark/15 dark:text-info-dark',
  warning: 'bg-warning-light/10 text-warning-light dark:bg-warning-dark/15 dark:text-warning-dark',
  success: cx(STATUS, 'text-success-light dark:text-success-dark'),
  error: cx(STATUS, 'text-error-light dark:text-error-dark'),
  'info-status': cx(STATUS, 'text-info-text dark:text-info-dark'),
  'warning-status': cx(STATUS, 'text-warning-light dark:text-warning-dark'),
  'neutral-status': cx(STATUS, 'text-text-tertiary-light dark:text-text-secondary-dark'),
  beat: 'bg-gain-soft text-gain-text dark:bg-gain-soft-dark dark:text-gain-dark',
  miss: 'bg-loss-soft text-loss-text dark:bg-loss-soft-dark dark:text-loss-dark',
  new: TINT,
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  /** Override the variant's automatic affordance (▲ / ▼ / pulse dot). Pass null to remove. */
  icon?: ReactNode
}

export function Badge({ variant = 'neutral', icon, className, children, ...rest }: BadgeProps) {
  const auto: ReactNode =
    icon !== undefined ? (
      icon
    ) : variant === 'beat' ? (
      // eslint-disable-next-line no-restricted-syntax -- aria-hidden direction glyph, not type (DS-08 exemption)
      <span aria-hidden="true" className="text-[10px] leading-none">▲</span>
    ) : variant === 'miss' ? (
      // eslint-disable-next-line no-restricted-syntax -- aria-hidden direction glyph, not type (DS-08 exemption)
      <span aria-hidden="true" className="text-[10px] leading-none">▼</span>
    ) : variant === 'new' ? (
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current animate-pulse motion-reduce:animate-none" />
    ) : null

  return (
    <span className={cx(BASE, VARIANT[variant], className)} {...rest}>
      {auto}
      {children}
    </span>
  )
}

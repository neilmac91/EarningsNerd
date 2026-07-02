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
     - beat / miss:  earnings surprise — gain/loss DATA colors (kept distinct
                     from the brand accent), soft tint bg, auto ▲/▼.
     - new:          new-filing pulse — warning tint + a calm pulsing dot
                     (respects prefers-reduced-motion).
   Casing: `pro` UPPERCASES its label; brand and every other variant stay
   sentence case. icon={null} strips a variant's automatic affordance —
   beat/miss/new double as plain TONAL RECIPES that way (e.g. a delta chip
   with no glyph, or `new`'s warning tint without the pulse).
============================================================================= */

import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './cx'

export type BadgeVariant =
  | 'pro'
  | 'brand'
  | 'solid'
  | 'free'
  | 'neutral'
  | 'info'
  | 'warning'
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

const VARIANT: Record<BadgeVariant, string> = {
  pro: cx(TINT, 'uppercase tracking-wider'),
  brand: TINT,
  // border-transparent keeps solid metric-identical to the bordered tint chips
  // it replaces on tinted grounds.
  solid: cx('border border-transparent bg-brand-strong text-white', 'dark:bg-brand-dark dark:text-background-dark'),
  free: QUIET,
  neutral: QUIET,
  info: 'bg-info-light/10 text-info-text dark:bg-info-dark/15 dark:text-info-dark',
  warning: 'bg-warning-light/10 text-warning-light dark:bg-warning-dark/15 dark:text-warning-dark',
  beat: 'bg-gain-soft text-gain-text dark:bg-gain-soft-dark dark:text-gain-dark',
  miss: 'bg-loss-soft text-loss-text dark:bg-loss-soft-dark dark:text-loss-dark',
  new: 'bg-warning-light/10 text-warning-light dark:bg-warning-dark/15 dark:text-warning-dark',
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
      <span aria-hidden="true" className="text-[10px] leading-none">▲</span>
    ) : variant === 'miss' ? (
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

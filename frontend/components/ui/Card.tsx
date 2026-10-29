/* =============================================================================
   Card — components/ui/Card.tsx
   -----------------------------------------------------------------------------
   Cards LIFT, never tint: lighter-than-page fill + hairline + soft e-shadow in
   light; in dark they separate via fill contrast + hairline with shadow:none.
   `interactive` hover BRIGHTENS (toward white + brand hairline), never darkens
   — and never hover:opacity. Pressed takes the sage tint, its dark twin in dark.
   Focus-visible = brand ring for keyboard users.
============================================================================= */

import { type ElementType, type HTMLAttributes } from 'react'
import { cx } from './cx'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  /** Semantic element to render — `<Card as="section">` (v2.2: three app sites
      hand-copied the recipe onto <section>/<article> before this existed). */
  as?: ElementType
  /** Hover/active/focus affordances for clickable cards (wrap in <a>/<button> for semantics). */
  interactive?: boolean
  /** The light lift; dark cards carry none whatever this says. `none` keeps the panel fill and the hairline with no
      shadow, for an input area that is not content: the analysis page's company and period form (Control, a level
      under the content cards; DESIGN.md Elevation & Depth). */
  elevation?: 'none' | 'e1' | 'e2' | 'e3'
  /** Corner step on the 16 / 24 scale (cards 16; a featured banner 24). A `rounded-2xl` in
      className would NOT override the recipe: the stylesheet emits it before `rounded-xl`. */
  radius?: 'xl' | '2xl'
}

const ELEVATION = { none: '', e1: 'shadow-e1', e2: 'shadow-e2', e3: 'shadow-e3' } as const
const RADIUS = { xl: 'rounded-xl', '2xl': 'rounded-2xl' } as const

export function Card({
  as: Tag = 'div',
  interactive = false,
  elevation = 'e2',
  radius = 'xl',
  className,
  ...rest
}: CardProps) {
  return (
    <Tag
      className={cx(
        RADIUS[radius],
        'border border-border-light bg-panel-light',
        ELEVATION[elevation],
        'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        interactive &&
          cx(
            'cursor-pointer transition-colors duration-fast',
            'hover:border-brand-border hover:bg-white',
            'active:bg-brand-weak/60 dark:active:bg-brand-weak-dark',
            'focus-visible:outline-none focus-visible:shadow-ring-brand',
            'dark:hover:border-brand-border-dark dark:focus-visible:shadow-ring-brand-dark',
          ),
        className,
      )}
      {...rest}
    />
  )
}

/* The sections' side padding is the capped step, px-cap-5 = min(1.25rem, 5vw) (E120; gate:
   earningsnerd/surface-padding-cap). A caller's numbered step on top (className="px-6") loses to it: the
   stylesheet emits px-cap-5 after every numbered step, and cx does no tailwind-merge. */
export function CardHeader({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx('flex items-center gap-3 border-b border-border-light px-cap-5 py-4 dark:border-border-dark', className)}
      {...rest}
    />
  )
}

/** Card title — sentence case in the heading register (14px/600, heading ink).
    NOT an eyebrow: uppercase tracked micro-labels are reserved for METRIC
    labels (table headers, KPI labels) — never card titles (DESIGN_SYSTEM §3).
    v2.1 change: this shipped as an uppercase eyebrow, contradicting that rule. */
export function CardTitle({ className, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cx(
        'text-sm font-semibold text-text-primary-light dark:text-text-primary-dark',
        className,
      )}
      {...rest}
    />
  )
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('px-cap-5 py-4', className)} {...rest} />
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        'flex items-center gap-3 border-t border-border-light px-cap-5 py-3 dark:border-border-dark',
        className,
      )}
      {...rest}
    />
  )
}

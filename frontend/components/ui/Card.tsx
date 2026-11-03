/* =============================================================================
   Card — components/ui/Card.tsx
   -----------------------------------------------------------------------------
   Cards LIFT, never tint: lighter-than-page fill + hairline + soft e-shadow in
   light; in dark they separate via fill contrast + hairline with shadow:none.
   A card whose action cannot be undone takes tone="danger": its hairline in
   the status error, in both themes (E283).
   `interactive` hover BRIGHTENS (toward white + brand hairline), never darkens
   — and never hover:opacity. Pressed takes the sage tint, its dark twin in dark.
   Focus-visible = brand ring for keyboard users.
   A caller sets what the card offers through its props (tone, radius, elevation,
   interactive), never a class on top that competes with one it sets here: cx
   merges nothing, so stylesheet order decides (gate:
   tests/unit/cardClassesNoOverrides.spec.tsx, which reads the sections too; D-076).
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
  /** The hairline. `danger` draws it in the status error, for a card whose action cannot be undone: deleting the
      account, on the settings page and on /delete-account (DESIGN_SYSTEM.md Card / panel). Set it through the prop,
      never a border colour on top: cx does no tailwind-merge, so two border colours win by stylesheet order, and
      Card's own dark hairline beat the settings card's dark override until E283 (a design selector in
      eslint.config.mjs fails a border colour written in a Card's className). */
  tone?: 'default' | 'danger'
}

const ELEVATION = { none: '', e1: 'shadow-e1', e2: 'shadow-e2', e3: 'shadow-e3' } as const
const RADIUS = { xl: 'rounded-xl', '2xl': 'rounded-2xl' } as const
/** Each tone's hairline, both themes in one string so a tone's colours never mix with another's. The error at 40%
    reads about 2:1 against the panel (2.05 in light, 1.93 in dark), where the default hairline reads 1.19 and 1.36. */
const HAIRLINE = {
  default: 'border border-border-light dark:border-white/10',
  danger: 'border border-error-light/40 dark:border-error-dark/40',
} as const

export function Card({
  as: Tag = 'div',
  interactive = false,
  elevation = 'e2',
  radius = 'xl',
  tone = 'default',
  className,
  ...rest
}: CardProps) {
  return (
    <Tag
      className={cx(
        RADIUS[radius],
        HAIRLINE[tone],
        'bg-panel-light',
        ELEVATION[elevation],
        'dark:bg-panel-dark dark:shadow-none',
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

/* =============================================================================
   Card — components/ui/Card.tsx
   -----------------------------------------------------------------------------
   Cards LIFT, never tint: lighter-than-page fill + hairline + soft e-shadow in
   light; in dark they separate via fill contrast + hairline with shadow:none.
   `interactive` hover BRIGHTENS (toward white + brand hairline), never darkens
   — and never hover:opacity. Focus-visible = brand ring for keyboard users.
============================================================================= */

import { type HTMLAttributes } from 'react'
import { cx } from './cx'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Hover/active/focus affordances for clickable cards (wrap in <a>/<button> for semantics). */
  interactive?: boolean
  elevation?: 'e1' | 'e2' | 'e3'
}

const ELEVATION = { e1: 'shadow-e1', e2: 'shadow-e2', e3: 'shadow-e3' } as const

export function Card({ interactive = false, elevation = 'e2', className, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        'rounded-xl border border-border-light bg-panel-light',
        ELEVATION[elevation],
        'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        interactive &&
          cx(
            'cursor-pointer transition-colors duration-fast',
            'hover:border-brand-border hover:bg-white',
            'active:bg-brand-weak/60',
            'focus-visible:outline-none focus-visible:shadow-ring-brand',
            'dark:hover:border-brand-border-dark dark:focus-visible:shadow-ring-brand-dark',
          ),
        className,
      )}
      {...rest}
    />
  )
}

export function CardHeader({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx('flex items-center gap-3 border-b border-border-light px-5 py-4 dark:border-border-dark', className)}
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
  return <div className={cx('px-5 py-4', className)} {...rest} />
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        'flex items-center gap-3 border-t border-border-light px-5 py-3 dark:border-border-dark',
        className,
      )}
      {...rest}
    />
  )
}

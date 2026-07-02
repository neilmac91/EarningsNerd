/* =============================================================================
   GuidanceCard — components/ui/GuidanceCard.tsx
   -----------------------------------------------------------------------------
   The system states a financial app needs, as one guidance surface:
     - empty:  brand-tint icon + a concrete next step (role="status").
     - error:  error-tint icon + honest copy + retry (role="alert").
   For loading, use Skeleton/SkeletonText in place of the content instead —
   a spinner card hides layout; bones preserve it.

   NAMING (v2.1): shipped in v2 as ui/StateCard — renamed because the app
   already owns components/StateCard.tsx (notice card, 10 importers) and both
   sit one letter from StatCard (the KPI tile). The app's StateCard keeps its
   name; this surface is the empty/error guidance card only.
============================================================================= */

import { type ReactNode } from 'react'
import { cx } from './cx'

export type GuidanceCardVariant = 'empty' | 'error'

export interface GuidanceCardProps {
  variant?: GuidanceCardVariant
  /** Defaults: magnifier (empty) / alert circle (error). */
  icon?: ReactNode
  title: string
  description?: ReactNode
  /** Usually a <Button> — primary for empty, secondary for error retry. */
  action?: ReactNode
  className?: string
}

const ICON_WRAP: Record<GuidanceCardVariant, string> = {
  empty: cx(
    'border-brand-border bg-brand-weak text-brand-strong',
    'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
  ),
  error: cx(
    'border-error-light/25 bg-error-light/10 text-error-light',
    'dark:border-error-dark/25 dark:bg-error-dark/10 dark:text-error-dark',
  ),
}

function DefaultIcon({ variant }: { variant: GuidanceCardVariant }) {
  return variant === 'error' ? (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
      <path d="M12 7.5v5.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="12" cy="16.4" r="1" fill="currentColor" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.7" />
      <path d="m15.8 15.8 3.7 3.7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}

export function GuidanceCard({ variant = 'empty', icon, title, description, action, className }: GuidanceCardProps) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cx(
        'flex flex-col items-center rounded-xl border border-border-light bg-panel-light px-6 py-10 text-center shadow-e2',
        'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        className,
      )}
    >
      <span className={cx('flex h-11 w-11 items-center justify-center rounded-full border', ICON_WRAP[variant])}>
        {icon ?? <DefaultIcon variant={variant} />}
      </span>
      <h3 className="mt-4 text-base font-semibold">{title}</h3>
      {description ? (
        <p className="mt-1.5 max-w-[38ch] text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-5 flex items-center gap-2">{action}</div> : null}
    </div>
  )
}

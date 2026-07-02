/* =============================================================================
   Notice — components/ui/Notice.tsx  (v2.2)
   -----------------------------------------------------------------------------
   The compact INLINE form notice: icon + title + message + optional action in
   one hairline-tinted row — form/auth flows, inline card states. Replaces the
   app-owned StateCard (variants error/info/success).

   NESTING RULE (codified v2.2): GuidanceCard is a STANDALONE centered panel —
   never nest it inside a Card. Inside a Card or a form flow, this inline
   icon + message + action pattern is the right scale.

   A Notice is static — it has no interactive states of its own; the `action`
   slot takes a <Button> (usually secondary/ghost, size="sm"), which carries
   hover/active/focus-visible. role="alert" for error (interrupts the reader);
   role="status" for info/success. Both themes audited: title = primary ink,
   message = secondary/secondary-dark, icons ≥3:1 inside their tints.
============================================================================= */

import { type ReactNode } from 'react'
import { cx } from './cx'

export type NoticeVariant = 'error' | 'info' | 'success'

const WRAP: Record<NoticeVariant, string> = {
  error: cx(
    'border-error-light/25 bg-error-light/[0.06]',
    'dark:border-error-dark/25 dark:bg-error-dark/10',
  ),
  info: cx(
    'border-info-light/25 bg-info-light/[0.06]',
    'dark:border-info-dark/25 dark:bg-info-dark/10',
  ),
  success: cx(
    'border-success-light/25 bg-success-light/[0.06]',
    'dark:border-success-dark/25 dark:bg-success-dark/10',
  ),
}

const ICON: Record<NoticeVariant, string> = {
  error: 'text-error-light dark:text-error-dark',
  // The glyph is a graphic (3:1 floor) — info.light holds 4.3:1 inside the
  // tint. Text at this size would need info.text (see Badge).
  info: 'text-info-light dark:text-info-dark',
  success: 'text-success-light dark:text-success-dark',
}

/** Outline glyphs matched to Phosphor regular weight (same set as GuidanceCard). */
function DefaultIcon({ variant }: { variant: NoticeVariant }) {
  if (variant === 'error') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
        <path d="M12 7.5v5.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        <circle cx="12" cy="16.4" r="1" fill="currentColor" />
      </svg>
    )
  }
  if (variant === 'success') {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
        <path d="m8.2 12.3 2.6 2.6 5-5.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
      <path d="M12 11v5.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="12" cy="7.6" r="1" fill="currentColor" />
    </svg>
  )
}

export interface NoticeProps {
  variant?: NoticeVariant
  /** Defaults per variant (alert / info / check circles). Pass null to remove. */
  icon?: ReactNode
  title: ReactNode
  /** Supporting copy under the title. */
  description?: ReactNode
  /** Usually a small secondary/ghost <Button> ("Retry", "Reset password"). */
  action?: ReactNode
  className?: string
}

export function Notice({ variant = 'info', icon, title, description, action, className }: NoticeProps) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cx('flex items-start gap-3 rounded-lg border px-4 py-3.5', WRAP[variant], className)}
    >
      {icon === null ? null : (
        <span aria-hidden="true" className={cx('mt-px flex-none', ICON[variant])}>
          {icon ?? <DefaultIcon variant={variant} />}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{title}</p>
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

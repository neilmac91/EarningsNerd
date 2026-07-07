'use client'

import { CheckCircleIcon, WarningCircleIcon, XCircleIcon } from '@/lib/icons'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ShareInvite from '@/features/admin/components/ShareInvite'

export interface BulkInviteOutcome {
  email: string
  ok: boolean
  link?: string
  error?: string
}

interface BulkResultSummaryProps {
  outcomes: BulkInviteOutcome[]
  skipped: string[]
}

/**
 * Inline breakdown of a bulk-invite run. Rendered only when something needs attention
 * (a failure or a skip); an all-success run is reported purely via a toast by the parent.
 * Wrapped in an aria-live region so the outcome is announced to screen readers.
 */
export default function BulkResultSummary({ outcomes, skipped }: BulkResultSummaryProps) {
  const succeeded = outcomes.filter((o) => o.ok)
  const failed = outcomes.filter((o) => !o.ok)

  if (outcomes.length === 0 && skipped.length === 0) return null

  return (
    <div
      aria-live="polite"
      className="mt-4 space-y-4 rounded-lg border border-border-light bg-panel-light p-4 dark:border-white/10 dark:bg-panel-dark"
    >
      {succeeded.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-success-light dark:text-success-dark">
            <CheckCircleIcon className="h-4 w-4" />
            {succeeded.length} invite{succeeded.length === 1 ? '' : 's'} sent
          </div>
          <ul className="space-y-1.5">
            {succeeded.map((o) => (
              <li
                key={o.email}
                className="flex flex-wrap items-center justify-between gap-2 rounded bg-background-light px-2.5 py-1.5 dark:bg-white/5"
              >
                <span className="truncate text-sm text-text-primary-light dark:text-text-primary-dark">
                  {o.email}
                </span>
                {o.link && (
                  <div className="flex flex-wrap items-center gap-2">
                    <CopyLinkButton link={o.link} />
                    <ShareInvite link={o.link} email={o.email} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {failed.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
            <XCircleIcon className="h-4 w-4" />
            {failed.length} failed
          </div>
          <ul className="space-y-1.5">
            {failed.map((o) => (
              <li
                key={o.email}
                className="rounded bg-error-light/10 px-2.5 py-1.5 dark:bg-error-dark/15"
              >
                <span className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
                  {o.email}
                </span>
                <span className="block text-xs text-error-light dark:text-error-dark">
                  {o.error || 'Unknown error'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {skipped.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-text-tertiary-light dark:text-text-secondary-dark">
            <WarningCircleIcon className="h-4 w-4" />
            {skipped.length} skipped
          </div>
          <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            {skipped.join(', ')}: already invited or invalid.
          </p>
        </div>
      )}
    </div>
  )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircleIcon, CopyIcon, WarningCircleIcon, XCircleIcon } from '@/lib/icons'

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

function CopyLinkButton({ link }: { link: string }) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clear the "Copied" flash timer on unmount so we never setState on an unmounted node.
  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded-md border border-border-light bg-panel-light px-2 py-1 text-xs font-medium text-text-secondary-light transition-colors hover:bg-brand-weak dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-white/5"
    >
      <CopyIcon className="h-3.5 w-3.5" />
      {copied ? 'Copied' : 'Copy link'}
    </button>
  )
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
                className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-background-light px-2.5 py-1.5 dark:bg-white/5"
              >
                <span className="truncate text-sm text-text-primary-light dark:text-text-primary-dark">
                  {o.email}
                </span>
                {o.link && <CopyLinkButton link={o.link} />}
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
                className="rounded-md bg-error-light/10 px-2.5 py-1.5 dark:bg-error-dark/15"
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
            {skipped.join(', ')} — already invited or invalid.
          </p>
        </div>
      )}
    </div>
  )
}

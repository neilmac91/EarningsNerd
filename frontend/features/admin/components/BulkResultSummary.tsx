'use client'

import { Fragment } from 'react'
import { CheckCircleIcon, WarningCircleIcon, XCircleIcon } from '@/lib/icons'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ShareInvite from '@/features/admin/components/ShareInvite'
import AddressText from '@/features/auth/components/AddressText'

export interface BulkInviteOutcome {
  email: string
  ok: boolean
  link?: string
  /** The API's `emailed` flag: the backend emails best-effort, so a created invite may not have been sent. */
  emailed?: boolean
  error?: string
}

interface BulkResultSummaryProps {
  outcomes: BulkInviteOutcome[]
  skipped: string[]
  /** "Email invites" was on for this run. Off, every invite is a link to share by hand. */
  emailRequested: boolean
}

/** The created group's heading: what was created and, when email was asked for, how many were emailed. */
function createdSummary(created: BulkInviteOutcome[], emailRequested: boolean): string {
  if (!emailRequested) return `${created.length} invite link${created.length === 1 ? '' : 's'} created`
  return `${created.length} created · ${created.filter((o) => o.emailed).length} emailed`
}

/**
 * Inline breakdown of a bulk-invite run, rendered whenever the run created, failed or skipped anything;
 * the parent's toast says the same in brief. Each created invite keeps its Copy link, and one that was
 * not emailed says so, so the links still to share by hand are plain.
 * Wrapped in an aria-live region so the outcome is announced to screen readers.
 */
export default function BulkResultSummary({ outcomes, skipped, emailRequested }: BulkResultSummaryProps) {
  const succeeded = outcomes.filter((o) => o.ok)
  const failed = outcomes.filter((o) => !o.ok)

  if (outcomes.length === 0 && skipped.length === 0) return null

  return (
    // Its inset and its rows' take E120's cap (E242): at 320px under 200% text p-4 and px-2.5 left a row 110px, narrower
    // than its Copy link and Share invite buttons (129px at their narrowest) and than an address's domain ("example.com").
    <div
      aria-live="polite"
      className="mt-4 space-y-4 rounded-lg border border-border-light bg-panel-light p-cap-4 dark:border-white/10 dark:bg-panel-dark"
    >
      {succeeded.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-success-light dark:text-success-dark">
            <CheckCircleIcon className="h-4 w-4" />
            {createdSummary(succeeded, emailRequested)}
          </div>
          <ul className="space-y-1.5">
            {succeeded.map((o) => (
              <li
                key={o.email}
                className="flex flex-wrap items-center justify-between gap-2 rounded bg-background-light px-cap-2.5 py-1.5 dark:bg-white/5"
              >
                {/* The address shows whole: it breaks after its @ (AddressText), and inside a part only where the part is
                    longer than the row (min-w-0, overflow-wrap), where truncate cut it to 110px at 320px under 200% text
                    (E242). */}
                <span className="min-w-0 break-words text-sm text-text-primary-light dark:text-text-primary-dark">
                  <AddressText address={o.email} />
                </span>
                {o.link && (
                  <div className="flex flex-wrap items-center gap-2">
                    {emailRequested && !o.emailed && (
                      <span className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Not emailed</span>
                    )}
                    <CopyLinkButton link={o.link} />
                    {/* The share options open in a dialog: under 200% text they cannot fit the row (E242). */}
                    <ShareInvite link={o.link} email={o.email} optionsIn="dialog" />
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
            {/* A failed row sits on the created rows' ground, its reason in the error ink: the group's heading already
                says these failed, and a tint behind each row was a status box of its own (E196 (4)). */}
            {failed.map((o) => (
              <li
                key={o.email}
                className="rounded bg-background-light px-cap-2.5 py-1.5 dark:bg-white/5"
              >
                {/* Set as a created row's address is: unbroken, a long one ran out of the row and scrolled the page
                    sideways, at 320px even at the default size (E242). */}
                <span className="break-words text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
                  <AddressText address={o.email} />
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
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-text-tertiary-light dark:text-text-tertiary-dark">
            <WarningCircleIcon className="h-4 w-4" />
            {skipped.length} skipped
          </div>
          {/* Each entry breaks as an address does (AddressText, overflow-wrap), so a long one stays inside the summary
              (E242). */}
          <p className="break-words text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
            {skipped.map((entry, i) => (
              <Fragment key={`${i}-${entry}`}>
                {i > 0 && ', '}
                <AddressText address={entry} />
              </Fragment>
            ))}
            : already invited or invalid.
          </p>
        </div>
      )}
    </div>
  )
}

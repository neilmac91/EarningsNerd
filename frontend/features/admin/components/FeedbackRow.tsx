'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useState } from 'react'
import { format } from 'date-fns'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CircleNotchIcon } from '@/lib/icons'
import { fieldUnavailableClass, inputClasses } from '@/components/ui/Input'
import { MissingValue } from '@/components/ui/MissingValue'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import {
  updateFeedbackStatus,
  type FeedbackRecord,
  type FeedbackStatus,
} from '@/features/admin/api/admin-api'
import FeedbackStatusBadge from '@/features/admin/components/FeedbackStatusBadge'
import FeedbackTypeBadge from '@/features/admin/components/FeedbackTypeBadge'
import FeedbackDetails from '@/features/admin/components/FeedbackDetails'

const STATUS_OPTIONS: FeedbackStatus[] = ['new', 'triaged', 'resolved']

/** A stored instant as its day, or null when there is none or it does not parse: the cell then shows MissingValue
 *  ("unavailable"), never a bare token. */
function fmtDate(value: string | null): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return format(d, 'MMM d, yyyy')
}

interface FeedbackRowProps {
  feedback: FeedbackRecord
}

export default function FeedbackRow({ feedback }: FeedbackRowProps) {
  const queryClient = useQueryClient()
  const [detailsOpen, setDetailsOpen] = useState(false)

  const statusMutation = useMutation({
    mutationFn: (status: FeedbackStatus) => updateFeedbackStatus(feedback.id, status),
    onSuccess: (updated) => {
      toast.success(`Marked as ${updated.status}`)
      // Returned, so the update stays pending until the list refetch moves the controlled value (or
      // drops the row from a filtered list): the select keeps focus, and released any sooner a
      // second keyboard change would send another, possibly conflicting, update.
      return queryClient.invalidateQueries({ queryKey: queryKeys.adminFeedback.all() })
    },
    onError: (err: unknown) => {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not update that feedback.')
    },
  })

  return (
    <tr className="ph-no-capture hover:bg-background-light dark:hover:bg-white/5">
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm">
        <FeedbackTypeBadge type={feedback.type} />
      </td>
      {/* The message column takes the width the others leave (w-full), so the status select keeps its own at 1440,
          where it was cut off at the card's edge. The button's intrinsic width is contained, or a one-line
          (truncate) message would size the column by its whole text; min-w-64 is the floor it keeps when the
          table scrolls on a phone. */}
      <td className="w-full px-4 py-3 align-top text-sm text-text-primary-light dark:text-text-primary-dark">
        <button
          type="button"
          onClick={() => setDetailsOpen(true)}
          aria-label={`View details for feedback ${feedback.id}`}
          aria-haspopup="dialog"
          aria-expanded={detailsOpen}
          className="block min-h-11 w-full min-w-64 rounded text-left [contain:inline-size] transition-colors hover:text-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
        >
          <span className="block truncate">{feedback.message}</span>
          <span className="mt-1 block text-xs underline underline-offset-2">View details</span>
        </button>
        <FeedbackDetails feedback={feedback} open={detailsOpen} onClose={() => setDetailsOpen(false)} />
      </td>
      <td className="px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {feedback.page_url ? (
          <span className="block max-w-[14rem] truncate">
            {feedback.page_url}
          </span>
        ) : (
          // Feedback sent from no page carries none: the words say so rather than "unavailable".
          <MissingValue label="no page" className="text-text-tertiary-light dark:text-text-secondary-dark" />
        )}
      </td>
      {/* The reporter's address is never cut: it keeps its own width up to 14rem and wraps inside that beyond it, so
          a 50-character address no longer takes the table past its box at 1440 (it was nowrap: 1264px in 1214px).
          The width lives on a block inside the cell, w-max under the cap: the message column's w-full holds every
          other column at its narrowest, so wrapping the cell itself broke even alice@example.com over four lines. */}
      <td className="px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        <span className="block w-max max-w-[14rem] [overflow-wrap:anywhere]">
          {feedback.user_email ?? (
            <span className="text-text-tertiary-light dark:text-text-secondary-dark">Anonymous</span>
          )}
        </span>
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(feedback.created_at) ?? <MissingValue />}
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm">
        <div className="flex items-center gap-2">
          <FeedbackStatusBadge status={feedback.status} />
          <label htmlFor={`feedback-status-${feedback.id}`} className="sr-only">
            Set status for feedback {feedback.id}
          </label>
          <div className="relative">
            {/* aria-disabled + an early return while its own update is in flight, not native
                `disabled`: Chromium blurs a focused select that turns disabled, dropping the
                keyboard user to <body>. The early return leaves the controlled value unchanged.
                fieldUnavailableClass gives the unavailable look by fading the text ink, not the element.
                autoWidth, not the default w-full: a percentage width zeroes the select's min-content
                width, so a table wider than its scroller squeezed the select until its label clipped. */}
            <select
              id={`feedback-status-${feedback.id}`}
              value={feedback.status}
              aria-disabled={statusMutation.isPending || undefined}
              aria-busy={statusMutation.isPending || undefined}
              onChange={(e) => {
                if (statusMutation.isPending) return
                statusMutation.mutate(e.target.value as FeedbackStatus)
              }}
              className={`${inputClasses({ select: true, density: 'compact', autoWidth: true })} ${fieldUnavailableClass}`}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            {statusMutation.isPending && (
              <CircleNotchIcon
                className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin motion-reduce:animate-none text-text-secondary-light dark:text-text-secondary-dark"
                aria-hidden="true"
              />
            )}
          </div>
        </div>
      </td>
    </tr>
  )
}

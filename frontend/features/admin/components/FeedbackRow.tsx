'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useState } from 'react'
import { format } from 'date-fns'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CircleNotchIcon } from '@/lib/icons'
import { inputClasses } from '@/components/ui/Input'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import {
  updateFeedbackStatus,
  type FeedbackRecord,
  type FeedbackStatus,
} from '@/features/admin/api/admin-api'
import FeedbackStatusBadge from '@/features/admin/components/FeedbackStatusBadge'
import FeedbackTypeBadge from '@/features/admin/components/FeedbackTypeBadge'

const STATUS_OPTIONS: FeedbackStatus[] = ['new', 'triaged', 'resolved']

function fmtDate(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return format(d, 'MMM d, yyyy')
}

interface FeedbackRowProps {
  feedback: FeedbackRecord
}

export default function FeedbackRow({ feedback }: FeedbackRowProps) {
  const queryClient = useQueryClient()
  // Long messages collapse to one line by default; admins can expand to read the full text.
  const [expanded, setExpanded] = useState(false)

  const statusMutation = useMutation({
    mutationFn: (status: FeedbackStatus) => updateFeedbackStatus(feedback.id, status),
    onSuccess: (updated) => {
      toast.success(`Marked as ${updated.status}`)
      queryClient.invalidateQueries({ queryKey: queryKeys.adminFeedback.all() })
    },
    onError: (err: unknown) => {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not update that feedback.')
    },
  })

  return (
    <tr className="hover:bg-background-light dark:hover:bg-white/5">
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm">
        <FeedbackTypeBadge type={feedback.type} />
      </td>
      <td className="max-w-md px-4 py-3 align-top text-sm text-text-primary-light dark:text-text-primary-dark">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          title={feedback.message}
          aria-expanded={expanded}
          className={`block w-full text-left transition-colors hover:text-brand-strong dark:hover:text-brand-strong-dark ${
            expanded ? 'whitespace-pre-wrap break-words' : 'truncate'
          }`}
        >
          {feedback.message}
        </button>
      </td>
      <td className="px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {feedback.page_url ? (
          <span className="block max-w-[14rem] truncate" title={feedback.page_url}>
            {feedback.page_url}
          </span>
        ) : (
          <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {feedback.user_email ?? (
          <span className="text-text-tertiary-light dark:text-text-secondary-dark">Anonymous</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(feedback.created_at)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-top text-sm">
        <div className="flex items-center gap-2">
          <FeedbackStatusBadge status={feedback.status} />
          <label htmlFor={`feedback-status-${feedback.id}`} className="sr-only">
            Set status for feedback {feedback.id}
          </label>
          <div className="relative">
            <select
              id={`feedback-status-${feedback.id}`}
              value={feedback.status}
              disabled={statusMutation.isPending}
              onChange={(e) => statusMutation.mutate(e.target.value as FeedbackStatus)}
              className={`${inputClasses()} w-auto py-1.5 pr-8 text-xs disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            {statusMutation.isPending && (
              <CircleNotchIcon
                className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-text-secondary-light dark:text-text-secondary-dark"
                aria-hidden="true"
              />
            )}
          </div>
        </div>
      </td>
    </tr>
  )
}

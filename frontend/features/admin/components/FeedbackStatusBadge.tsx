'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import type { FeedbackStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for a feedback item, mirroring InviteStatusBadge: new=info (an unread envelope; the
 * sparkle is reserved for the AI summary chip), triaged=warning, resolved=success, each with an icon
 * and a label (never color alone), on the status chip recipe (DESIGN_SYSTEM.md §4).
 */
const STATUS_CONFIG: Record<
  FeedbackStatus,
  { label: string; className: string; Icon: typeof CheckCircleIcon }
> = {
  new: {
    label: 'New',
    Icon: EnvelopeSimpleIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-info-text dark:text-info-dark',
  },
  triaged: {
    label: 'Triaged',
    Icon: ClockIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-warning-light dark:text-warning-dark',
  },
  resolved: {
    label: 'Resolved',
    Icon: CheckCircleIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-success-light dark:text-success-dark',
  },
}

export default function FeedbackStatusBadge({ status }: { status: FeedbackStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.new
  const { label, Icon, className } = config
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

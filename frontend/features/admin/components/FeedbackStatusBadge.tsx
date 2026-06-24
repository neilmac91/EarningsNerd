'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, SparkleIcon } from '@/lib/icons'
import type { FeedbackStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for a feedback item. Uses semantic tokens (never color alone — each carries an
 * icon + label) per the design system, mirroring InviteStatusBadge: new=info, triaged=warning,
 * resolved=success.
 */
const STATUS_CONFIG: Record<
  FeedbackStatus,
  { label: string; className: string; Icon: typeof CheckCircleIcon }
> = {
  new: {
    label: 'New',
    Icon: SparkleIcon,
    className:
      'border-info-light/40 bg-info-light/10 text-info-light dark:border-info-dark/40 dark:bg-info-dark/15 dark:text-info-dark',
  },
  triaged: {
    label: 'Triaged',
    Icon: ClockIcon,
    className:
      'border-warning-light/40 bg-warning-light/10 text-warning-light dark:border-warning-dark/40 dark:bg-warning-dark/15 dark:text-warning-dark',
  },
  resolved: {
    label: 'Resolved',
    Icon: CheckCircleIcon,
    className:
      'border-success-light/40 bg-success-light/10 text-success-light dark:border-success-dark/40 dark:bg-success-dark/15 dark:text-success-dark',
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

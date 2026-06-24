'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, ProhibitIcon, WarningCircleIcon } from '@/lib/icons'
import type { InviteStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for an invite. Uses semantic tokens (never color alone — each carries an icon +
 * label) per the design system: pending=info, used=success, expired=warning, revoked=neutral.
 */
const STATUS_CONFIG: Record<
  InviteStatus,
  { label: string; className: string; Icon: typeof CheckCircleIcon }
> = {
  pending: {
    label: 'Pending',
    Icon: ClockIcon,
    className:
      'border-info-light/40 bg-info-light/10 text-info-light dark:border-info-dark/40 dark:bg-info-dark/15 dark:text-info-dark',
  },
  used: {
    label: 'Used',
    Icon: CheckCircleIcon,
    className:
      'border-success-light/40 bg-success-light/10 text-success-light dark:border-success-dark/40 dark:bg-success-dark/15 dark:text-success-dark',
  },
  expired: {
    label: 'Expired',
    Icon: WarningCircleIcon,
    className:
      'border-warning-light/40 bg-warning-light/10 text-warning-light dark:border-warning-dark/40 dark:bg-warning-dark/15 dark:text-warning-dark',
  },
  revoked: {
    label: 'Revoked',
    Icon: ProhibitIcon,
    className:
      'border-border-light bg-black/[0.04] text-text-tertiary-light dark:border-white/10 dark:bg-white/5 dark:text-text-secondary-dark',
  },
}

export default function InviteStatusBadge({ status }: { status: InviteStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
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

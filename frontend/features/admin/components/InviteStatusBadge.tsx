'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, ProhibitIcon, WarningCircleIcon } from '@/lib/icons'
import type { InviteStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for an invite: pending=info, used=success, expired=warning, revoked=neutral, each with
 * an icon and a label (never color alone). The status chip recipe (DESIGN_SYSTEM.md §4): the status
 * ink on the quiet ground, white with a hairline in light and the bare hairline in dark, so the label
 * clears 4.5:1 on the row at rest and under its hover tint (tests/unit/statusChipContrast.spec.ts).
 */
const STATUS_CONFIG: Record<
  InviteStatus,
  { label: string; className: string; Icon: typeof CheckCircleIcon }
> = {
  pending: {
    label: 'Pending',
    Icon: ClockIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-info-text dark:text-info-dark',
  },
  used: {
    label: 'Used',
    Icon: CheckCircleIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-success-light dark:text-success-dark',
  },
  expired: {
    label: 'Expired',
    Icon: WarningCircleIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-warning-light dark:text-warning-dark',
  },
  revoked: {
    label: 'Revoked',
    Icon: ProhibitIcon,
    className:
      'border-border-light bg-white dark:border-border-dark dark:bg-transparent text-text-tertiary-light dark:text-text-secondary-dark',
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

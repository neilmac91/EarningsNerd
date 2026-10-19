'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, ProhibitIcon, WarningCircleIcon } from '@/lib/icons'
import type { InviteStatus } from '@/features/admin/api/admin-api'
import { STATUS_CHIP, STATUS_CHIP_INK, type StatusChipTone } from '@/features/admin/lib/statusChip'

/**
 * Status pill for an invite: pending=info, used=success, expired=warning, revoked=neutral, each with
 * an icon and a label (never color alone), on the status chip recipe (features/admin/lib/statusChip.ts).
 */
const STATUS_CONFIG: Record<
  InviteStatus,
  { label: string; tone: StatusChipTone; Icon: typeof CheckCircleIcon }
> = {
  pending: { label: 'Pending', tone: 'info', Icon: ClockIcon },
  used: { label: 'Used', tone: 'success', Icon: CheckCircleIcon },
  expired: { label: 'Expired', tone: 'warning', Icon: WarningCircleIcon },
  revoked: { label: 'Revoked', tone: 'neutral', Icon: ProhibitIcon },
}

export default function InviteStatusBadge({ status }: { status: InviteStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  const { label, Icon, tone } = config
  return (
    <span className={clsx(STATUS_CHIP, STATUS_CHIP_INK[tone])}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

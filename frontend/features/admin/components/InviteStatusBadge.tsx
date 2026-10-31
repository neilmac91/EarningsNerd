'use client'

import { CheckCircleIcon, ClockIcon, ProhibitIcon, WarningCircleIcon } from '@/lib/icons'
import { Badge, type BadgeStatusVariant } from '@/components/ui'
import type { InviteStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for an invite: pending=info, used=success, expired=warning, revoked=neutral, each with
 * an icon and a label (never color alone), on Badge's status set (components/ui/Badge.tsx).
 */
const STATUS_CONFIG: Record<
  InviteStatus,
  { label: string; variant: BadgeStatusVariant; Icon: typeof CheckCircleIcon }
> = {
  pending: { label: 'Pending', variant: 'info-status', Icon: ClockIcon },
  used: { label: 'Used', variant: 'success', Icon: CheckCircleIcon },
  expired: { label: 'Expired', variant: 'warning-status', Icon: WarningCircleIcon },
  revoked: { label: 'Revoked', variant: 'neutral-status', Icon: ProhibitIcon },
}

export default function InviteStatusBadge({ status }: { status: InviteStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  const { label, Icon, variant } = config
  return (
    <Badge variant={variant} icon={<Icon className="h-3.5 w-3.5" />}>
      {label}
    </Badge>
  )
}

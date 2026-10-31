'use client'

import { CheckCircleIcon, ClockIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import { Badge, type BadgeStatusVariant } from '@/components/ui'
import type { FeedbackStatus } from '@/features/admin/api/admin-api'

/**
 * Status pill for a feedback item, mirroring InviteStatusBadge: new=info (an unread envelope; the
 * sparkle is reserved for the summary's AI mark, DESIGN.md, reserved glyphs), triaged=warning,
 * resolved=success, each with an icon and a label (never color alone), on Badge's status set
 * (components/ui/Badge.tsx).
 */
const STATUS_CONFIG: Record<
  FeedbackStatus,
  { label: string; variant: BadgeStatusVariant; Icon: typeof CheckCircleIcon }
> = {
  new: { label: 'New', variant: 'info-status', Icon: EnvelopeSimpleIcon },
  triaged: { label: 'Triaged', variant: 'warning-status', Icon: ClockIcon },
  resolved: { label: 'Resolved', variant: 'success', Icon: CheckCircleIcon },
}

export default function FeedbackStatusBadge({ status }: { status: FeedbackStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.new
  const { label, Icon, variant } = config
  return (
    <Badge variant={variant} icon={<Icon className="h-3.5 w-3.5" />}>
      {label}
    </Badge>
  )
}

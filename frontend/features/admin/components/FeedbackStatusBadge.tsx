'use client'

import { clsx } from 'clsx'
import { CheckCircleIcon, ClockIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import type { FeedbackStatus } from '@/features/admin/api/admin-api'
import { STATUS_CHIP, STATUS_CHIP_INK, type StatusChipTone } from '@/features/admin/lib/statusChip'

/**
 * Status pill for a feedback item, mirroring InviteStatusBadge: new=info (an unread envelope; the
 * sparkle is reserved for the summary's AI mark, DESIGN.md, reserved glyphs), triaged=warning,
 * resolved=success, each with an icon and a label (never color alone), on the status chip recipe
 * (features/admin/lib/statusChip.ts).
 */
const STATUS_CONFIG: Record<
  FeedbackStatus,
  { label: string; tone: StatusChipTone; Icon: typeof CheckCircleIcon }
> = {
  new: { label: 'New', tone: 'info', Icon: EnvelopeSimpleIcon },
  triaged: { label: 'Triaged', tone: 'warning', Icon: ClockIcon },
  resolved: { label: 'Resolved', tone: 'success', Icon: CheckCircleIcon },
}

export default function FeedbackStatusBadge({ status }: { status: FeedbackStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.new
  const { label, Icon, tone } = config
  return (
    <span className={clsx(STATUS_CHIP, STATUS_CHIP_INK[tone])}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

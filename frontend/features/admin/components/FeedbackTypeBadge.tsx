'use client'

import { clsx } from 'clsx'
import { ChatTextIcon, LightningIcon, WarningCircleIcon } from '@/lib/icons'
import type { FeedbackType } from '@/features/admin/api/admin-api'

/**
 * Neutral, icon+label chip for the kind of feedback. Type is not a status, so it stays neutral
 * (theme-paired neutral surface) rather than borrowing semantic status colors: only the status
 * badge carries semantic meaning. Each variant pairs an icon with its label. Dark carries no fill,
 * as the status chip beside it does (Badge's status set, components/ui/Badge.tsx): a white/5 fill
 * under the row's own white/5 hover tint drops the label to 4.27:1 on a hovered row. The hairline
 * stays, and tests/unit/statusChipContrast.spec.ts measures the label on FeedbackRow's grounds.
 */
const TYPE_CONFIG: Record<
  FeedbackType,
  { label: string; Icon: typeof ChatTextIcon }
> = {
  bug: { label: 'Bug', Icon: WarningCircleIcon },
  feature: { label: 'Feature', Icon: LightningIcon },
  general: { label: 'General', Icon: ChatTextIcon },
}

export default function FeedbackTypeBadge({ type }: { type: FeedbackType }) {
  const config = TYPE_CONFIG[type] ?? TYPE_CONFIG.general
  const { label, Icon } = config
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        'border-border-light bg-black/[0.04] text-text-secondary-light',
        'dark:border-white/10 dark:bg-transparent dark:text-text-secondary-dark',
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

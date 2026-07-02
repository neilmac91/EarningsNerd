import React from 'react'
import { QuestionIcon } from '@/lib/icons'
import { GuidanceCard } from './GuidanceCard'

interface EmptyStateProps {
  label: string
  message?: string
}

/**
 * TRANSITIONAL SHIM (design-system v2 adoption): delegates to GuidanceCard so every
 * empty state renders the v2 surface, while call sites keep the label-composition
 * API they were built against. Inline GuidanceCard at the call sites and delete
 * this file in the marketing/consolidation adoption PR.
 */
export function EmptyState({ label, message }: EmptyStateProps) {
  return (
    <GuidanceCard
      variant="empty"
      icon={<QuestionIcon className="h-5 w-5" />}
      title={`No ${label} Found`}
      description={
        message ||
        "The AI couldn't extract this specific section from the filing. This usually means the company didn't report it in standard format."
      }
    />
  )
}

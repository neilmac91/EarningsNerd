import { QuestionIcon } from '@/lib/icons'
import { GuidanceCard } from '@/components/ui'

/**
 * Empty state for an AI summary section the model couldn't extract — the
 * filings feature's composition of the v2 GuidanceCard (replaces the
 * transitional ui/EmptyState shim).
 */
export function SectionEmpty({ label }: { label: string }) {
  return (
    <GuidanceCard
      variant="empty"
      icon={<QuestionIcon className="h-5 w-5" />}
      title={`No ${label} Found`}
      description="The AI couldn't extract this specific section from the filing. This usually means the company didn't report it in standard format."
    />
  )
}

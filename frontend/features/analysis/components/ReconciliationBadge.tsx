import { Badge } from '@/components/ui'

/** Reconciliation is independent of whether a value was computed (for example, Q4). */
export default function ReconciliationBadge({ reconciled, label = 'Unverified' }: {
  reconciled?: boolean | null
  label?: string
}) {
  if (reconciled !== false) return null
  return (
    <Badge
      variant="warning"
      title="These figures have not passed automated reconciliation. Verify them against the original filing before relying on them."
    >
      {label}
    </Badge>
  )
}

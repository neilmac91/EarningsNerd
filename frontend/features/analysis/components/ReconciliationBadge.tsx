import { Badge } from '@/components/ui'
import { needsSourceCheck, qualityReasons, type FactProvenance } from '@/features/analysis/lib/provenance'

/** Reconciliation is independent of whether a value was computed (for example, Q4). */
export default function ReconciliationBadge({ reconciled, provenance, label = 'Source check needed' }: {
  reconciled?: boolean | null
  provenance?: FactProvenance | null
  label?: string
}) {
  if (!needsSourceCheck({ reconciled, provenance })) return null
  return (
    <Badge
      variant="warning"
      title={qualityReasons({ reconciled, provenance }).join(' ')}
    >
      {label}
    </Badge>
  )
}

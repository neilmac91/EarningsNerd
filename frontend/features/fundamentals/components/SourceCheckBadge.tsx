import { Badge } from '@/components/ui'
import { needsSourceCheck, qualityReasons, type FactProvenance } from '@/features/analysis/lib/provenance'

/** Reconciliation is independent of whether a value was computed (for example, Q4). The badge sits beside the Financial
 *  trends heading in a row that wraps; below a 24rem viewport (384px, 768px under a 200% text setting) its label may
 *  wrap too, as the hero example's badge does (E156): on a line of its own the one-line badge is wider than a phone's
 *  card under 200% text. The media variant comes after Badge's whitespace-nowrap in the stylesheet, so the label breaks
 *  only where the badge does not fit, and a badge that wraps takes the 16px step (DESIGN.md's radius scale). */
export default function SourceCheckBadge({ reconciled, provenance, label = 'Source check needed' }: {
  reconciled?: boolean | null
  provenance?: FactProvenance | null
  label?: string
}) {
  if (!needsSourceCheck({ reconciled, provenance })) return null
  return (
    <Badge
      variant="warning"
      title={qualityReasons({ reconciled, provenance }).join(' ')}
      className="[@media(max-width:24rem)]:whitespace-normal [@media(max-width:24rem)]:rounded-xl"
    >
      {label}
    </Badge>
  )
}

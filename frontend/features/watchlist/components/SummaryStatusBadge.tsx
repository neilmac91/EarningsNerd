import { Badge, type BadgeVariant } from '@/components/ui'

/**
 * The shared summary-status → badge for a watched company's latest filing. One source of truth so
 * the Watchlist insights page and the dashboard "Your companies" rows can never drift.
 *
 * The tonal variants (beat/miss/new) are used as plain colour recipes here — `icon={null}` strips
 * their automatic glyphs (▲ / ▼ / pulse).
 */
export default function SummaryStatusBadge({
  status,
  needsRegeneration,
}: {
  status: string
  needsRegeneration: boolean
}) {
  const [base, detail] = status.split(':')
  let label: string
  let variant: BadgeVariant
  switch (base) {
    case 'ready':
      label = 'Ready'
      variant = 'beat'
      break
    case 'generating':
      label = detail ? `Generating (${detail})` : 'Generating'
      variant = 'brand'
      break
    case 'placeholder':
      label = 'Fallback'
      variant = 'new'
      break
    case 'error':
      label = 'Error'
      variant = 'miss'
      break
    default:
      label = needsRegeneration ? 'Needs Attention' : 'Pending'
      variant = needsRegeneration ? 'miss' : 'neutral'
  }
  return (
    <Badge variant={variant} icon={null}>
      {label}
    </Badge>
  )
}

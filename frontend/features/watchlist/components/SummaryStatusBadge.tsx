import { Badge, type BadgeVariant } from '@/components/ui'

/**
 * The summary status of a watched company's latest filing, read from the server's `summary_status`
 * (backend/app/routers/watchlist.py and dashboard_feed_service._summary_status): `ready`, `placeholder`,
 * `generating:<stage>`, `error` or `missing`. One source of truth for the badge and the watchlist card's
 * next-step sentence, so the Watchlist insights page and the dashboard "Your companies" rows can never
 * drift. The prefix decides both; `needs_regeneration` only breaks the tie for a prefix this list does
 * not know (it is true for missing, placeholder and error alike, and false while a summary is written).
 * Gate: tests/unit/summaryStatusCopy.spec.tsx.
 *
 * Ready and Error still borrow the beat/miss chips with their glyphs stripped (`icon={null}`); they move
 * to Badge's success and error status variants once those land (brand-chrome-primitives, D-032).
 */
export type SummaryStatusKind = 'ready' | 'generating' | 'missing' | 'placeholder' | 'error'

const KINDS: ReadonlySet<string> = new Set<SummaryStatusKind>(['ready', 'generating', 'missing', 'placeholder', 'error'])

/** The status prefix (`generating:summarizing` reads `generating`), or null for one this list does not know. */
export function summaryStatusKind(status: string): SummaryStatusKind | null {
  const base = status.split(':')[0]
  return KINDS.has(base) ? (base as SummaryStatusKind) : null
}

/** The badge's label and variant for a status. */
export function summaryStatusBadge(status: string, needsRegeneration: boolean): { label: string; variant: BadgeVariant } {
  switch (summaryStatusKind(status)) {
    case 'ready':
      return { label: 'Ready', variant: 'beat' }
    case 'generating':
      // One word for every stage: the stage after the colon is the pipeline's key (`summarizing`,
      // `fetching`, even a stale `completed`), and the filing page's step log speaks in long phrases a
      // chip cannot carry, so the chip says only that a summary is being written.
      return { label: 'Generating', variant: 'brand' }
    case 'missing':
      return { label: 'No summary yet', variant: 'neutral' }
    case 'placeholder':
      return { label: 'Unavailable', variant: 'warning' }
    case 'error':
      return { label: 'Error', variant: 'miss' }
    default:
      return needsRegeneration
        ? { label: 'Needs regenerating', variant: 'warning' }
        : { label: 'Pending', variant: 'neutral' }
  }
}

/** What the reader can do next about the summary, one sentence per status. */
export function summaryNextStep(status: string, needsRegeneration: boolean): string {
  switch (summaryStatusKind(status)) {
    case 'ready':
      return 'Summary is current.'
    case 'generating':
      return 'A summary is being written.'
    case 'missing':
      return 'No summary yet. Open the filing to generate one.'
    case 'placeholder':
      return "This summary isn't available right now. Open the filing and generate it again."
    case 'error':
      return 'The last attempt failed. Open the filing and generate it again.'
    default:
      return needsRegeneration ? 'Open the filing and generate its summary again.' : 'Open the filing to see its summary.'
  }
}

export default function SummaryStatusBadge({
  status,
  needsRegeneration,
}: {
  status: string
  needsRegeneration: boolean
}) {
  const { label, variant } = summaryStatusBadge(status, needsRegeneration)
  return (
    <Badge variant={variant} icon={null}>
      {label}
    </Badge>
  )
}

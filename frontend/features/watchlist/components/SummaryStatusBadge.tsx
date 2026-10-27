import { Badge, type BadgeStatusVariant } from '@/components/ui'

/**
 * The summary status of a watched company's latest filing, read from the server's `summary_status`
 * (the watchlist insights, backend/app/routers/watchlist.py): `ready`, `placeholder`,
 * `generating:<stage>`, `error` or `missing`. One source of truth for the badge and the watchlist card's
 * next-step sentence, so the Watchlist insights page and the dashboard "Your companies" rows can never
 * drift. The prefix decides both; `needs_regeneration` only breaks the tie for a prefix this list does
 * not know (it is true for missing, placeholder and error alike, and false while a summary is written).
 * Gate: tests/unit/summaryStatusCopy.spec.tsx.
 *
 * The badge is a status, so it takes Badge's status set (D-032; BadgeStatusVariant, components/ui/Badge.tsx),
 * the status ink on the one quiet ground: Ready on success, Generating on info-status, No summary yet and
 * Pending on neutral-status, Unavailable and Needs regenerating on warning-status, Error on error. Never a
 * tint or the quiet chip (brand, info, warning, neutral), and never beat or miss: those are the
 * earnings-surprise direction (tests/unit/badgeVariants.spec.tsx). tests/unit/statusChipContrast.spec.ts
 * holds the badge to the set and measures every chip summaryStatusBadge() returns on both rows, at rest and
 * hovered, in both themes.
 */
export type SummaryStatusKind = 'ready' | 'generating' | 'missing' | 'placeholder' | 'error'

const KINDS: ReadonlySet<string> = new Set<SummaryStatusKind>(['ready', 'generating', 'missing', 'placeholder', 'error'])

/** The status prefix (`generating:summarizing` reads `generating`), or null for one this list does not know. */
export function summaryStatusKind(status: string): SummaryStatusKind | null {
  const base = status.split(':')[0]
  return KINDS.has(base) ? (base as SummaryStatusKind) : null
}

/** The badge's label and variant for a status: always a member of Badge's status set. */
export function summaryStatusBadge(status: string, needsRegeneration: boolean): { label: string; variant: BadgeStatusVariant } {
  switch (summaryStatusKind(status)) {
    case 'ready':
      return { label: 'Ready', variant: 'success' }
    case 'generating':
      // One word for every stage: the stage after the colon is the pipeline's key (`summarizing`,
      // `fetching`, even a stale `completed`), and the filing page's step log speaks in long phrases a
      // chip cannot carry, so the chip says only that a summary is being written.
      return { label: 'Generating', variant: 'info-status' }
    case 'missing':
      return { label: 'No summary yet', variant: 'neutral-status' }
    case 'placeholder':
      return { label: 'Unavailable', variant: 'warning-status' }
    case 'error':
      return { label: 'Error', variant: 'error' }
    default:
      return needsRegeneration
        ? { label: 'Needs regenerating', variant: 'warning-status' }
        : { label: 'Pending', variant: 'neutral-status' }
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
    <Badge variant={variant}>{label}</Badge>
  )
}

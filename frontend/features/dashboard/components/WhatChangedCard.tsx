'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import Link from 'next/link'
import { ArrowRightIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { FeedItem, WhatChangedItem, WordingChangesSummary } from '@/features/dashboard/api/dashboard-api'
import { plural } from '@/features/filings/lib/sectionChanges'
import { formatLocalDate } from '@/lib/format'
import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, Card } from '@/components/ui'
import { directionChip, type Direction } from '@/lib/financialTone'

// A filing counts as "New" for up to two weeks. Because the feed now always shows each company's
// latest filing regardless of age, this badge is what distinguishes "fresh this week" from "their
// last report, months ago." Parsed as a LOCAL calendar day (matching formatLocalDate) so it doesn't
// flip a day early for users west of UTC.
function isRecentFiling(value: string | null, withinDays = 14): boolean {
  if (!value) return false
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return false
  // Diff two UTC midnights of the local calendar days: Date.UTC keeps the delta an exact multiple
  // of a day, so a DST fall-back week can't push a 14-day-old filing to 14.04 and drop the badge a
  // day early.
  const filed = Date.UTC(year, month - 1, day)
  if (Number.isNaN(filed)) return false
  const now = new Date()
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  const diffDays = (today - filed) / 86_400_000
  return diffDays >= 0 && diffDays <= withinDays
}

// A metric chip is a figure's change, so it takes the direction chip of lib/financialTone: the 700-level
// gain and loss inks on their soft grounds (flat in the secondary ink), never sage (D-030, DESIGN.md
// Separate Signals). The colour follows the tone the server computed with the signed display string;
// the glyph follows its direction and is decorative, since the sign (or, with no figure, the sr-only
// word) says the direction. Gates: eslint's earningsnerd/direction-text-tokens reads `<Icon />` through
// GLYPH and bans sage on it; tests/unit/whatChangedChip.spec.tsx holds its colour to the tone.
const GLYPH = { up: TrendUpIcon, down: TrendDownIcon, flat: MinusIcon } as const
const TONE: Record<WhatChangedItem['tone'], Direction> = { gain: 'up', loss: 'down', flat: 'flat' }

function ctaLabel(status: string): string {
  if (status === 'ready') return 'Read summary'
  if (status.startsWith('generating')) return 'Generating…'
  if (status === 'placeholder') return 'Regenerate summary'
  return 'Generate summary'
}

/** The card's one line on the risk factors' wording (E27, PR B), in the Compare periods card's words,
 *  with the Pro reader's own progress through the change queue after it; nothing when the filing has
 *  no comparison yet or its own section only refers back to the annual report. */
export function wordingLine(wording: WordingChangesSummary | null | undefined): string | null {
  if (!wording || wording.reference_only) return null
  if (wording.prior_reference_only) return 'Risk factors restated in full.'
  if (!wording.has_changes) return 'No wording changes in the risk factors.'
  const line = `${plural(wording.items_total, 'paragraph')} of risk factors changed.`
  const review = wording.review
  if (!review) return line
  if (review.completed_at) return `${line} Reviewed.`
  if (review.labeled > 0) return `${line} ${review.labeled} of ${wording.items_total} marked.`
  return line
}

function MetricChip({ item }: { item: WhatChangedItem }) {
  const Icon = GLYPH[item.direction] ?? GLYPH.flat
  const tone = TONE[item.tone] ?? item.direction ?? 'flat'
  const shown = item.direction !== 'flat' && item.display
  // Under 200% text a chip's label and figure can need two lines ("Noninterest income +103.9%" on a bank's card at 320px):
  // the figure moves under its label, and a word still wider than the group breaks inside it, the house's last resort
  // ([overflow-wrap:anywhere], as on the legal pages: "Noninterest" in the two-column feed at 640 and 1024px), so the chip
  // shrinks to its row instead of passing it (E268, chief design on #1877). It takes the 16px radius of a chip that can
  // wrap (DESIGN.md's radius scale): a pill on one line, a rounded box once it wraps. The glyph stays beside the group,
  // centred, as the other wrapping chips keep theirs.
  return (
    <span
      data-what-changed-chip
      className={`inline-flex items-center gap-1 rounded-xl border px-2.5 py-1 text-xs font-medium ${directionChip[tone]}`}
    >
      <Icon aria-hidden="true" className="h-3.5 w-3.5 flex-shrink-0" />
      <span className="flex min-w-0 flex-wrap items-center gap-x-1 [overflow-wrap:anywhere]">
        <span>{item.label}</span>
        {shown ? (
          <span className="font-data font-semibold">{item.display}</span>
        ) : item.direction !== 'flat' ? (
          <span className="sr-only">{item.direction === 'up' ? ' up' : ' down'}</span>
        ) : null}
      </span>
    </span>
  )
}

/** The call to action's words with the arrow held to the last of them, so a label that wraps carries the arrow onto its
 *  last line instead of parting it to the card's far edge (chief design on #1897, E272). */
function CallToAction({ label }: { label: string }) {
  const last = label.lastIndexOf(' ') + 1
  return (
    <>
      {label.slice(0, last)}
      <span className="whitespace-nowrap">
        {label.slice(last)}
        <ArrowRightIcon aria-hidden="true" className="ml-1 inline-block h-4 w-4 align-text-bottom" />
      </span>
    </>
  )
}

export default function WhatChangedCard({ item }: { item: FeedItem }) {
  const { what_changed: wc, company } = item
  const wording = wordingLine(item.wording_changes)
  return (
    <Link
      href={`/filing/${item.filing_id}`}
      onClick={() => analytics.dashboardFeedClicked(item.filing_id, company.ticker, item.filing_type)}
      className="block rounded-xl focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
    >
      {/* The card is the header's query container. Side by side the header needs about 21rem: the date column's widest
          line (8.45rem for "10-Q · May 28, 2026"), the ticker (up to 3.3rem for "BRK.B"), the logo (1.75rem at the
          default size), three gaps (1.9rem) and at least 5.6rem of name. Below that, on a phone and under 200% text at
          every width, the date column moves under the company line, left-aligned, and the name wraps instead of
          truncating, so it keeps its words (E272, chief design on #1897); the ticker follows the name, under it when
          the two do not fit. Stacked, the logo keeps to the name's first line, as ActivityLine's dot does (the line
          at items-start, the logo nudged by half of the name's line less the logo; chief design on #1900). Below
          7.25rem the decorative logo gives way too, as the calendar's event row drops its own, since beside it a
          phone under 200% text breaks common words ("International", "Laboratories"). */}
      <Card interactive className="h-full p-cap-5 [container-type:inline-size]">
        <div data-what-changed-header className="flex items-start justify-between gap-3 [@container(width<21rem)]:flex-col [@container(width<21rem)]:gap-2">
          <div className="flex min-w-0 items-center gap-2.5 [@container(width<21rem)]:items-start">
            <CompanyLogo
              decorative
              ticker={company.ticker}
              name={formatCompanyName(company.name)}
              size={28}
              className="[@container(width<21rem)]:mt-[calc((1.5rem_-_28px)/2)] [@container(width<7.25rem)]:hidden"
            />
            <div className="flex min-w-0 items-center gap-2 [@container(width<21rem)]:flex-wrap [@container(width<21rem)]:gap-y-1">
              <span className="truncate font-semibold text-text-primary-light dark:text-text-primary-dark [@container(width<21rem)]:whitespace-normal [@container(width<21rem)]:[overflow-wrap:anywhere]">
                {formatCompanyName(company.name)}
              </span>
              <span className="rounded-full bg-panel-light px-2 py-0.5 font-data text-xs font-semibold text-text-secondary-light dark:bg-background-dark dark:text-text-secondary-dark">
                {company.ticker}
              </span>
            </div>
          </div>
          <div className="flex flex-shrink-0 flex-col items-end gap-0.5 text-right [@container(width<21rem)]:items-start [@container(width<21rem)]:text-left">
            {isRecentFiling(item.filing_date) && (
              <Badge variant="new" icon={null} className="mb-0.5">New</Badge>
            )}
            {/* "Latest report" (vs "Last filed" in Your companies): this feed shows the newest
                10-K/10-Q, which can be older than a company's most recent filing of any form. */}
            <span className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">Latest report</span>
            {/* The date keeps whole: where the line wraps under 200% text it breaks after the form, not inside the
                date (chief design on #1900). */}
            <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {item.filing_type} · <span className="whitespace-nowrap">{formatLocalDate(item.filing_date, 'MMM d, yyyy')}</span>
            </span>
          </div>
        </div>

        {wc ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {wc.items.map((m) => (
              <MetricChip key={m.metric} item={m} />
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            No comparison figures for this one yet. The summary has the full picture.
          </p>
        )}
        {wording && <p className="mt-2 text-xs tnum text-text-secondary-light dark:text-text-secondary-dark">{wording}</p>}

        <div className="mt-3 text-sm font-medium text-brand-strong dark:text-brand-strong-dark">
          <CallToAction label={ctaLabel(item.summary_status)} />
        </div>
      </Card>
    </Link>
  )
}

'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import Link from 'next/link'
import { ArrowRightIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { FeedItem, WhatChangedItem } from '@/features/dashboard/api/dashboard-api'
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
// word) says the direction. Gate: tests/unit/whatChangedChip.spec.tsx, since eslint's
// earningsnerd/direction-text-tokens cannot follow a glyph drawn through a variable (`<Icon />`).
const GLYPH = { up: TrendUpIcon, down: TrendDownIcon, flat: MinusIcon } as const
const TONE: Record<WhatChangedItem['tone'], Direction> = { gain: 'up', loss: 'down', flat: 'flat' }

function ctaLabel(status: string): string {
  if (status === 'ready') return 'Read summary'
  if (status.startsWith('generating')) return 'Generating…'
  if (status === 'placeholder') return 'Regenerate summary'
  return 'Generate summary'
}

function MetricChip({ item }: { item: WhatChangedItem }) {
  const Icon = GLYPH[item.direction] ?? GLYPH.flat
  const tone = TONE[item.tone] ?? item.direction ?? 'flat'
  const shown = item.direction !== 'flat' && item.display
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${directionChip[tone]}`}>
      <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      {item.label}
      {shown ? (
        <span className="font-data font-semibold">{item.display}</span>
      ) : item.direction !== 'flat' ? (
        <span className="sr-only">{item.direction === 'up' ? ' up' : ' down'}</span>
      ) : null}
    </span>
  )
}

export default function WhatChangedCard({ item }: { item: FeedItem }) {
  const { what_changed: wc, company } = item
  return (
    <Link
      href={`/filing/${item.filing_id}`}
      onClick={() => analytics.dashboardFeedClicked(item.filing_id, company.ticker, item.filing_type)}
      className="block rounded-xl focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
    >
      <Card interactive className="h-full p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <CompanyLogo decorative ticker={company.ticker} name={formatCompanyName(company.name)} size={28} />
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-semibold text-text-primary-light dark:text-text-primary-dark">
                {formatCompanyName(company.name)}
              </span>
              <span className="rounded-full bg-panel-light px-2 py-0.5 font-data text-xs font-semibold text-text-secondary-light dark:bg-background-dark dark:text-text-secondary-dark">
                {company.ticker}
              </span>
            </div>
          </div>
          <div className="flex flex-shrink-0 flex-col items-end gap-0.5 text-right">
            {isRecentFiling(item.filing_date) && (
              <Badge variant="new" icon={null} className="mb-0.5">New</Badge>
            )}
            {/* "Latest report" (vs "Last filed" in Your companies): this feed shows the newest
                10-K/10-Q, which can be older than a company's most recent filing of any form. */}
            <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">Latest report</span>
            <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {item.filing_type} · {formatLocalDate(item.filing_date, 'MMM d, yyyy')}
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

        <div className="mt-3 flex items-center gap-1 text-sm font-medium text-brand-strong dark:text-brand-strong-dark">
          {ctaLabel(item.summary_status)}
          <ArrowRightIcon className="h-4 w-4" />
        </div>
      </Card>
    </Link>
  )
}

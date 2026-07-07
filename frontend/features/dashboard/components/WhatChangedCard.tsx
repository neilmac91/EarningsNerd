'use client'

import Link from 'next/link'
import { ArrowRightIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { FeedItem, WhatChangedItem } from '@/features/dashboard/api/dashboard-api'
import { formatLocalDate } from '@/lib/format'
import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, Card } from '@/components/ui'

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

// Calm directional chips: brand accent for up, muted neutral for down — never casino red/green.
// Deliberate exception to financialTone.directionChip (gain/loss tones): a feed of watched
// companies isn't a P&L readout, so it keeps the calm treatment. Icons still carry direction.
const DIRECTION = {
  up: { Icon: TrendUpIcon, cls: 'text-brand-strong dark:text-brand-strong-dark bg-brand-weak dark:bg-white/5' },
  down: { Icon: TrendDownIcon, cls: 'text-text-secondary-light dark:text-text-secondary-dark bg-brand-weak dark:bg-white/5' },
  flat: { Icon: MinusIcon, cls: 'text-text-tertiary-light dark:text-text-secondary-dark bg-brand-weak dark:bg-white/5' },
} as const

function ctaLabel(status: string): string {
  if (status === 'ready') return 'Read summary'
  if (status.startsWith('generating')) return 'Generating…'
  if (status === 'placeholder') return 'Regenerate summary'
  return 'Generate summary'
}

function MetricChip({ item }: { item: WhatChangedItem }) {
  const { Icon, cls } = DIRECTION[item.direction] ?? DIRECTION.flat
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {item.label}
      {item.direction !== 'flat' && item.pct !== null && (
        <span className="font-semibold">{item.pct.toFixed(1)}%</span>
      )}
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
            <CompanyLogo ticker={company.ticker} name={company.name} size={28} />
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-semibold text-text-primary-light dark:text-text-primary-dark">
                {company.name}
              </span>
              <span className="rounded-full bg-panel-light px-2 py-0.5 text-xs font-semibold text-text-secondary-light dark:bg-background-dark dark:text-text-secondary-dark">
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

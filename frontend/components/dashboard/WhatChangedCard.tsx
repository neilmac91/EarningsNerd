'use client'

import Link from 'next/link'
import { ArrowRight, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { FeedItem, WhatChangedItem } from '@/features/dashboard/api/dashboard-api'
import { formatLocalDate } from '@/lib/format'
import analytics from '@/lib/analytics'

// Calm directional chips: mint for up, muted slate for down — never casino red/green.
const DIRECTION = {
  up: { Icon: TrendingUp, cls: 'text-mint-700 dark:text-mint-300 bg-mint-500/10' },
  down: { Icon: TrendingDown, cls: 'text-slate-600 dark:text-slate-300 bg-slate-500/10' },
  flat: { Icon: Minus, cls: 'text-slate-500 bg-slate-500/10' },
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
      className="block rounded-xl border border-border-light bg-background-light p-5 transition hover:border-mint-400 hover:shadow-sm dark:border-border-dark dark:bg-panel-dark"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold text-text-primary-light dark:text-text-primary-dark">
              {company.name}
            </span>
            <span className="rounded-full bg-panel-light px-2 py-0.5 text-xs font-semibold text-text-secondary-light dark:bg-background-dark dark:text-text-secondary-dark">
              {company.ticker}
            </span>
          </div>
        </div>
        <div className="flex-shrink-0 text-right text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {item.filing_type} · {formatLocalDate(item.filing_date, 'MMM d, yyyy')}
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
          New {item.filing_type} filed — open for the full breakdown.
        </p>
      )}

      <div className="mt-3 flex items-center gap-1 text-sm font-medium text-mint-600 dark:text-mint-400">
        {ctaLabel(item.summary_status)}
        <ArrowRight className="h-4 w-4" />
      </div>
    </Link>
  )
}

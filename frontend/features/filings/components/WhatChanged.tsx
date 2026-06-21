import React from 'react'
import Link from 'next/link'
import { TrendingUp, TrendingDown, Minus, GitCompare } from 'lucide-react'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import { directionText } from '@/lib/financialTone'

const DIR_ICON = { up: TrendingUp, down: TrendingDown, flat: Minus } as const
const DIR_TONE = directionText

function formatDelta(pct: number | null, direction: 'up' | 'down' | 'flat'): string {
  if (pct === null || direction === 'flat') return 'flat'
  return `${direction === 'up' ? '+' : '−'}${pct.toFixed(1)}%`
}

/**
 * A5 "What Changed": a calm, deterministic period-over-period change report — metric deltas, new /
 * no-longer-cited risk factors, and management's note — shown at the top of a filing summary. Renders
 * nothing unless there is something material to report (has_changes).
 */
export function WhatChanged({ report }: { report: ChangeReport }) {
  if (!report.has_changes) return null
  const { metrics, risks, key_changes: keyChanges, comparison_basis: basis, prior_filing: prior } = report

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <GitCompare className="h-5 w-5 text-mint-600 dark:text-mint-400" aria-hidden />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-text-primary-dark">
            What changed
          </h2>
          {basis && (
            <span className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-text-tertiary-dark">
              {basis}
            </span>
          )}
        </div>
        {prior && (
          <Link
            href={`/filing/${prior.filing_id}`}
            className="shrink-0 text-xs font-medium text-mint-600 hover:underline dark:text-mint-400"
          >
            vs prior {prior.filing_type}
            {prior.period_end_date ? ` (${prior.period_end_date.slice(0, 10)})` : ''} ↗
          </Link>
        )}
      </div>

      {metrics && metrics.items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {metrics.items.map((item) => {
            const Icon = DIR_ICON[item.direction]
            return (
              <span
                key={item.metric}
                className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-sm dark:border-border-dark dark:bg-background-dark"
              >
                <span className="text-gray-600 dark:text-text-secondary-dark">{item.label}</span>
                <Icon className={`h-4 w-4 ${DIR_TONE[item.direction]}`} aria-hidden />
                <span className={`font-semibold tabular-nums ${DIR_TONE[item.direction]}`}>
                  {formatDelta(item.pct, item.direction)}
                </span>
              </span>
            )
          })}
        </div>
      )}

      {metrics?.data_quality === 'partial' && (
        <p className="mt-2 text-xs text-gray-400 dark:text-text-tertiary-dark">
          Some figures were withheld where the SEC XBRL data looked inconsistent.
        </p>
      )}

      {risks && (risks.new.length > 0 || risks.resolved.length > 0) && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {risks.new.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                New risk factors
              </h3>
              <ul className="space-y-1 text-sm text-gray-700 dark:text-text-secondary-dark">
                {risks.new.map((risk, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden className="text-slate-400">+</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {risks.resolved.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-mint-600 dark:text-mint-400">
                No longer cited
              </h3>
              <ul className="space-y-1 text-sm text-gray-700 dark:text-text-secondary-dark">
                {risks.resolved.map((risk, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden className="text-mint-500">−</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {risks && risks.carried_count > 0 && (
        <p className="mt-2 text-xs text-gray-400 dark:text-text-tertiary-dark">
          {risks.carried_count} risk factor{risks.carried_count === 1 ? '' : 's'} carried over.
        </p>
      )}

      {keyChanges && (
        <div className="mt-4 border-t border-gray-100 pt-3 dark:border-border-dark">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-text-tertiary-dark">
            Management&apos;s note on changes
          </h3>
          <p className="text-sm text-gray-700 dark:text-text-secondary-dark">{keyChanges}</p>
        </div>
      )}
    </section>
  )
}

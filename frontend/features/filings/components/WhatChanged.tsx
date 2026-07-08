import React from 'react'
import Link from 'next/link'
import { GitDiffIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import { directionText } from '@/lib/financialTone'

const DIR_ICON = { up: TrendUpIcon, down: TrendDownIcon, flat: MinusIcon } as const
const DIR_TONE = directionText

/**
 * A5 "What Changed": a calm, deterministic period-over-period change report — metric deltas, new /
 * no-longer-cited risk factors, and management's note — shown at the top of a filing summary. Renders
 * nothing unless there is something material to report (has_changes).
 */
export function WhatChanged({ report }: { report: ChangeReport }) {
  if (!report.has_changes) return null
  const { metrics, risks, comparison_basis: basis, prior_filing: prior } = report

  return (
    <section className="rounded-lg border border-border-light bg-panel-light p-6 shadow-e1 dark:shadow-none dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <GitDiffIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" aria-hidden />
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
            What changed
          </h2>
          {basis && (
            <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
              {basis}
            </span>
          )}
        </div>
        {prior && (
          <Link
            href={`/filing/${prior.filing_id}`}
            className="shrink-0 text-xs font-medium text-brand-strong hover:underline dark:text-brand-strong-dark"
          >
            vs prior {prior.filing_type}
            {prior.period_end_date ? ` (${prior.period_end_date.slice(0, 10)})` : ''} ↗
          </Link>
        )}
      </div>

      {/* Lead with the deterministic delta headline (computed from XBRL), not the summary's own
          outlook prose — which duplicated the Outlook section verbatim (plan §2.3). */}
      {metrics?.headline && (
        <p className="mb-4 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {metrics.headline}
        </p>
      )}

      {metrics && metrics.items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {metrics.items.map((item) => {
            const Icon = DIR_ICON[item.direction]
            return (
              <span
                key={item.metric}
                className="inline-flex items-center gap-1.5 rounded-full border border-border-light bg-background-light px-3 py-1 text-sm dark:border-border-dark dark:bg-background-dark"
              >
                <span className="text-text-secondary-light dark:text-text-secondary-dark">{item.label}</span>
                <Icon className={`h-4 w-4 ${DIR_TONE[item.direction]}`} aria-hidden />
                <span className={`font-semibold tabular-nums ${DIR_TONE[item.direction]}`}>
                  {item.display}
                </span>
              </span>
            )
          })}
        </div>
      )}

      {metrics?.data_quality === 'partial' && (
        <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          Some figures were withheld where the SEC XBRL data looked inconsistent.
        </p>
      )}

      {risks && (risks.new.length > 0 || risks.resolved.length > 0) && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {risks.new.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
                New risk factors
              </h3>
              <ul className="space-y-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {risks.new.map((risk, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden className="text-text-tertiary-light dark:text-text-secondary-dark">+</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {risks.resolved.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-strong dark:text-brand-strong-dark">
                No longer cited
              </h3>
              <ul className="space-y-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {risks.resolved.map((risk, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden className="text-brand-strong dark:text-brand-strong-dark">−</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {risks && risks.carried_count > 0 && (
        <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {risks.carried_count} risk factor{risks.carried_count === 1 ? '' : 's'} carried over.
        </p>
      )}
    </section>
  )
}

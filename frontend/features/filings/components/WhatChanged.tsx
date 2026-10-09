import React from 'react'
import Link from 'next/link'
import { CaretRightIcon } from '@/lib/icons'
import { Card, cx } from '@/components/ui'
import type { ChangeReport, WhatChangedMetricItem } from '@/features/summaries/api/summaries-api'
import { periodKind } from '@/features/filings/lib/filingPeriod'
import { directionText } from '@/lib/financialTone'
import { fmtCurrency, formatLocalDate } from '@/lib/format'

/**
 * A5 "What Changed": a calm, deterministic period-over-period change report — shown at the top of a
 * filing summary and, fed static samples, as the landing page's Change Report screen. Renders nothing
 * unless there is something material to report (has_changes).
 *
 * Rebuilt 2026-10 (docs/design/filings-index-review.md):
 *  - the Card recipe (`<Card as="section">`, 16 / e2), a sentence-case heading, and the comparison
 *    stated as a sentence — the basis is a qualifier, not an uppercase eyebrow;
 *  - metric deltas as a small table with DataTable manners — Metric · Prior · Current · Change —
 *    figures in the data face, right-aligned. Change is the server's `display` string VERBATIM,
 *    coloured by the server's `tone` (metric-aware: a fall in debt is a gain — DESIGN_SYSTEM §10),
 *    never re-derived from `direction`. The sign carries direction without colour, so no trend icon;
 *  - the risk diff with sentence-case subheads, counts, and neutral +/− glyphs (brand never signals a
 *    state). The backend withholds risk lines today (model-authored labels — change_report_service),
 *    so this block renders only when the payload carries them.
 */

const TONE_TEXT: Record<WhatChangedMetricItem['tone'], string> = {
  gain: directionText.up,
  loss: directionText.down,
  flat: directionText.flat,
}

const SUBHEADING = { h2: 'h3', h3: 'h4', h4: 'h5' } as const
const PER_SHARE = /eps|per_share/i
const PERIOD_NOUN = { annual: 'year', quarter: 'quarter', period: 'period' } as const

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'

/** Formatting only (no client math): "$394.3B"; per-share figures keep cents ("$6.11"). */
function figure(item: WhatChangedMetricItem, value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return PER_SHARE.test(item.metric) ? fmtCurrency(value, { digits: 2, compact: false }) : fmtCurrency(value)
}

export function WhatChanged({
  report,
  headingLevel: Heading = 'h2',
}: {
  report: ChangeReport
  /** Heading element for "What changed"; the landing page nests the report under an h3. */
  headingLevel?: 'h2' | 'h3' | 'h4'
}) {
  if (!report.has_changes) return null
  const { metrics, risks, comparison_basis: basis, prior_filing: prior } = report
  const Sub = SUBHEADING[Heading]
  const priorEnded = prior?.period_end_date ? formatLocalDate(prior.period_end_date, 'MMM d, yyyy') : ''

  return (
    <Card as="section" aria-label="What changed" className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <Heading className={cx('text-lg font-semibold', INK)}>What changed</Heading>
          {(basis || priorEnded) && (
            <p className={cx('mt-0.5 text-sm', MUTED)}>
              {basis && <span>{basis}</span>}
              {prior && priorEnded && (
                <>
                  {basis ? ', against' : 'Against'} the {prior.filing_type} for the {PERIOD_NOUN[periodKind(prior.filing_type)]} ended{' '}
                  <span className="tnum">{priorEnded}</span>
                </>
              )}
              .
            </p>
          )}
        </div>
        {prior && (
          <Link
            href={`/filing/${prior.filing_id}`}
            className={cx(
              '-mr-2 inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-semibold',
              'text-brand-strong transition-colors duration-fast hover:bg-brand-weak',
              'focus-visible:outline-none focus-visible:shadow-ring-brand',
              'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark',
            )}
          >
            Prior {prior.filing_type}
            <CaretRightIcon aria-hidden="true" className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>

      {/* Lead with the deterministic delta headline (computed from XBRL), not the summary's own
          outlook prose — which duplicated the Outlook section verbatim (plan §2.3). */}
      {metrics?.headline && <p className={cx('mt-4 max-w-prose text-base leading-relaxed', INK)}>{metrics.headline}</p>}

      {metrics && metrics.items.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark">
                <th scope="col" className="py-2 pr-4 text-left font-semibold">Metric</th>
                <th scope="col" className="py-2 pl-4 text-right font-semibold">Prior</th>
                <th scope="col" className="py-2 pl-4 text-right font-semibold">Current</th>
                <th scope="col" className="py-2 pl-4 text-right font-semibold">Change</th>
              </tr>
            </thead>
            <tbody>
              {metrics.items.map((item) => (
                <tr key={item.metric} className={cx('border-t', HAIRLINE)}>
                  <th scope="row" className={cx('py-2.5 pr-4 text-left font-medium', INK)}>{item.label}</th>
                  <td className={cx('py-2.5 pl-4 text-right font-data tabular-nums', MUTED)}>{figure(item, item.prior)}</td>
                  <td className={cx('py-2.5 pl-4 text-right font-data tabular-nums', INK)}>{figure(item, item.current)}</td>
                  <td className={cx('py-2.5 pl-4 text-right font-data font-semibold tabular-nums', TONE_TEXT[item.tone] ?? TONE_TEXT.flat)}>
                    {item.display}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {metrics?.data_quality === 'partial' && (
        <p className={cx('mt-2 text-xs', MUTED)}>Some figures were withheld where the SEC XBRL data looked inconsistent.</p>
      )}

      {risks && (risks.new.length > 0 || risks.resolved.length > 0) && (
        <div className={cx('mt-4 grid grid-cols-1 gap-x-8 gap-y-5 border-t pt-4 sm:grid-cols-2', HAIRLINE)}>
          {risks.new.length > 0 && <RiskList Heading={Sub} title="New risk factors" glyph="+" items={risks.new} />}
          {risks.resolved.length > 0 && <RiskList Heading={Sub} title="No longer cited" glyph="−" items={risks.resolved} />}
        </div>
      )}

      {risks && risks.carried_count > 0 && (
        <p className={cx('mt-3 text-xs', MUTED)}>
          {risks.carried_count} risk factor{risks.carried_count === 1 ? '' : 's'} carried over unchanged.
        </p>
      )}
    </Card>
  )
}

function RiskList({
  Heading,
  title,
  glyph,
  items,
}: {
  Heading: 'h3' | 'h4' | 'h5'
  title: string
  glyph: '+' | '−'
  items: string[]
}) {
  return (
    <div className="min-w-0">
      <Heading className={cx('flex items-baseline gap-2 text-sm font-semibold', INK)}>
        {title}{' '}
        <span className={cx('font-data text-xs font-medium tabular-nums', MUTED)}>{items.length}</span>
      </Heading>
      <ul className={cx('mt-2 space-y-1.5 text-sm', MUTED)}>
        {items.map((risk, i) => (
          <li key={i} className="grid grid-cols-[0.875rem_minmax(0,1fr)] gap-1.5">
            <span aria-hidden="true" className="font-data">{glyph}</span>
            <span>{risk}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

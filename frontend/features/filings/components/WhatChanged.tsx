import React, { type ReactNode } from 'react'
import Link from 'next/link'
import { CaretRightIcon } from '@/lib/icons'
import { Card, cx } from '@/components/ui'
import type { ChangeReport, WhatChangedMetricItem } from '@/features/summaries/api/summaries-api'
import { periodKind } from '@/features/filings/lib/filingPeriod'
import { directionText } from '@/lib/financialTone'
import { fmtCurrency, fmtScale, formatLocalDate } from '@/lib/format'

/**
 * A5 "What Changed": a calm, deterministic period-over-period change report — a numbered section of
 * the filing summary (`bare`, under the section's own heading) and, fed static samples, the landing
 * page's Change Report screen (its own Card). Renders nothing unless there is something material to
 * report (has_changes).
 *
 * Rebuilt 2026-10 (docs/design/filings-index-review.md, then the 2026-10 critique's P-07):
 *  - the Card recipe (`<Card as="section">`, 16 / e2) with a sentence-case heading, or, `bare`, no
 *    chrome of its own; the comparison stated as a sentence, never an uppercase eyebrow;
 *  - metric deltas as a small table with DataTable manners — Metric · Prior · Current · Change ·
 *    Read as — figures in the data face, right-aligned. Change is the server's `display` string
 *    VERBATIM, coloured by the server's `tone` (metric-aware: a fall in debt is a gain —
 *    DESIGN_SYSTEM §10), never re-derived from `direction`. A ▲/▼ text glyph states the arithmetic
 *    direction (aria-hidden: the signed string already carries it) and "Read as" states the tone in
 *    words, so direction and valence never share one signal. Below `sm` each metric is a stacked
 *    row — name and change, then prior → current and "Read as" — switched by CSS alone, like the
 *    metric cards (the inactive layout is display:none);
 *  - the risk diff with sentence-case subheads, counts, and neutral +/− glyphs (brand never signals a
 *    state). The backend withholds risk lines today (model-authored labels — change_report_service),
 *    so this block renders only when the payload carries them.
 */

const TONE_TEXT: Record<WhatChangedMetricItem['tone'], string> = {
  gain: directionText.up,
  loss: directionText.down,
  flat: directionText.flat,
}

/** The server's tone in words: what the change usually means for this metric, not its sign. */
const READ_AS: Record<WhatChangedMetricItem['tone'], string> = {
  gain: 'Favorable',
  loss: 'Unfavorable',
  flat: 'Neutral',
}

const GLYPH: Record<WhatChangedMetricItem['direction'], string> = { up: '▲', down: '▼', flat: '' }

const SUBHEADING = { h2: 'h3', h3: 'h4', h4: 'h5' } as const
const PER_SHARE = /eps|per_share/i
// An 8-K (`event`) has no change report; its noun is here only to keep the map total.
const PERIOD_NOUN = { annual: 'year', quarter: 'quarter', period: 'period', event: 'period' } as const

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'

/** Formatting only (no client math), in the filer's own reporting currency: "$394.3B", "¥37.2T";
 *  per-share figures keep cents ("$6.11"). The amounts are raw XBRL values in that currency (a
 *  foreign filer reports in its own), so an unknown currency shows them unlabelled ("394.3B"),
 *  never as dollars. */
function figure(item: WhatChangedMetricItem, value: number | null, currency: string | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const perShare = PER_SHARE.test(item.metric)
  if (currency) return perShare ? fmtCurrency(value, { currency, digits: 2, compact: false }) : fmtCurrency(value, { currency })
  return perShare ? fmtScale(value, { digits: 2 }) : fmtScale(value)
}

/** The served change: its direction glyph, then the display string, both in the tone's ink. */
function Change({ item }: { item: WhatChangedMetricItem }) {
  const glyph = GLYPH[item.direction]
  return (
    <span className={TONE_TEXT[item.tone] ?? TONE_TEXT.flat}>
      {glyph && (
        <span aria-hidden="true" className="mr-1">
          {glyph}
        </span>
      )}
      {item.display}
    </span>
  )
}

export function WhatChanged({
  report,
  headingLevel: Heading = 'h2',
  bare = false,
}: {
  report: ChangeReport
  /** Heading element for "What changed"; the landing page nests the report under an h3. When `bare`,
   * the level of the enclosing section's heading, so the risk subheads sit one below it. */
  headingLevel?: 'h2' | 'h3' | 'h4'
  /** Inside a summary section that supplies the heading: no Card and no heading of its own. */
  bare?: boolean
}) {
  if (!report.has_changes) return null
  const { metrics, risks, comparison_basis: basis, prior_filing: prior, reporting_currency: currency } = report
  const Sub = SUBHEADING[Heading]
  const priorEnded = prior?.period_end_date ? formatLocalDate(prior.period_end_date, 'MMM d, yyyy') : ''

  const basisLine = (basis || priorEnded) && (
    <p className={cx('text-sm', !bare && 'mt-0.5', MUTED)}>
      {basis && <span>{basis}</span>}
      {prior && priorEnded && (
        <>
          {basis ? ', against' : 'Against'} the {prior.filing_type} for the {PERIOD_NOUN[periodKind(prior.filing_type)]} ended{' '}
          <span className="tnum">{priorEnded}</span>
        </>
      )}
      .
    </p>
  )

  const priorLink = prior && (
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
  )

  const body: ReactNode = (
    <>
      {/* Lead with the deterministic delta headline (computed from XBRL), not the summary's own
          outlook prose — which duplicated the Outlook section verbatim (plan §2.3). */}
      {metrics?.headline && <p className={cx('mt-4 max-w-prose text-base leading-relaxed', INK)}>{metrics.headline}</p>}

      {metrics && metrics.items.length > 0 && (
        <div className="mt-3">
          <div data-change-layout="table" className="hidden overflow-x-auto sm:block">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark">
                  <th scope="col" className="py-2 pr-4 text-left font-semibold">Metric</th>
                  <th scope="col" className="py-2 pl-4 text-right font-semibold">Prior</th>
                  <th scope="col" className="py-2 pl-4 text-right font-semibold">Current</th>
                  <th scope="col" className="py-2 pl-4 text-right font-semibold">Change</th>
                  <th scope="col" className="py-2 pl-6 text-left font-semibold">Read as</th>
                </tr>
              </thead>
              <tbody>
                {metrics.items.map((item) => (
                  <tr key={item.metric} className={cx('border-t', HAIRLINE)}>
                    <th scope="row" className={cx('py-2.5 pr-4 text-left font-medium', INK)}>{item.label}</th>
                    <td className={cx('py-2.5 pl-4 text-right font-data tabular-nums', MUTED)}>{figure(item, item.prior, currency)}</td>
                    <td className={cx('py-2.5 pl-4 text-right font-data tabular-nums', INK)}>{figure(item, item.current, currency)}</td>
                    <td className="whitespace-nowrap py-2.5 pl-4 text-right font-data font-semibold tabular-nums">
                      <Change item={item} />
                    </td>
                    <td className={cx('whitespace-nowrap py-2.5 pl-6 text-left', MUTED)}>{READ_AS[item.tone] ?? READ_AS.flat}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul role="list" data-change-layout="rows" className={cx('border-t text-sm sm:hidden', HAIRLINE)}>
            {metrics.items.map((item) => (
              <li key={item.metric} className={cx('flex flex-col gap-1 border-b py-3 [overflow-wrap:anywhere]', HAIRLINE)}>
                <div className="flex items-baseline justify-between gap-3">
                  <span className={cx('min-w-0 font-semibold', INK)}>{item.label}</span>
                  <span className="shrink-0 font-data font-semibold tabular-nums">
                    <Change item={item} />
                  </span>
                </div>
                <div className={cx('flex flex-wrap items-baseline justify-between gap-x-3 text-xs', MUTED)}>
                  <span className="font-data tabular-nums">
                    <span className="sr-only">Prior </span>
                    {figure(item, item.prior, currency)}
                    <span aria-hidden="true"> → </span>
                    <span className="sr-only">, current </span>
                    {figure(item, item.current, currency)}
                  </span>
                  <span>{READ_AS[item.tone] ?? READ_AS.flat}</span>
                </div>
              </li>
            ))}
          </ul>

          <p className={cx('mt-2 text-xs', MUTED)}>
            ▲ and ▼ show the direction of each change. Color and “Read as” show whether that direction is usually
            favorable for the metric.
          </p>
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
    </>
  )

  if (bare) {
    return (
      <div>
        {(basisLine || priorLink) && (
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            {basisLine}
            {priorLink}
          </div>
        )}
        {body}
      </div>
    )
  }

  return (
    <Card as="section" aria-label="What changed" className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <Heading className={cx('text-lg font-semibold', INK)}>What changed</Heading>
          {basisLine}
        </div>
        {priorLink}
      </div>
      {body}
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

'use client'

import type { ReactNode } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { fmtCurrency, fmtPercent, fmtScale, parseNumeric } from '@/lib/format'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { PerAdsNote } from '@/features/summaries/components/PerAdsNote'
import { Card, CardHeader, CardTitle, CardFooter, DataTable, cx, type Column, type CellTone } from '@/components/ui'
import type { PerAdsValue } from '@/types/summary'
import type { BlockEvidence } from '@/features/summaries/api/summaries-api'

// A type alias (not an interface) so it satisfies DataTable's
// `T extends Record<string, unknown>` constraint via the implied index signature.
export type FinancialMetric = {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
  source_url?: string | null
  source_verified?: boolean | null
  source_section_ref?: string | null
  xbrl_concept?: string | null
  per_ads?: PerAdsValue | null
  // Change is computed server-side by metric_delta_service (one policy; ppts for margins). The
  // client renders this string verbatim and does NO delta math (rule 12 single-source gate).
  change_display?: string | null
  change_direction?: 'up' | 'down' | 'flat' | null
  change_tone?: CellTone | null
  // T4: server-verified citation for the Investor-Takeaway (`commentary`) — a text-anchored deep link,
  // distinct from the XBRL number provenance above (MetricSourceLink).
  commentary_evidence?: BlockEvidence | null
}

interface FinancialMetricsTableProps {
  metrics?: FinancialMetric[]
  /** Footer note; a node lets a caller emphasise a phrase (the landing page's evidence card). */
  notes?: ReactNode
  // Embed mode (T2.4): render just the table (+ notes) without the wrapping Card / "Financial
  // Highlights" header, because the structured page's section Card already supplies that title.
  // Default false preserves the self-contained card for the standalone/legacy call sites.
  bare?: boolean
}

const formatMetricValue = (value: string): string => {
  if (!value) {
    return ''
  }

  const numeric = parseNumeric(value)
  if (numeric === null) {
    return value
  }

  if (value.includes('%')) {
    return fmtPercent(numeric)
  }

  if (value.includes('$')) {
    return fmtCurrency(numeric)
  }

  return fmtScale(numeric, { digits: 2 })
}

// Mirrors DataTable's (unexported) TONE map so the phone card's change chip reads exactly like the
// md table's change cell: the 700-level text tokens, bold for a move, quiet for flat. Keyed by the
// server's `change_tone`; the direction glyph (`change_direction`) carries the meaning, never the
// colour alone (lib/financialTone).
const CHANGE_TONE: Record<CellTone, string> = {
  gain: 'font-semibold text-gain-text dark:text-gain-dark',
  loss: 'font-semibold text-loss-text dark:text-loss-dark',
  flat: 'text-flat-light dark:text-flat-dark',
}

const EYEBROW = 'text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark'

/** The server-computed change, rendered the same way in both layouts (an em dash when absent). */
function renderChange(row: FinancialMetric): ReactNode {
  // Server-computed string only — no client-side delta math (single-source gate).
  if (!row.change_display) {
    return <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
  }
  const Icon = row.change_direction === 'up' ? TrendUpIcon : row.change_direction === 'down' ? TrendDownIcon : MinusIcon
  // Direction never rides on color alone (financialTone rule) — the icon carries it.
  return (
    <span className="inline-flex items-center gap-1">
      <Icon className="h-4 w-4 shrink-0" />
      {row.change_display}
    </span>
  )
}

export default function FinancialMetricsTable({ metrics, notes, bare = false }: FinancialMetricsTableProps) {
  if (!metrics || metrics.length === 0) {
    return null
  }

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)
  const caption = hasComparatives
    ? 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
    : 'Financial highlights: current period and investor takeaway per metric'

  const columns: Column<FinancialMetric>[] = [
    {
      key: 'metric',
      header: 'Metric',
      render: (row) => (
        <div className="flex flex-col font-medium text-text-primary-light dark:text-text-primary-dark">
          <span>{row.metric}</span>
          <MetricSourceLink
            url={row.source_url}
            verified={row.source_verified}
            concept={row.xbrl_concept}
            sectionRef={row.source_section_ref}
          />
        </div>
      ),
    },
    {
      key: 'current_period',
      header: 'Current Period',
      align: 'right',
      numeric: true,
      render: (row) => (
        <span className="whitespace-nowrap text-text-primary-light dark:text-text-primary-dark">
          {formatMetricValue(row.current_period)}
          {row.per_ads && <PerAdsNote perAds={row.per_ads} />}
        </span>
      ),
    },
    ...(hasComparatives
      ? ([
          {
            key: 'prior_period',
            header: 'Prior Period',
            align: 'right',
            numeric: true,
            render: (row) => (
              <span className="whitespace-nowrap text-text-secondary-light dark:text-text-secondary-dark">
                {formatMetricValue(row.prior_period)}
              </span>
            ),
          },
          {
            key: 'change',
            header: 'Change',
            align: 'right',
            numeric: true,
            tone: (row) => row.change_tone ?? undefined,
            render: (row) => (
              <span className="whitespace-nowrap">
                {renderChange(row)}
              </span>
            ),
          },
        ] satisfies Column<FinancialMetric>[])
      : []),
    {
      key: 'commentary',
      header: 'Investor Takeaway',
      render: (row) => (
        <div className="flex flex-col gap-1">
          <span className="text-text-secondary-light dark:text-text-secondary-dark">{row.commentary || '-'}</span>
          {row.commentary_evidence && (
            <SourceTrace
              url={row.commentary_evidence.fragment_url}
              verified={row.commentary_evidence.verified}
              sectionRef={row.commentary_evidence.section_ref}
              excerpt={row.commentary_evidence.verified ? row.commentary_evidence.excerpt : null}
            />
          )}
        </div>
      ),
    },
  ]

  // Two presentations of the same rows, switched by CSS alone (`md:` = 768px, the documented
  // breakpoint): below md the five-column table left ~400px-tall rows with the takeaway and its
  // provenance pushed out of view, so each metric is one stacked card there; at/above md the
  // DataTable is unchanged (inside the self-contained Card the list takes the Card's own gutter). The inactive layout is display:none — out of the accessibility tree
  // and the tab order — and nothing in either carries a static id, so the duplicate is inert. A
  // JS media query would render the phone layout on the server for every viewer and flip after
  // hydration; CSS keeps SSR deterministic (the SummaryBlocks section nav uses the same idiom).
  const table = (
    <div className="hidden md:block" data-metric-table>
      <DataTable
        columns={columns}
        rows={metrics}
        rowKey={(row, index) => `${row.metric}-${index}`}
        caption={caption}
        className="px-2"
      />
    </div>
  )

  // Phone cards: every cell the table shows, in reading order — name + XBRL chip, the values with
  // their period labels (a `<dl>` so each figure is announced with its label; the row wraps rather
  // than clipping when a value is longer than the fixture's), the takeaway and its chip. Type never
  // drops below the table's (text-sm body, text-xs labels — the table's header size); no nowrap,
  // ellipsis, line clamp or fixed height anywhere: long content grows the card.
  const cards = (
    <ul className={cx('space-y-3 md:hidden', !bare && 'px-5 pb-4')} aria-label={caption} data-metric-cards>
      {metrics.map((row, index) => {
        const prior = hasComparatives ? formatMetricValue(row.prior_period) : ''
        return (
          <li
            key={`${row.metric}-${index}`}
            data-metric-card
            className="min-w-0 rounded-lg border border-border-light bg-white p-3 dark:border-white/10 dark:bg-white/5"
          >
            <div className="flex flex-col font-medium text-text-primary-light dark:text-text-primary-dark">
              <span className="break-words">{row.metric}</span>
              <MetricSourceLink
                url={row.source_url}
                verified={row.source_verified}
                concept={row.xbrl_concept}
                sectionRef={row.source_section_ref}
              />
            </div>
            <dl className="mt-2 flex flex-wrap items-start gap-x-5 gap-y-2">
              <div className="min-w-0">
                <dt className={EYEBROW}>Current period</dt>
                <dd className="break-words font-data text-sm tabular-nums text-text-primary-light dark:text-text-primary-dark">
                  {formatMetricValue(row.current_period)}
                  {row.per_ads && <PerAdsNote perAds={row.per_ads} />}
                </dd>
              </div>
              {prior && (
                <div className="min-w-0">
                  <dt className={EYEBROW}>Prior period</dt>
                  <dd className="break-words font-data text-sm tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
                    {prior}
                  </dd>
                </div>
              )}
              {hasComparatives && (
                <div className="min-w-0">
                  <dt className={EYEBROW}>Change</dt>
                  <dd className={cx('break-words font-data text-sm tabular-nums', row.change_tone && CHANGE_TONE[row.change_tone])}>
                    {renderChange(row)}
                  </dd>
                </div>
              )}
            </dl>
            <div className="mt-2 flex flex-col gap-1">
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{row.commentary || '-'}</p>
              {row.commentary_evidence && (
                <SourceTrace
                  url={row.commentary_evidence.fragment_url}
                  verified={row.commentary_evidence.verified}
                  sectionRef={row.commentary_evidence.section_ref}
                  excerpt={row.commentary_evidence.verified ? row.commentary_evidence.excerpt : null}
                />
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )

  const layouts = (
    <>
      {cards}
      {table}
    </>
  )

  // Embedded in a structured-page section Card — no wrapping Card / header (that would double the
  // "Financial Highlights" title). Notes render as a plain trailing paragraph instead of a footer.
  if (bare) {
    return (
      <>
        {layouts}
        {notes && (
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{notes}</p>
        )}
      </>
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Financial Highlights</CardTitle>
      </CardHeader>
      {layouts}
      {notes && (
        <CardFooter>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{notes}</p>
        </CardFooter>
      )}
    </Card>
  )
}

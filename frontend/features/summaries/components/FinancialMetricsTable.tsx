'use client'

import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { fmtCurrency, fmtPercent, fmtScale, parseNumeric } from '@/lib/format'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { PerAdsNote } from '@/features/summaries/components/PerAdsNote'
import { Card, CardHeader, CardTitle, CardFooter, DataTable, type Column, type CellTone } from '@/components/ui'
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
  notes?: string
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

export default function FinancialMetricsTable({ metrics, notes, bare = false }: FinancialMetricsTableProps) {
  if (!metrics || metrics.length === 0) {
    return null
  }

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)

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
            render: (row) => {
              // Server-computed string only — no client-side delta math (single-source gate).
              if (!row.change_display) {
                return <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
              }
              const Icon =
                row.change_direction === 'up'
                  ? TrendUpIcon
                  : row.change_direction === 'down'
                    ? TrendDownIcon
                    : MinusIcon
              // Direction never rides on color alone (financialTone rule) — the icon carries it.
              return (
                <span className="inline-flex items-center gap-1 whitespace-nowrap">
                  <Icon className="h-4 w-4" />
                  {row.change_display}
                </span>
              )
            },
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

  const table = (
    <DataTable
      columns={columns}
      rows={metrics}
      rowKey={(row, index) => `${row.metric}-${index}`}
      caption={
        hasComparatives
          ? 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
          : 'Financial highlights: current period and investor takeaway per metric'
      }
      className="px-2"
    />
  )

  // Embedded in a structured-page section Card — no wrapping Card / header (that would double the
  // "Financial Highlights" title). Notes render as a plain trailing paragraph instead of a footer.
  if (bare) {
    return (
      <>
        {table}
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
      {table}
      {notes && (
        <CardFooter>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{notes}</p>
        </CardFooter>
      )}
    </Card>
  )
}

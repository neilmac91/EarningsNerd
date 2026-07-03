'use client'

import { useContext, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

import {
  getFilingFundamentals,
  FundamentalsResponse,
} from '@/features/fundamentals/api/fundamentals-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { WarningIcon } from '@/lib/icons'
import { ThemeContext } from '@/components/ThemeProvider'
import { Badge, Card, seriesColor, gridProps, xAxisProps, yAxisProps, barCursorProps, ChartTooltip, Skeleton } from '@/components/ui'

type FmtKind = 'usd' | 'eps' | 'pct' | 'ratio'

// Curated, ordered set of concepts to offer (only those present in the response are shown).
// `concept` keys match the backend's standardized vocabulary (facts_service._CONCEPT_UNITS).
const FEATURED: { key: string; label: string; fmt: FmtKind }[] = [
  { key: 'revenue', label: 'Revenue', fmt: 'usd' },
  { key: 'net_income', label: 'Net Income', fmt: 'usd' },
  { key: 'gross_profit', label: 'Gross Profit', fmt: 'usd' },
  { key: 'operating_income', label: 'Operating Income', fmt: 'usd' },
  { key: 'operating_cash_flow', label: 'Operating Cash Flow', fmt: 'usd' },
  { key: 'investing_cash_flow', label: 'Investing Cash Flow', fmt: 'usd' },
  { key: 'financing_cash_flow', label: 'Financing Cash Flow', fmt: 'usd' },
  { key: 'free_cash_flow', label: 'Free Cash Flow', fmt: 'usd' },
  { key: 'eps_diluted', label: 'Diluted EPS', fmt: 'eps' },
  { key: 'earnings_per_share', label: 'EPS', fmt: 'eps' },
  { key: 'gross_margin', label: 'Gross Margin', fmt: 'pct' },
  { key: 'operating_margin', label: 'Operating Margin', fmt: 'pct' },
  { key: 'net_margin', label: 'Net Margin', fmt: 'pct' },
  { key: 'total_assets', label: 'Total Assets', fmt: 'usd' },
  { key: 'current_assets', label: 'Current Assets', fmt: 'usd' },
  { key: 'current_liabilities', label: 'Current Liabilities', fmt: 'usd' },
  { key: 'working_capital', label: 'Working Capital', fmt: 'usd' },
  { key: 'current_ratio', label: 'Current Ratio', fmt: 'ratio' },
  { key: 'shareholders_equity', label: "Shareholders' Equity", fmt: 'usd' },
]


// Derive an ISO-4217 currency code from a fact's stored unit (e.g. "CNY", "CNY/shares" -> "CNY",
// "pure" -> USD fallback, never used for percentages). Foreign issuers report in their own
// currency, so a CNY/EUR value must NOT render with a "$".
const currencyFromUnit = (unit: string | undefined): string => {
  const code = (unit || 'USD').split('/')[0].trim().toUpperCase()
  return /^[A-Z]{3}$/.test(code) ? code : 'USD'
}

const formatValue = (value: number, fmt: FmtKind, currency = 'USD'): string => {
  if (fmt === 'pct') return fmtPercent(value, { digits: 1 })
  // A ratio (e.g. current ratio 2.5) is a dimensionless multiple — never a "$" or "%".
  if (fmt === 'ratio')
    return `${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}×`
  if (fmt === 'eps') return fmtCurrency(value, { currency, digits: 2, compact: false })
  return fmtCurrency(value, { currency, compact: true })
}

export default function FundamentalsTrendChart({
  filingId,
  subtitle,
}: {
  // Filing-scoped (roadmap B): the multi-year figures *as reported in this specific filing* — an
  // immutable snapshot faithful to the document, not the company's accumulated latest series.
  filingId: number
  // Optional context line under the heading (the filing page passes one to frame the source).
  subtitle?: string
}) {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw. Chrome comes from the
  // Chart factories (chartTheme/gridProps/axis props/ChartTooltip) — no local hexes.
  const dark = useContext(ThemeContext)?.theme === 'dark'

  const { data, isLoading, isError } = useQuery<FundamentalsResponse>({
    queryKey: ['filing-fundamentals', filingId],
    queryFn: () => getFilingFundamentals(filingId),
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    staleTime: 60 * 60 * 1000, // facts change only with new filings (filing-scoped is immutable)
    gcTime: 2 * 60 * 60 * 1000,
  })

  // The concepts actually available for this company, in our curated order.
  const available = useMemo(() => {
    const present = new Set((data?.concepts ?? []).map((c) => c.concept))
    return FEATURED.filter((f) => present.has(f.key))
  }, [data])

  const [selected, setSelected] = useState<string | null>(null)
  const activeKey = selected && available.some((a) => a.key === selected)
    ? selected
    : available[0]?.key ?? null
  const active = FEATURED.find((f) => f.key === activeKey)
  // Reporting currency of the active series (CNY for an FPI like Alibaba), so values render in the
  // as-filed currency rather than an implied USD "$".
  const activeCurrency = currencyFromUnit(
    data?.concepts.find((c) => c.concept === activeKey)?.unit
  )

  const chartData = useMemo(() => {
    if (!data || !activeKey) return []
    const series = data.concepts.find((c) => c.concept === activeKey)
    if (!series) return []
    return series.points
      .filter((p) => p.value !== null)
      .map((p) => ({
        year: String(p.fiscal_year ?? (p.period_end ? p.period_end.slice(0, 4) : '')),
        value: p.value as number,
      }))
  }, [data, activeKey])

  // Any flagged value in the active series → show the honesty badge.
  const hasUnverified = useMemo(() => {
    if (!data || !activeKey) return false
    const series = data.concepts.find((c) => c.concept === activeKey)
    return !!series?.points.some((p) => p.reconciled === false)
  }, [data, activeKey])

  // Supplementary section: stay quiet on error, and disappear when there are no facts
  // (e.g. before the backfill runs) rather than showing an empty card. Keep the card (with a
  // spinner sized to the chart) mounted *while loading* so the common "has data" case doesn't
  // shift content when the query resolves — only collapse once we know there are no facts.
  if (isError || (!isLoading && available.length === 0)) return null

  return (
    <Card as="section" className="mb-8 p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Financial Trends</h2>
            {hasUnverified && (
              <Badge
                variant="warning"
                icon={<WarningIcon className="h-3 w-3" aria-hidden="true" />}
                title="Some figures here are machine-extracted from XBRL and failed an automated sanity check (e.g. an unusual period-over-period swing). Treat them with caution and verify against the filing."
              >
                Unverified
              </Badge>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">{subtitle}</p>
          )}
        </div>
        {available.length > 0 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Select metric">
            {available.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setSelected(f.key)}
                aria-pressed={f.key === activeKey}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  f.key === activeKey
                    ? 'bg-brand hover:bg-brand-strong active:bg-brand-emphasis text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                    : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <div role="status" aria-label="Loading financial trends">
          <Skeleton className="h-72 w-full rounded-lg" />
          <span className="sr-only">Loading…</span>
        </div>
      ) : chartData.length === 0 ? (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          No multi-year data available for this metric.
        </p>
      ) : (
        <div className="h-72 w-full" data-testid="fundamentals-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis dataKey="year" {...xAxisProps(dark)} />
              <YAxis
                {...yAxisProps(dark)}
                width={70 /* currency tick labels outgrow the factory's 44px */}
                tickFormatter={(v: number) => formatValue(v, active?.fmt ?? 'usd', activeCurrency)}
              />
              <Tooltip
                cursor={barCursorProps(dark)}
                content={
                  <ChartTooltip
                    dark={dark}
                    formatValue={(v) => formatValue(Number(v), active?.fmt ?? 'usd', activeCurrency)}
                  />
                }
              />
              <Bar
                dataKey="value"
                name={active?.label ?? 'Value'}
                fill={seriesColor(0)}
                radius={[4, 4, 0, 0]}
                maxBarSize={56}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Annual figures from SEC filings (XBRL){activeCurrency !== 'USD' ? `, reported in ${activeCurrency}` : ''}.{' '}
        {active ? active.label : ''} by fiscal year.
      </p>
    </Card>
  )
}

'use client'

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2 } from 'lucide-react'

import { getFundamentals, FundamentalsResponse } from '@/features/fundamentals/api/fundamentals-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import UnverifiedBadge from '@/components/UnverifiedBadge'

type FmtKind = 'usd' | 'eps' | 'pct'

// Curated, ordered set of concepts to offer (only those present in the response are shown).
// `concept` keys match the backend's standardized vocabulary (facts_service._CONCEPT_UNITS).
const FEATURED: { key: string; label: string; fmt: FmtKind }[] = [
  { key: 'revenue', label: 'Revenue', fmt: 'usd' },
  { key: 'net_income', label: 'Net Income', fmt: 'usd' },
  { key: 'gross_profit', label: 'Gross Profit', fmt: 'usd' },
  { key: 'operating_income', label: 'Operating Income', fmt: 'usd' },
  { key: 'operating_cash_flow', label: 'Operating Cash Flow', fmt: 'usd' },
  { key: 'free_cash_flow', label: 'Free Cash Flow', fmt: 'usd' },
  { key: 'eps_diluted', label: 'Diluted EPS', fmt: 'eps' },
  { key: 'earnings_per_share', label: 'EPS', fmt: 'eps' },
  { key: 'gross_margin', label: 'Gross Margin', fmt: 'pct' },
  { key: 'operating_margin', label: 'Operating Margin', fmt: 'pct' },
  { key: 'net_margin', label: 'Net Margin', fmt: 'pct' },
  { key: 'total_assets', label: 'Total Assets', fmt: 'usd' },
  { key: 'shareholders_equity', label: "Shareholders' Equity", fmt: 'usd' },
]

const MINT = '#10B981'

const formatValue = (value: number, fmt: FmtKind): string => {
  if (fmt === 'pct') return fmtPercent(value, { digits: 1 })
  if (fmt === 'eps') return fmtCurrency(value, { digits: 2, compact: false })
  return fmtCurrency(value, { compact: true })
}

export default function FundamentalsTrendChart({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useQuery<FundamentalsResponse>({
    queryKey: ['fundamentals', ticker],
    queryFn: () => getFundamentals(ticker),
    enabled: !!ticker,
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    staleTime: 60 * 60 * 1000, // facts change only with new filings
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
    <section className="mb-8 rounded-lg border border-border-light bg-panel-light p-6 shadow-sm dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Financial Trends</h2>
          {hasUnverified && <UnverifiedBadge />}
        </div>
        {available.length > 0 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Select metric">
            {available.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setSelected(f.key)}
                aria-pressed={f.key === activeKey}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  f.key === activeKey
                    ? 'bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark'
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
        <div className="flex h-72 items-center justify-center" aria-label="Loading financial trends">
          <Loader2 className="h-6 w-6 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        </div>
      ) : chartData.length === 0 ? (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
          No multi-year data available for this metric.
        </p>
      ) : (
        <div className="h-72 w-full" data-testid="fundamentals-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#9CA3AF" strokeOpacity={0.2} vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
              <YAxis
                tick={{ fontSize: 12, fill: '#9CA3AF' }}
                tickLine={false}
                axisLine={false}
                width={70}
                tickFormatter={(v: number) => formatValue(v, active?.fmt ?? 'usd')}
              />
              <Tooltip
                cursor={{ fill: 'rgba(16,185,129,0.08)' }}
                formatter={(v) => [formatValue(Number(v), active?.fmt ?? 'usd'), active?.label ?? '']}
                contentStyle={{
                  background: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: 8,
                  color: '#fff',
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" fill={MINT} radius={[4, 4, 0, 0]} maxBarSize={56} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
        Annual figures from SEC filings (XBRL). {active ? active.label : ''} by fiscal year.
      </p>
    </section>
  )
}

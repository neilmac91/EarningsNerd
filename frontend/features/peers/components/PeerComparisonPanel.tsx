'use client'

import { useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { CircleNotchIcon } from '@/lib/icons'

import { getPeers, PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import UnverifiedBadge from '@/components/UnverifiedBadge'
import { ThemeContext } from '@/components/ThemeProvider'

type FmtKind = 'usd' | 'eps' | 'pct'

// Metrics offered in the selector. `key` matches the backend's standardized concepts.
const METRICS: { key: string; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'net_income', label: 'Net Income' },
  { key: 'gross_profit', label: 'Gross Profit' },
  { key: 'operating_income', label: 'Operating Income' },
  { key: 'net_margin', label: 'Net Margin' },
  { key: 'operating_margin', label: 'Operating Margin' },
  { key: 'gross_margin', label: 'Gross Margin' },
  { key: 'eps_diluted', label: 'Diluted EPS' },
  { key: 'total_assets', label: 'Total Assets' },
]

const MAX_BARS = 10
const SUBJECT_FILL = '#3E8E84' // chart.1 (teal)

const fmtKindFor = (unit: string | null | undefined): FmtKind =>
  unit === 'pure' ? 'pct' : unit === 'USD/shares' ? 'eps' : 'usd'

const formatValue = (value: number, kind: FmtKind): string => {
  if (kind === 'pct') return fmtPercent(value, { digits: 1 })
  if (kind === 'eps') return fmtCurrency(value, { digits: 2, compact: false })
  return fmtCurrency(value, { compact: true })
}

export default function PeerComparisonPanel({ ticker }: { ticker: string }) {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const axisText = dark ? '#9CA3AF' : '#6B7280'
  const peerFill = dark ? '#475569' : '#94A3B8'
  const tooltipBg = dark ? '#1F2937' : '#FBFAF6'
  const tooltipBorder = dark ? 'rgba(255,255,255,0.1)' : '#E5E7EB'
  const tooltipText = dark ? '#D7DADC' : '#1A1A17'
  const cursorFill = dark ? 'rgba(62,142,132,0.16)' : 'rgba(62,142,132,0.08)'

  const [metric, setMetric] = useState('revenue')
  const { data, isLoading, isError } = useQuery<PeerComparisonResponse>({
    queryKey: ['peers', ticker, metric],
    queryFn: () => getPeers(ticker, metric),
    enabled: !!ticker,
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    staleTime: 60 * 60 * 1000,
    gcTime: 2 * 60 * 60 * 1000,
  })

  // Keep the panel mounted once any metric has shown peers, so switching to a
  // sparse metric shows an inline message instead of making the panel vanish.
  const everHadPeers = useRef(false)
  useEffect(() => {
    if (data && data.peer_count >= 2) {
      everHadPeers.current = true
    }
  }, [data])

  const meaningful = !!data && data.peer_count >= 2
  const label = METRICS.find((m) => m.key === metric)?.label ?? metric
  const kind = fmtKindFor(data?.unit)

  const chartData = useMemo(() => {
    if (!data || data.peer_count < 2) return []
    const rows = data.peers.filter((p) => p.value !== null)
    // `peers` is ranked value-desc; show the top N but always include the subject.
    const top = rows.slice(0, MAX_BARS)
    if (!top.some((p) => p.is_subject)) {
      const subj = rows.find((p) => p.is_subject)
      if (subj) top.push(subj)
    }
    return top.map((p) => ({
      ticker: p.ticker,
      value: p.value as number,
      isSubject: p.is_subject,
      reconciled: p.reconciled,
    }))
  }, [data])

  // Any flagged value among the shown bars → surface the honesty badge.
  const hasUnverified = chartData.some((d) => d.reconciled === false)

  // Hide entirely until we know there are peers for at least one metric. Once the
  // panel has shown peers, keep it mounted and surface errors/sparsity inline.
  if (isError && !everHadPeers.current) return null
  if (!everHadPeers.current && (isLoading || !data || data.peer_count < 2)) return null

  const subject = data?.subject

  return (
    <section className="mb-8 rounded-lg border border-border-light bg-panel-light p-6 shadow-sm dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Sector Peers</h2>
            {hasUnverified && <UnverifiedBadge />}
          </div>
          {meaningful && subject?.rank != null && (
            <p className="mt-1 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
              Ranks <span className="font-semibold text-brand-strong dark:text-brand-strong-dark">#{subject.rank}</span>{' '}
              of {data!.peer_count} on {label}
              {subject.percentile != null ? ` · ${Math.round(subject.percentile)}th percentile` : ''}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Select metric">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setMetric(m.key)}
              aria-pressed={m.key === metric}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                m.key === metric
                  ? 'bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                  : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-72 items-center justify-center" aria-label="Loading peer comparison">
          <CircleNotchIcon className="h-6 w-6 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          Couldn&rsquo;t load peer data for {label}. Try another metric.
        </p>
      ) : !meaningful ? (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          Not enough sector peers with {label} data yet.
        </p>
      ) : (
        <div className="h-72 w-full" data-testid="peers-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
            >
              <XAxis
                type="number"
                tick={{ fontSize: 12, fill: axisText }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => formatValue(v, kind)}
              />
              <YAxis
                type="category"
                dataKey="ticker"
                tick={{ fontSize: 12, fill: axisText }}
                tickLine={false}
                axisLine={false}
                width={64}
              />
              <Tooltip
                cursor={{ fill: cursorFill }}
                formatter={(v) => [formatValue(Number(v), kind), label]}
                contentStyle={{
                  background: tooltipBg,
                  border: `1px solid ${tooltipBorder}`,
                  borderRadius: 8,
                  color: tooltipText,
                  fontSize: 12,
                }}
                labelStyle={{ color: tooltipText }}
                itemStyle={{ color: tooltipText }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={28}>
                {chartData.map((entry) => (
                  <Cell key={entry.ticker} fill={entry.isSubject ? SUBJECT_FILL : peerFill} fillOpacity={entry.isSubject ? 1 : 0.45} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Same-SIC peers, most recent annual {label} from SEC filings. Coverage grows over time.
      </p>
    </section>
  )
}

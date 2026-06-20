'use client'

import { useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Loader2 } from 'lucide-react'

import { getPeers, PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtPercent } from '@/lib/format'

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
const MINT = '#10B981'
const GRAY = '#9CA3AF'

const fmtKindFor = (unit: string | null | undefined): FmtKind =>
  unit === 'pure' ? 'pct' : unit === 'USD/shares' ? 'eps' : 'usd'

const formatValue = (value: number, kind: FmtKind): string => {
  if (kind === 'pct') return fmtPercent(value, { digits: 1 })
  if (kind === 'eps') return fmtCurrency(value, { digits: 2, compact: false })
  return fmtCurrency(value, { compact: true })
}

export default function PeerComparisonPanel({ ticker }: { ticker: string }) {
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
  if (data && data.peer_count >= 2) everHadPeers.current = true

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
    }))
  }, [data])

  // Hide entirely until we know there are peers for at least one metric.
  if (isError) return null
  if (!everHadPeers.current && (isLoading || !data || data.peer_count < 2)) return null

  const subject = data?.subject

  return (
    <section className="mb-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-slate-900">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Sector Peers</h2>
          {meaningful && subject?.rank != null && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Ranks <span className="font-semibold text-mint-600 dark:text-mint-400">#{subject.rank}</span>{' '}
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
                  ? 'bg-mint-500 text-slate-950'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-72 items-center justify-center" aria-label="Loading peer comparison">
          <Loader2 className="h-6 w-6 animate-spin text-mint-500" />
        </div>
      ) : !meaningful ? (
        <p className="py-12 text-center text-sm text-gray-500 dark:text-gray-400">
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
                tick={{ fontSize: 12, fill: GRAY }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => formatValue(v, kind)}
              />
              <YAxis
                type="category"
                dataKey="ticker"
                tick={{ fontSize: 12, fill: GRAY }}
                tickLine={false}
                axisLine={false}
                width={64}
              />
              <Tooltip
                cursor={{ fill: 'rgba(16,185,129,0.08)' }}
                formatter={(v) => [formatValue(Number(v), kind), label]}
                contentStyle={{
                  background: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: 8,
                  color: '#fff',
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={28}>
                {chartData.map((entry) => (
                  <Cell key={entry.ticker} fill={entry.isSubject ? MINT : GRAY} fillOpacity={entry.isSubject ? 1 : 0.45} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
        Same-SIC peers, most recent annual {label} from SEC filings. Coverage grows over time.
      </p>
    </section>
  )
}

'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

import { getPeers, PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { WarningIcon } from '@/lib/icons'
import { ThemeContext } from '@/components/ThemeProvider'
import { Badge, Card, seriesColor, chartTheme, xAxisProps, yAxisProps, barCursorProps, ChartTooltip, Skeleton } from '@/components/ui'

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

// Any "<ccy>/shares" unit is a per-share metric; "pure" is a ratio; everything else is a
// monetary amount. Keyed on the suffix (not a literal "USD/shares") so a foreign issuer's
// "CNY/shares" is recognised as EPS rather than mislabelled as a compact currency.
const fmtKindFor = (unit: string | null | undefined): FmtKind =>
  unit === 'pure' ? 'pct' : unit?.endsWith('/shares') ? 'eps' : 'usd'

// Derive an ISO-4217 code from the stored unit ("CNY", "CNY/shares" -> "CNY"; "pure"/unknown ->
// USD fallback, never used for percentages) so a foreign issuer's value never renders with a "$".
const currencyFromUnit = (unit: string | null | undefined): string => {
  const code = (unit || 'USD').split('/')[0].trim().toUpperCase()
  return /^[A-Z]{3}$/.test(code) ? code : 'USD'
}

const formatValue = (value: number, kind: FmtKind, currency = 'USD'): string => {
  if (kind === 'pct') return fmtPercent(value, { digits: 1 })
  if (kind === 'eps') return fmtCurrency(value, { currency, digits: 2, compact: false })
  return fmtCurrency(value, { currency, compact: true })
}

export default function PeerComparisonPanel({ ticker }: { ticker: string }) {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw. Chrome comes from the
  // Chart factories (chartTheme/axis props/ChartTooltip) — no local hexes.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  // De-emphasized peer bars: the theme's neutral grey at partial opacity keeps the
  // subject (seriesColor(0)) unmistakably THE bar — a magnitude ranking, not deltas.
  const peerFill = chartTheme(dark).flat

  const [metric, setMetric] = useState('revenue')
  const { data, isLoading, isError } = useQuery<PeerComparisonResponse>({
    queryKey: queryKeys.peers(ticker, metric),
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
  const currency = currencyFromUnit(data?.unit)

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
  // eslint-disable-next-line react-hooks/refs -- intentional render-time ref latch: everHadPeers only flips false->true to keep the panel mounted once it has shown peers; reading it in render avoids re-render churn
  if (isError && !everHadPeers.current) return null
  // eslint-disable-next-line react-hooks/refs -- intentional render-time ref latch: everHadPeers only flips false->true to keep the panel mounted once it has shown peers; reading it in render avoids re-render churn
  if (!everHadPeers.current && (isLoading || !data || data.peer_count < 2)) return null

  const subject = data?.subject

  return (
    <Card as="section" className="mb-8 p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Sector Peers</h2>
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
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                m.key === metric
                  ? 'bg-brand hover:bg-brand-strong active:bg-brand-emphasis text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                  : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div role="status" aria-label="Loading peer comparison">
          <Skeleton className="h-72 w-full rounded-lg" />
          <span className="sr-only">Loading…</span>
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
                {...xAxisProps(dark)}
                axisLine={false /* horizontal bars: the category labels carry the scale */}
                tickFormatter={(v: number) => formatValue(v, kind, currency)}
              />
              <YAxis type="category" dataKey="ticker" {...yAxisProps(dark)} width={64 /* tickers outgrow the factory's 44px */} />
              <Tooltip
                cursor={barCursorProps(dark)}
                content={<ChartTooltip dark={dark} formatValue={(v) => formatValue(Number(v), kind, currency)} />}
              />
              <Bar dataKey="value" name={label} radius={[0, 4, 4, 0]} maxBarSize={28}>
                {chartData.map((entry) => (
                  <Cell key={entry.ticker} fill={entry.isSubject ? seriesColor(0) : peerFill} fillOpacity={entry.isSubject ? 1 : 0.45} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Same-SIC peers, most recent annual {label} from SEC filings. Coverage grows over time.
      </p>
    </Card>
  )
}

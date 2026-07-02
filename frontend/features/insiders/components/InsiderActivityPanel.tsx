'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

import {
  getInsiderActivity,
  InsiderActivityResponse,
  InsiderTransaction,
} from '@/features/insiders/api/insiders-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtScale } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { Badge, DataTable, Skeleton, type Column } from '@/components/ui'

const WINDOWS: { days: number; label: string }[] = [
  { days: 90, label: '90D' },
  { days: 180, label: '180D' },
  { days: 365, label: '1Y' },
]

const MAX_ROWS = 8

const fmtShares = (n: number | null | undefined): string =>
  n === null || n === undefined ? '—' : fmtScale(Math.abs(n), { digits: 1 })

const fmtMoney = (n: number | null | undefined): string =>
  n === null || n === undefined ? '—' : fmtCurrency(Math.abs(n), { compact: true })

function roleOf(t: InsiderTransaction): string {
  if (t.insider_title) return t.insider_title
  const roles: string[] = []
  if (t.is_officer) roles.push('Officer')
  if (t.is_director) roles.push('Director')
  if (t.is_ten_pct_owner) roles.push('10% Owner')
  return roles.join(', ') || '—'
}

// 'A' (acquired) is a buy, 'D' (disposed) a sell; fall back to the label text.
function isBuy(t: InsiderTransaction): boolean {
  if (t.acquired_disposed) return t.acquired_disposed.toUpperCase() === 'A'
  return (t.transaction_label ?? '').toLowerCase().includes('buy')
}

// v2 DataTable columns: Shares/Value/Date are numeric (data face + tabular-nums,
// right-aligned); the Type cell tone carries buy/sell as gain/loss — the label
// text ("Buy"/"Sell") means color is never the sole cue.
const TRANSACTION_COLUMNS: Column<InsiderTransaction>[] = [
  {
    key: 'insider',
    header: 'Insider',
    render: (t) => (
      <>
        <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
          {t.insider_name ?? '—'}
        </span>
        <span className="block text-xs text-text-tertiary-light dark:text-text-secondary-dark">{roleOf(t)}</span>
      </>
    ),
  },
  {
    key: 'type',
    header: 'Type',
    tone: (t) => (isBuy(t) ? 'gain' : 'loss'),
    render: (t) => (
      <>
        {t.transaction_label ?? (isBuy(t) ? 'Buy' : 'Sell')}
        {t.is_10b5_1 && (
          <Badge variant="neutral" icon={null} className="ml-1.5">
            10b5-1
          </Badge>
        )}
      </>
    ),
  },
  { key: 'shares', header: 'Shares', align: 'right', numeric: true, render: (t) => fmtShares(t.shares) },
  { key: 'value', header: 'Value', align: 'right', numeric: true, render: (t) => fmtMoney(t.value) },
  { key: 'date', header: 'Date', align: 'right', numeric: true, render: (t) => t.transaction_date ?? '—' },
]

export default function InsiderActivityPanel({
  ticker,
  isFpi,
}: {
  ticker: string
  isFpi?: boolean
}) {
  const [windowDays, setWindowDays] = useState(90)
  const { data, isLoading, isError } = useQuery<InsiderActivityResponse>({
    queryKey: ['insiders', ticker, windowDays],
    queryFn: () => getInsiderActivity(ticker, windowDays),
    // Foreign private issuers don't file Form 4s — skip the (slow) live SEC read entirely. While
    // filings are still loading isFpi is undefined, so only enable the query once we KNOW the
    // company is not an FPI (isFpi === false) — never fire a premature read on an as-yet-unknown FPI.
    enabled: !!ticker && isFpi === false,
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    staleTime: 60 * 60 * 1000, // Form 4 data changes slowly; the endpoint is a live SEC read
    gcTime: 2 * 60 * 60 * 1000,
  })

  // Keep the panel mounted once it has shown trades, so switching to a quiet window shows an
  // inline message instead of making the panel vanish.
  const everHadData = useRef(false)
  useEffect(() => {
    if (data && data.total_transactions > 0) everHadData.current = true
  }, [data])

  // Foreign private issuers (20-F/6-K filers) are generally exempt from Section 16 insider
  // reporting, so there are no Form 4s to show. Render an honest note instead of an empty/absent
  // panel (the live SEC read is disabled for FPIs via `enabled` above).
  if (isFpi) {
    return (
      <section className="mb-8 rounded-xl border border-border-light bg-panel-light p-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
        <h2 className="mb-3 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider Activity</h2>
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Insider (Form&nbsp;4) reporting is not generally required for foreign private issuers, so
          no open-market insider trades are available for this company.
        </p>
      </section>
    )
  }

  // eslint-disable-next-line react-hooks/refs -- intentional render-time ref latch: everHadData only flips false->true to keep the panel mounted once it has shown trades; reading it in render avoids re-render churn
  if (isError && !everHadData.current) return null
  // eslint-disable-next-line react-hooks/refs -- intentional render-time ref latch: everHadData only flips false->true to keep the panel mounted once it has shown trades; reading it in render avoids re-render churn
  if (!everHadData.current && (isLoading || !data || data.total_transactions === 0)) return null

  const summary = data?.summary
  const hasTrades = !!data && data.total_transactions > 0
  // Lead with net value when known, else net shares. The sign is the buy/sell signal.
  const signalValue = summary ? (summary.net_value ?? summary.net_shares) : 0
  const signalIsValue = !!summary && summary.net_value !== null
  const direction = signalValue > 0 ? 'buy' : signalValue < 0 ? 'sell' : 'flat'
  const planSells = summary?.plan_10b5_1_sell_shares ?? 0

  const SignalIcon = direction === 'buy' ? TrendUpIcon : direction === 'sell' ? TrendDownIcon : MinusIcon
  // Design-system gain/loss semantics: buys = gain (green), sells = loss (red), balanced = flat.
  // The magnitude + arrow glyph carry the signal alongside colour (colour is never the sole cue).
  const signalColor = directionText[direction === 'buy' ? 'up' : direction === 'sell' ? 'down' : 'flat']
  const signalText =
    direction === 'buy'
      ? 'Net insider buying'
      : direction === 'sell'
        ? 'Net insider selling'
        : 'Balanced insider activity'
  const signalMagnitude = signalIsValue ? fmtMoney(signalValue) : `${fmtShares(signalValue)} shares`

  return (
    // v2 Card recipe on the semantic <section> — lift via e2 in light, hairline-only in dark.
    <section className="mb-8 rounded-xl border border-border-light bg-panel-light p-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider Activity</h2>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Select window">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              type="button"
              onClick={() => setWindowDays(w.days)}
              aria-pressed={w.days === windowDays}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                w.days === windowDays
                  ? 'bg-brand hover:bg-brand-strong active:bg-brand-emphasis text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                  : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && !hasTrades ? (
        <div role="status" aria-label="Loading insider activity">
          <Skeleton className="h-48 w-full rounded-lg" />
          <span className="sr-only">Loading…</span>
        </div>
      ) : !hasTrades || !summary ? (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          No open-market insider trades in the last {windowDays} days.
        </p>
      ) : (
        <>
          {/* Signal headline */}
          <div className="mb-5 flex items-center gap-3">
            <SignalIcon className={`h-7 w-7 shrink-0 ${signalColor}`} aria-hidden="true" />
            <div>
              <p className={`text-lg font-semibold ${signalColor}`}>
                {signalText}
                {direction !== 'flat' && <> · {signalMagnitude}</>}
              </p>
              {planSells > 0 && (
                <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                  Excludes {fmtShares(planSells)} shares sold under pre-scheduled 10b5-1 plans
                  {summary.discretionary_net_shares !== summary.net_shares && (
                    <> · discretionary net {fmtShares(summary.discretionary_net_shares)} shares</>
                  )}
                </p>
              )}
            </div>
          </div>

          {/* Buy / Sell / Net stats */}
          <div className="mb-5 grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-gain-soft p-3 dark:bg-gain-soft-dark">
              <p className="text-xs font-medium text-gain-light dark:text-gain-dark">
                Buys ({summary.buy_count})
              </p>
              <p className="mt-0.5 text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                {fmtMoney(summary.buy_value) !== '—' ? fmtMoney(summary.buy_value) : `${fmtShares(summary.buy_shares)} sh`}
              </p>
            </div>
            <div className="rounded-lg bg-loss-soft p-3 dark:bg-loss-soft-dark">
              <p className="text-xs font-medium text-loss-light dark:text-loss-dark">
                Sells ({summary.sell_count})
              </p>
              <p className="mt-0.5 text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                {fmtMoney(summary.sell_value) !== '—' ? fmtMoney(summary.sell_value) : `${fmtShares(summary.sell_shares)} sh`}
              </p>
            </div>
            <div className="rounded-lg bg-background-light p-3 dark:bg-white/5">
              <p className="text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">Net</p>
              <p className={`mt-0.5 text-sm font-semibold ${signalColor}`}>
                {direction === 'sell' ? '−' : direction === 'buy' ? '+' : ''}
                {signalMagnitude}
              </p>
            </div>
          </div>

          {/* Recent transactions */}
          <DataTable
            columns={TRANSACTION_COLUMNS}
            rows={data!.transactions.slice(0, MAX_ROWS)}
            rowKey={(t, i) => `${t.accession ?? ''}-${i}`}
            caption="Recent open-market insider transactions: insider, type, shares, value, and date"
          />
        </>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Open-market Form 4 trades from SEC EDGAR. 10b5-1 marks pre-scheduled trades (weaker signal).
      </p>
    </section>
  )
}

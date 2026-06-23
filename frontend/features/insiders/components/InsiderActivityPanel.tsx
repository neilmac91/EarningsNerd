'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CircleNotchIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

import {
  getInsiderActivity,
  InsiderActivityResponse,
  InsiderTransaction,
} from '@/features/insiders/api/insiders-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtScale } from '@/lib/format'
import { directionText } from '@/lib/financialTone'

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

export default function InsiderActivityPanel({ ticker }: { ticker: string }) {
  const [windowDays, setWindowDays] = useState(90)
  const { data, isLoading, isError } = useQuery<InsiderActivityResponse>({
    queryKey: ['insiders', ticker, windowDays],
    queryFn: () => getInsiderActivity(ticker, windowDays),
    enabled: !!ticker,
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

  if (isError && !everHadData.current) return null
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
    <section className="mb-8 rounded-lg border border-border-light bg-panel-light p-6 shadow-sm dark:border-border-dark dark:bg-panel-dark">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider Activity</h2>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Select window">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              type="button"
              onClick={() => setWindowDays(w.days)}
              aria-pressed={w.days === windowDays}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                w.days === windowDays
                  ? 'bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                  : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && !hasTrades ? (
        <div className="flex h-48 items-center justify-center" aria-label="Loading insider activity">
          <CircleNotchIcon className="h-6 w-6 animate-spin text-brand-strong dark:text-brand-strong-dark" />
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
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border-light text-xs uppercase tracking-wide text-text-tertiary-light dark:border-border-dark dark:text-text-secondary-dark">
                  <th className="py-2 pr-3 font-medium">Insider</th>
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 text-right font-medium">Shares</th>
                  <th className="py-2 pr-3 text-right font-medium">Value</th>
                  <th className="py-2 text-right font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {data!.transactions.slice(0, MAX_ROWS).map((t, i) => {
                  const buy = isBuy(t)
                  return (
                    <tr
                      key={`${t.accession ?? ''}-${i}`}
                      className="border-b border-border-light last:border-0 dark:border-border-dark"
                    >
                      <td className="py-2 pr-3">
                        <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                          {t.insider_name ?? '—'}
                        </span>
                        <span className="block text-xs text-text-tertiary-light dark:text-text-secondary-dark">{roleOf(t)}</span>
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`font-medium ${directionText[buy ? 'up' : 'down']}`}>
                          {t.transaction_label ?? (buy ? 'Buy' : 'Sell')}
                        </span>
                        {t.is_10b5_1 && (
                          <span className="ml-1.5 rounded bg-background-light px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary-light dark:bg-white/5 dark:text-text-secondary-dark">
                            10b5-1
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
                        {fmtShares(t.shares)}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
                        {fmtMoney(t.value)}
                      </td>
                      <td className="py-2 text-right tabular-nums text-text-tertiary-light dark:text-text-secondary-dark">
                        {t.transaction_date ?? '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
        Open-market Form 4 trades from SEC EDGAR. 10b5-1 marks pre-scheduled trades (weaker signal).
      </p>
    </section>
  )
}

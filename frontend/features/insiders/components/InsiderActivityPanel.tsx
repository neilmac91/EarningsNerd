'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

import {
  getInsiderActivity,
  InsiderActivityResponse,
  InsiderTransaction,
} from '@/features/insiders/api/insiders-api'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtShares } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { Badge, Card, DataTable, MissingValue, SegmentedControl, Skeleton, type Column } from '@/components/ui'

const WINDOWS: { days: number; label: string }[] = [
  { days: 90, label: '90D' },
  { days: 180, label: '180D' },
  { days: 365, label: '1Y' },
]

const MAX_ROWS = 8

/** A dollar amount's size, compact ("$1.8M"); the panel states its direction beside it, in words or a sign. */
const fmtMoney = (n: number): string => fmtCurrency(Math.abs(n), { compact: true })

/** The insider's role: the filing's title for them, else the relationships it flags, else null, and the cell shows
 *  MissingValue read as "no role listed". Not "unavailable": with every flag false the filing names none of the
 *  three roles, and the words claim no more than the row lists. */
function roleOf(t: InsiderTransaction): string | null {
  if (t.insider_title) return t.insider_title
  const roles: string[] = []
  if (t.is_officer) roles.push('Officer')
  if (t.is_director) roles.push('Director')
  if (t.is_ten_pct_owner) roles.push('10% Owner')
  return roles.join(', ') || null
}

// 'A' (acquired) is a buy, 'D' (disposed) a sell; fall back to the label text.
function isBuy(t: InsiderTransaction): boolean {
  if (t.acquired_disposed) return t.acquired_disposed.toUpperCase() === 'A'
  return (t.transaction_label ?? '').toLowerCase().includes('buy')
}

// v2 DataTable columns: Shares/Value/Date are numeric (data face + tabular-nums,
// right-aligned); the Type cell tone carries buy/sell as gain/loss, with a ▲/▼ glyph
// and the label text ("Buy"/"Sell"), so color is never the sole cue. A trade's missing share count, value or
// date is MissingValue alone in its cell, read as "unavailable"; the summary never needs it, since the API always
// sends its share counts and a missing dollar value falls back to them. A missing name reads "name unavailable", so
// the cell never reads as the insider being unavailable: a Form 4 always names its reporting owner, so the name is
// one this read lacks.
const TRANSACTION_COLUMNS: Column<InsiderTransaction>[] = [
  {
    key: 'insider',
    header: 'Insider',
    render: (t) => (
      <>
        <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
          {t.insider_name ?? <MissingValue label="name unavailable" />}
        </span>
        <span className="block text-xs text-text-tertiary-light dark:text-text-secondary-dark">{roleOf(t) ?? <MissingValue label="no role listed" />}</span>
      </>
    ),
  },
  {
    key: 'type',
    header: 'Type',
    tone: (t) => (isBuy(t) ? 'gain' : 'loss'),
    render: (t) => (
      <>
        <span aria-hidden="true">{isBuy(t) ? '▲' : '▼'} </span>
        {t.transaction_label ?? (isBuy(t) ? 'Buy' : 'Sell')}
        {t.is_10b5_1 && (
          <Badge variant="neutral" icon={null} className="ml-1.5">
            10b5-1
          </Badge>
        )}
      </>
    ),
  },
  { key: 'shares', header: 'Shares', align: 'right', numeric: true, render: (t) => (t.shares == null ? <MissingValue /> : fmtShares(t.shares)) },
  { key: 'value', header: 'Value', align: 'right', numeric: true, render: (t) => (t.value == null ? <MissingValue /> : fmtMoney(t.value)) },
  { key: 'date', header: 'Date', align: 'right', numeric: true, render: (t) => t.transaction_date ?? <MissingValue /> },
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
    queryKey: queryKeys.insiders(ticker, windowDays),
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
      <Card as="section" className="mb-8 p-cap-6">
        <h2 className="mb-3 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider activity</h2>
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Insider (Form&nbsp;4) reporting is not generally required for foreign private issuers, so
          no open-market insider trades are available for this company.
        </p>
      </Card>
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
    <Card as="section" className="mb-8 p-cap-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider activity</h2>
        <SegmentedControl
          label="Time window"
          size="adaptive"
          fullWidth
          value={String(windowDays)}
          onChange={(v) => setWindowDays(Number(v))}
          options={WINDOWS.map((w) => ({ value: String(w.days), label: w.label, mono: true }))}
        />
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
          {/* Signal headline: the row wraps as a Notice's does (components/ui/Notice.tsx), so where the text cannot
              keep its 9rem beside the glyph it goes under it at the card's whole width. Each separator dot is held to
              the word before it by a no-break space, so a line never starts with one. */}
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <SignalIcon className={`h-7 w-7 shrink-0 ${signalColor}`} aria-hidden="true" />
            <div className="min-w-0 flex-[1_1_9rem]">
              <p className={`text-lg font-semibold ${signalColor}`}>
                {signalText}
                {direction !== 'flat' && <>&nbsp;· {signalMagnitude}</>}
              </p>
              {planSells > 0 && (
                <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                  Excludes {fmtShares(planSells)} shares sold under pre-scheduled 10b5-1 plans
                  {summary.discretionary_net_shares !== summary.net_shares && (
                    <>&nbsp;· discretionary net {fmtShares(summary.discretionary_net_shares, { signed: true })} shares</>
                  )}
                </p>
              )}
            </div>
          </div>

          {/* Buy / Sell / Net stats: equal tracks of at least 5.5rem, as many as fit, so the three tinted tiles keep
              one width whatever their figures say and stack when enlarged text leaves no room for three (a rem
              minimum grows with the text). A figure never breaks inside itself: at 320px under 200% text "$900.0K"
              broke as "$900.0" over "K", and with the card's capped inset (E120) a stacked tile holds it whole; a
              figure with a space ("+10.0K shares") still wraps at its space. The figures are in the data face
              (frontend/DESIGN_SYSTEM.md §3; lessons/frontend-variable-text-must-not-size-a-wrapping-row.md,
              lessons/frontend-check-brand-layouts-at-200-percent-text.md). */}
          <div className="mb-5 grid grid-cols-[repeat(auto-fit,minmax(min(5.5rem,100%),1fr))] gap-3">
            <div className="min-w-0 rounded-lg bg-gain-soft p-3 dark:bg-gain-soft-dark">
              <p className="text-xs font-medium text-gain-text dark:text-gain-dark">
                Buys ({summary.buy_count})
              </p>
              <p className="mt-0.5 font-data text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                {summary.buy_value != null ? fmtMoney(summary.buy_value) : `${fmtShares(summary.buy_shares)} sh`}
              </p>
            </div>
            <div className="min-w-0 rounded-lg bg-loss-soft p-3 dark:bg-loss-soft-dark">
              <p className="text-xs font-medium text-loss-text dark:text-loss-dark">
                Sells ({summary.sell_count})
              </p>
              <p className="mt-0.5 font-data text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                {summary.sell_value != null ? fmtMoney(summary.sell_value) : `${fmtShares(summary.sell_shares)} sh`}
              </p>
            </div>
            <div className="min-w-0 rounded-lg bg-background-light p-3 dark:bg-white/5">
              <p className="text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">Net</p>
              <p className={`mt-0.5 font-data text-sm font-semibold tabular-nums ${signalColor}`}>
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
        Open-market Form 4 trades from SEC EDGAR. 10b5-1 marks a trade scheduled in advance under a trading plan.
      </p>
    </Card>
  )
}

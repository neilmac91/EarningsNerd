'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import {
  getInsiderActivity,
  InsiderActivityResponse,
  InsiderTransaction,
} from '@/features/insiders/api/insiders-api'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { ApiError } from '@/lib/api/client'
import { fmtCurrency, fmtShares, formatLocalDate } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { ActivityLine, Badge, Card, DataTable, MissingValue, Notice, SegmentedControl, Skeleton, type Column } from '@/components/ui'

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
        <span className="block text-xs text-text-tertiary-light dark:text-text-tertiary-dark">{roleOf(t) ?? <MissingValue label="no role listed" />}</span>
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

/** A scan under way says when asking again can show more (`scan.retry_after_seconds`). The panel asks again then, never
 *  sooner than this floor, and for at most POLL_LIMIT_MS from its first request for the ticker, so a scan that is slow
 *  or paused does not keep a page open asking for good (ADR 0009, decision 7). */
const POLL_FLOOR_MS = 5_000
const POLL_LIMIT_MS = 3 * 60_000

/** 401 (signed out), 403 (not a beta account) and 404 (the endpoint switched off, or a company it does not know): the
 *  panel is not for this reader here, so it renders nothing rather than an error. */
const isRefusal = (error: unknown): boolean => error instanceof ApiError && [401, 403, 404].includes(error.status)

const STATUS_TEXT = 'text-sm text-text-secondary-light dark:text-text-secondary-dark'

/** What the stored scan behind an answer says of itself, in words: null once it is complete. The words carry the state,
 *  never a colour; the panel's status region announces them as they change, so they hold no count: the count moves
 *  with every answer and is the bar's to say (ScanProgress). Once the panel has stopped asking (`stopped`), a scan
 *  still reading says so and how to see more, since the words would otherwise stand still as if nothing were left. */
function scanLine(data: InsiderActivityResponse, stopped: boolean): ReactNode {
  const { scan } = data
  if (scan.status === 'complete') return null
  if (scan.status === 'failed') return <p className={STATUS_TEXT}>Insider activity is unavailable for this company right now.</p>
  const reach = data.total_transactions > 0 ? formatLocalDate(scan.oldest_filed_date, 'MMM d, yyyy') : ''
  const soFar = reach ? ` Trades shown so far go back to filings from ${reach}.` : ''
  if (scan.status === 'paused') {
    return <p className={STATUS_TEXT}>Reading this company’s Form&nbsp;4 filings is paused and resumes on its own.{soFar}</p>
  }
  if (stopped) {
    return <p className={STATUS_TEXT}>Reading continues in the background. Reload the page to see more.{soFar}</p>
  }
  // A run that reports how far it has got shows a bar, and one that does not yet is the Activity line
  // (frontend/DESIGN_SYSTEM.md §4 › Activity line): nothing is listed on a company's first visit.
  if (scan.filings_listed === 0) return <ActivityLine>Reading this company’s recent Form&nbsp;4 filings.</ActivityLine>
  return <p className={STATUS_TEXT}>Reading this company’s recent Form&nbsp;4 filings.{soFar}</p>
}

/** How far a scan under way has got: the count in words and a bar, as the summary's generating card draws its own
 *  (app/filing/[id]/StreamingSummaryDisplay.tsx). Outside the status region, so each answer's new count is not read
 *  out; the bar carries it for a reader who asks. */
function ScanProgress({ scan }: { scan: InsiderActivityResponse['scan'] }) {
  if (scan.filings_listed === 0 || (scan.status !== 'scanning' && scan.status !== 'paused')) return null
  return (
    <div className="mb-4">
      <p className="font-data text-xs tabular-nums text-text-tertiary-light dark:text-text-tertiary-dark">
        {scan.filings_read} of {scan.filings_listed} filings read
      </p>
      <div
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-border-light dark:bg-white/10"
        role="progressbar"
        aria-label="Form 4 filings read"
        aria-valuemin={0}
        aria-valuemax={scan.filings_listed}
        aria-valuenow={scan.filings_read}
      >
        <div
          className="h-full rounded-full bg-brand-strong transition-[width] duration-slow ease-standard motion-reduce:transition-none dark:bg-brand-dark"
          style={{ width: `${Math.round((scan.filings_read / scan.filings_listed) * 100)}%` }}
        />
      </div>
    </div>
  )
}

export default function InsiderActivityPanel({
  ticker,
  isFpi,
}: {
  ticker: string
  isFpi?: boolean
}) {
  const [windowDays, setWindowDays] = useState(90)
  const headingRef = useRef<HTMLHeadingElement>(null)
  // The current reader, from the page's own read of /me (the same query, so no request of its own). Only a beta
  // account may ask (the endpoint answers 401 signed out and 403 to any other account): signed out, still loading
  // or not beta, the panel asks nothing and renders nothing.
  const { data: currentUser } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isBeta = currentUser?.is_beta === true
  // When this mount first asked for this ticker: the polling's three minutes run from it, whatever the window.
  const pollFrom = useRef<{ ticker: string; at: number } | null>(null)
  const insidersKey = queryKeys.insiders.byWindow(ticker, windowDays)
  const query = useQuery<InsiderActivityResponse>({
    queryKey: insidersKey,
    queryFn: () => {
      if (pollFrom.current?.ticker !== ticker) pollFrom.current = { ticker, at: Date.now() }
      return getInsiderActivity(ticker, windowDays)
    },
    // Foreign private issuers don't file Form 4s, so they are never asked about. While filings are still loading
    // isFpi is undefined, so the query waits until the company is known not to be one (isFpi === false).
    enabled: !!ticker && isFpi === false && isBeta,
    // A failed read waits for the reader's Try again.
    retry: false,
    // The endpoint answers from the stored scan, at once; a scan under way is followed by the polling below.
    staleTime: 5 * 60 * 1000,
    refetchInterval: (q) => {
      const wait = q.state.data?.scan.retry_after_seconds
      const from = pollFrom.current
      if (q.state.status === 'error' || wait == null || from?.ticker !== ticker) return false
      const delay = Math.max(wait * 1000, POLL_FLOOR_MS)
      return Date.now() + delay - from.at <= POLL_LIMIT_MS ? delay : false
    },
  })
  const { data } = query
  const failure = useRetainedFailure(query, insidersKey)
  // The ticker whose three minutes are up: from then the panel asks nothing more by itself, and says so.
  const [stoppedFor, setStoppedFor] = useState<string | null>(null)
  const pending = data?.scan.retry_after_seconds != null && !failure.failed
  useEffect(() => {
    const from = pollFrom.current
    if (!pending || from?.ticker !== ticker) return
    const timer = setTimeout(() => setStoppedFor(ticker), Math.max(0, from.at + POLL_LIMIT_MS - Date.now()))
    return () => clearTimeout(timer)
  }, [pending, ticker, data])

  if (!isBeta) return null

  // Foreign private issuers (20-F/6-K filers) are generally exempt from Section 16 insider
  // reporting, so there are no Form 4s to show. Render an honest note instead of an empty/absent
  // panel (the query is disabled for FPIs via `enabled` above).
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
  // Not known yet whether the company is a foreign private issuer: nothing is asked, and nothing shows.
  if (isFpi !== false) return null
  if (failure.failed && isRefusal(failure.error)) return null

  const summary = data?.summary
  const hasTrades = !!data && data.total_transactions > 0
  const statusLine = data ? scanLine(data, stoppedFor === ticker) : null
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
        <h2 ref={headingRef} tabIndex={-1} className="text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark">
          Insider activity
        </h2>
        <SegmentedControl
          label="Time window"
          size="adaptive"
          fullWidth
          value={String(windowDays)}
          onChange={(v) => setWindowDays(Number(v))}
          options={WINDOWS.map((w) => ({ value: String(w.days), label: w.label, mono: true }))}
        />
      </div>

      {/* The scan's progress, in a status region mounted from the first render, so the words it gains are heard. */}
      <div role="status" className={statusLine ? 'mb-4' : undefined}>
        {statusLine}
      </div>
      {data && <ScanProgress scan={data.scan} />}

      {failure.failed && (
        <div className="mb-4">
          <Notice
            variant="error"
            title="Couldn’t load insider activity"
            description="The rest of this page is unaffected."
            action={<RetryButton size="sm" failures={[failure]} focusTarget={headingRef} />}
          />
        </div>
      )}

      {!data ? (
        !failure.failed && (
          <div role="status" aria-label="Loading insider activity">
            <Skeleton className="h-48 w-full rounded-lg" />
            <span className="sr-only">Loading…</span>
          </div>
        )
      ) : !hasTrades || !summary ? (
        // Only a complete scan has read everything there is: until then the status line above says how far it got.
        data.scan.status === 'complete' && (
          <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
            No open-market insider trades in the last {windowDays} days.
          </p>
        )
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
                <p className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
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
            <div className="min-w-0 rounded-lg bg-background-light p-3 dark:bg-background-dark">
              <p className="text-xs font-medium text-gain-text dark:text-gain-dark">
                Buys ({summary.buy_count})
              </p>
              <p className="mt-0.5 font-data text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
                {summary.buy_value != null ? fmtMoney(summary.buy_value) : `${fmtShares(summary.buy_shares)} sh`}
              </p>
            </div>
            <div className="min-w-0 rounded-lg bg-background-light p-3 dark:bg-background-dark">
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
            rows={data.transactions.slice(0, MAX_ROWS)}
            rowKey={(t, i) => `${t.accession ?? ''}-${i}`}
            caption="Recent open-market insider transactions: insider, type, shares, value, and date"
          />
        </>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
        Open-market Form 4 trades from SEC EDGAR. 10b5-1 marks a trade scheduled in advance under a trading plan.
      </p>
    </Card>
  )
}

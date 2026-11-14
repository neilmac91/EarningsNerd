'use client'

import { useRef, useState, type ReactNode } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

import type { InsiderActivityResponse, InsiderTransaction } from '@/features/insiders/api/insiders-api'
import { insiderSignal, useInsiderActivity } from '@/features/insiders/hooks/useInsiderActivity'
import { RetryButton } from '@/hooks/useRetainedFailure'
import { fmtCurrency, fmtShares, formatLocalDate } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { ActivityLine, Badge, Card, DataTable, MissingValue, Notice, SegmentedControl, Skeleton, type Column } from '@/components/ui'

const WINDOWS: { days: number; label: string }[] = [
  { days: 90, label: '90D' },
  { days: 180, label: '180D' },
  { days: 365, label: '1Y' },
]

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

const STATUS_TEXT = 'text-sm text-text-secondary-light dark:text-text-secondary-dark'

/** What the stored scan behind an answer says of itself, in words: null once it is complete. The words carry the state,
 *  never a colour; the panel's status region announces them when they change, so they hold nothing that moves with
 *  each answer: the count and the date the filings reach back to are the bar's to say (ScanProgress). Once the panel
 *  has stopped asking (`stopped`), the words say how to see more, since they would otherwise stand still as if
 *  nothing were left. */
function scanLine(scan: InsiderActivityResponse['scan'], stopped: boolean): ReactNode {
  if (scan.status === 'complete') return null
  if (scan.status === 'failed') return <p className={STATUS_TEXT}>Insider activity is unavailable for this company right now.</p>
  if (scan.status === 'paused') {
    return (
      <p className={STATUS_TEXT}>
        Reading this company’s Form&nbsp;4 filings is paused and resumes on its own.{stopped && ' Reload the page later to see more.'}
      </p>
    )
  }
  if (stopped) return <p className={STATUS_TEXT}>Reading continues in the background. Reload the page to see more.</p>
  // A run that reports how far it has got shows a bar, and one that does not yet is the Activity line
  // (frontend/DESIGN_SYSTEM.md §4 › Activity line): nothing is listed on a company's first visit.
  if (scan.filings_listed === 0) return <ActivityLine>Reading this company’s recent Form&nbsp;4 filings.</ActivityLine>
  return <p className={STATUS_TEXT}>Reading this company’s recent Form&nbsp;4 filings.</p>
}

/** How far a scan under way has got: the count in words and a bar, as the summary's generating card draws its own
 *  (app/filing/[id]/StreamingSummaryDisplay.tsx). Outside the status region, so each answer's new count is not read
 *  out; the bar carries it for a reader who asks. */
function ScanProgress({ scan }: { scan: InsiderActivityResponse['scan'] }) {
  if (scan.filings_listed === 0 || (scan.status !== 'scanning' && scan.status !== 'paused')) return null
  // The earliest filing read so far, whatever the window: how far back the scan has got, not how far the trades
  // shown reach.
  const reach = formatLocalDate(scan.oldest_filed_date, 'MMM d, yyyy')
  return (
    <div className="mb-4">
      <p className="font-data text-xs tabular-nums text-text-tertiary-light dark:text-text-tertiary-dark">
        {scan.filings_read} of {scan.filings_listed} filings read{reach && `, back to ${reach}`}
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

/**
 * A company's insider (Form 4) activity in full, on its own page (/company/{ticker}/insiders): the window control, the
 * net signal, the buy, sell and net tiles and every trade the answer carries, newest first. The company page shows the
 * same read as a compact card that links here (InsiderActivityCard), so its filings keep the page. Only a beta account
 * asks (useInsiderActivity); for any other reader the panel renders nothing and its page says who it is for.
 */
export default function InsiderActivityPanel({
  ticker,
  isFpi,
}: {
  ticker: string
  isFpi?: boolean
}) {
  const [windowDays, setWindowDays] = useState(90)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const { isBeta, data, failure, refused, stopped } = useInsiderActivity(ticker, windowDays, isFpi)

  if (!isBeta) return null

  // Foreign private issuers (20-F/6-K filers) are generally exempt from Section 16 insider
  // reporting, so there are no Form 4s to show. Render an honest note instead of an empty/absent
  // panel (the query is disabled for FPIs via `enabled` above).
  if (isFpi) {
    return (
      <Card as="section" className="p-cap-6">
        <h2 className="mb-3 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Insider activity</h2>
        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Insider (Form&nbsp;4) reporting is not generally required for foreign private issuers, so
          no open-market insider trades are available for this company.
        </p>
      </Card>
    )
  }
  // From here the card stands for a beta account, whatever the read says: bones while the company's filings or the
  // first answer are still loading (nothing is asked until the company is known not to be a foreign private
  // issuer), and a plain line where the endpoint has no answer for this company (a refusal, not a failure).

  const summary = data?.summary
  const hasTrades = !!data && data.total_transactions > 0
  const statusLine = data ? scanLine(data.scan, stopped) : null
  // Lead with net value when known, else net shares. The sign is the buy/sell signal.
  const { value: signalValue, isValue: signalIsValue, direction } = insiderSignal(summary)
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
    <Card as="section" className="p-cap-6">
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

      {/* The scan's state in words. The region is mounted with the card, so a change of its words (reading, paused,
          stopped, gone once complete) is heard; the words it is created with are read in place, as the card's are. */}
      <div role="status" className={statusLine ? 'mb-4' : undefined}>
        {statusLine}
      </div>
      {data && <ScanProgress scan={data.scan} />}

      {refused && (
        <p className="py-12 text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
          No insider activity is available for this company.
        </p>
      )}
      {failure.failed && !refused && (
        <div className="mb-4">
          <Notice
            variant="error"
            title="Couldn’t load insider activity"
            description="Try again in a moment."
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

          {/* Every trade the answer carries, newest first. The endpoint sends the most recent of a window's trades,
              so where the window holds more, a line under the table says how many of them these are. */}
          <DataTable
            columns={TRANSACTION_COLUMNS}
            rows={data.transactions}
            rowKey={(t, i) => `${t.accession ?? ''}-${i}`}
            caption="Recent open-market insider transactions: insider, type, shares, value, and date"
          />
          {data.total_transactions > data.transactions.length && (
            <p className="mt-3 text-xs tnum text-text-tertiary-light dark:text-text-tertiary-dark">
              The {data.transactions.length} most recent of {data.total_transactions} trades in this window. The totals
              above count them all.
            </p>
          )}
        </>
      )}

      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
        Open-market Form 4 trades from SEC EDGAR. 10b5-1 marks a trade scheduled in advance under a trading plan.
      </p>
    </Card>
  )
}

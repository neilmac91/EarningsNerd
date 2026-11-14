'use client'

import Link from 'next/link'
import { useId, useMemo, useRef, type ReactElement, type ReactNode, type RefObject } from 'react'

import { ActivityLine, Card, Notice, TrailingArrowLabel, cx } from '@/components/ui'
import { insiderSignal, useInsiderActivity } from '@/features/insiders/hooks/useInsiderActivity'
import { RetryButton } from '@/hooks/useRetainedFailure'
import { directionText } from '@/lib/financialTone'
import { fmtCurrency, fmtShares } from '@/lib/format'

/** The card's one window. The company's insider page offers the others. */
const WINDOW_DAYS = 90

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'

const fmtMoney = (n: number): string => fmtCurrency(Math.abs(n), { compact: true })
const trades = (n: number): string => `${n} ${n === 1 ? 'trade' : 'trades'}`

/** One side of the window, buys or sells: its size in the data face (dollars where every trade has a value, else
 *  shares) and how many trades made it; "None" where there were none, never a zero dressed as a figure. */
function Side({ count, value, shares }: { count: number; value: number | null; shares: number }) {
  if (count === 0) return <span className={cx('shrink-0', MUTED)}>None</span>
  return (
    <span className="flex shrink-0 items-baseline gap-2">
      <span className={cx('font-data font-semibold tabular-nums', INK)}>
        {value != null ? fmtMoney(value) : `${fmtShares(shares)} sh`}
      </span>
      <span className={cx('text-xs tnum', MUTED)}>{trades(count)}</span>
    </span>
  )
}

/** The company's insider page, where the card's read is shown in full. */
export const insidersHref = (ticker: string): string => `/company/${encodeURIComponent(ticker)}/insiders`

/**
 * Insider activity on the company page: a card in the side column, under Compare periods, so the filings keep the
 * page. It says the last 90 days in three lines (the net signal, buys, sells) and links to the company's insider
 * page, which holds the windows and the trades. The same read and query key as that page (useInsiderActivity), so
 * following the link renders it from cache.
 *
 * It wraps what the page lays out around it and hands that the card, or null: the page mounts it above its filings
 * grid, so the page knows whether there is a card before it opens the side column for one. There is a card only
 * once there is something to show: for a beta account, on a company known not to be a foreign private issuer
 * (`isFpi` is undefined until the filings say, and nothing is asked until then), with the endpoint's first answer or
 * a failure a retry can help. So a reader the endpoint refuses never sees a card appear and go, the backend's switch
 * hides the card when it is off (ADR 0009, decision 7), and the side column never stands empty. What the card then
 * says: the scan's own words while Form 4 filings are still being read, a plain line where the window holds no
 * trades, and a Notice with Try again on a failure, over the answer it already has. The page keys it by ticker, so
 * the read's three minutes of polling start again for another company.
 */
export function InsiderActivityCard({
  ticker,
  isFpi,
  focusFallback,
  children,
}: {
  ticker: string
  isFpi: boolean | undefined
  /** Where the card's Try again hands focus if the card itself leaves: a retry the endpoint refuses takes the card
   *  away, heading and all. The page gives its filings heading. */
  focusFallback: RefObject<HTMLElement | null>
  children: (card: ReactElement | null) => ReactNode
}) {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  // The card's heading while the card stands, the page's fallback once it has gone. Resolved after the commit.
  const retryTarget = useMemo(() => ({
    get current() { return headingRef.current ?? focusFallback.current },
  }), [focusFallback])
  const { isBeta, data, failure, refused, stopped, hasContent } = useInsiderActivity(ticker, WINDOW_DAYS, isFpi)
  if (!isBeta || isFpi !== false || !hasContent) return children(null)

  const summary = data?.summary
  const scan = data?.scan
  const hasTrades = !!data && data.total_transactions > 0 && !!summary
  const { value, isValue, direction } = insiderSignal(summary)
  const ink = directionText[direction === 'buy' ? 'up' : direction === 'sell' ? 'down' : 'flat']
  const size = isValue ? fmtMoney(value) : `${fmtShares(value)} shares`
  const reading = scan?.status === 'scanning' || scan?.status === 'paused'

  // The scan's state in words, as the insider page says it; null once every listed filing is read.
  const scanWords = !scan
    ? null
    : scan.status === 'failed'
      ? 'Insider activity is unavailable for this company right now.'
      : scan.status === 'paused'
        ? `Reading Form\u00a04 filings is paused and resumes on its own.${stopped ? ' Reload the page later to see more.' : ''}`
        : scan.status === 'scanning'
          ? stopped
            ? 'Reading continues in the background. Reload the page to see more.'
            : 'Reading recent Form\u00a04 filings.'
          : null

  return children(
    <Card as="aside" aria-labelledby={headingId} className="p-cap-5">
      <h2 id={headingId} ref={headingRef} tabIndex={-1} className={cx('text-lg font-semibold outline-none', INK)}>
        Insider activity
      </h2>
      <p className={cx('mt-1 font-data text-xs tabular-nums', MUTED)}>Form 4 · last {WINDOW_DAYS} days</p>

      {failure.failed && !refused && (
        <div className="mt-4">
          <Notice
            variant="error"
            title="Couldn’t load insider activity"
            description="The rest of this page is unaffected."
            action={<RetryButton size="sm" failures={[failure]} focusTarget={retryTarget} />}
          />
        </div>
      )}
      {data && (
        <>
          {/* The scan's state in words. The region is mounted with the answer, so a change of its words (reading,
              paused, stopped, gone once complete) is heard. It holds no count: the insider page's bar carries that. */}
          <div role="status" className={scanWords ? 'mt-4' : undefined}>
            {scanWords &&
              (scan?.status === 'scanning' && scan.filings_listed === 0 && !stopped ? (
                <ActivityLine>{scanWords}</ActivityLine>
              ) : (
                <p className={cx('text-sm', MUTED)}>{scanWords}</p>
              ))}
          </div>

          {hasTrades && summary ? (
            <ul role="list" className={cx('mt-4 border-t text-sm', HAIRLINE)}>
              {/* The net signal: its direction in words and a glyph beside its ink, never the colour alone. */}
              <li className={cx('flex items-baseline justify-between gap-3 border-b py-2.5', HAIRLINE)}>
                <span className={cx('min-w-0', INK)}>
                  {direction === 'buy' ? 'Net buying' : direction === 'sell' ? 'Net selling' : 'Buying and selling balanced'}
                </span>
                {direction !== 'flat' && (
                  <span className={cx('shrink-0 font-data font-semibold tabular-nums', ink)}>
                    <span aria-hidden="true">{direction === 'buy' ? '▲' : '▼'} </span>
                    {size}
                  </span>
                )}
              </li>
              <li className={cx('flex items-baseline justify-between gap-3 border-b py-2.5', HAIRLINE)}>
                <span className={cx('min-w-0', INK)}>Buys</span>
                <Side count={summary.buy_count} value={summary.buy_value} shares={summary.buy_shares} />
              </li>
              <li className={cx('flex items-baseline justify-between gap-3 border-b py-2.5', HAIRLINE)}>
                <span className={cx('min-w-0', INK)}>Sells</span>
                <Side count={summary.sell_count} value={summary.sell_value} shares={summary.sell_shares} />
              </li>
            </ul>
          ) : (
            // Only a complete scan has read everything there is: until then the words above say it is still reading.
            !reading &&
            scan?.status !== 'failed' && (
              <p className={cx('mt-4 text-sm', MUTED)}>No open-market insider trades in the last {WINDOW_DAYS} days.</p>
            )
          )}

          {/* A link that stands alone: one box that grows with its lines where its label wraps under 200% text
              (min-h-9, not h-9), its arrow kept with its last word (DESIGN_SYSTEM.md §4, Trailing arrow). */}
          <Link
            href={insidersHref(ticker)}
            className={cx(
              '-ml-2 mt-3 inline-block min-h-9 rounded-lg px-2 py-2 text-sm font-semibold',
              'text-brand-strong transition-colors duration-fast hover:bg-brand-weak',
              'focus-visible:outline-none focus-visible:shadow-ring-brand',
              'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark',
            )}
          >
            <TrailingArrowLabel arrowClassName="ml-1.5 h-4 w-4">Open insider activity</TrailingArrowLabel>
          </Link>
        </>
      )}
    </Card>,
  )
}

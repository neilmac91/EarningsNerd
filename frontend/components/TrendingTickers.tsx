'use client'

import { queryKeys } from '@/lib/queryKeys'
import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowsClockwiseIcon, EyeIcon, FlameIcon, MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import clsx from 'clsx'
import { formatDistanceToNowStrict } from 'date-fns'
import posthog from 'posthog-js'

import {
  getTrendingTickers,
  refreshTickerPrices,
  TrendingTicker,
  TrendingTickerResponse,
  PriceData,
} from '@/features/companies/api/companies-api'
import { directionText, directionOf } from '@/lib/financialTone'
import CompanyLogo from '@/components/CompanyLogo'
import { Button, GuidanceCard, Skeleton } from '@/components/ui'

const FULL_REFRESH_INTERVAL = 10 * 60 * 1000 // 10 minutes for full data
const PRICE_REFRESH_INTERVAL = 2 * 60 * 1000 // 2 minutes for prices only
const DEFAULT_EMPTY_MESSAGE = 'Trending data is temporarily unavailable. Please check back soon.'

const formatPrice = (price?: number | null): string | null => {
  if (price === null || price === undefined) {
    return null
  }
  return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const formatChangePercent = (change?: number | null): string | null => {
  if (change === null || change === undefined) {
    return null
  }
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}%`
}

const formatWatchlistCount = (count?: number | null): string | null => {
  if (count === null || count === undefined) {
    return null
  }

  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1)}M`
  }
  if (count >= 1_000) {
    return `${(count / 1_000).toFixed(1)}K`
  }
  return count.toLocaleString()
}

function PriceChangeIndicator({ changePercent }: { changePercent?: number | null }) {
  if (changePercent === null || changePercent === undefined) {
    return null
  }

  const isPositive = changePercent > 0
  const isNegative = changePercent < 0
  const iconClass = 'h-3 w-3'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-0.5 text-sm font-medium',
        directionText[directionOf(changePercent)]
      )}
    >
      {isPositive && <TrendUpIcon className={iconClass} />}
      {isNegative && <TrendDownIcon className={iconClass} />}
      {!isPositive && !isNegative && <MinusIcon className={iconClass} />}
      <span className="tabular-nums">{formatChangePercent(changePercent)}</span>
    </span>
  )
}

function TrendingTickerCard({
  ticker,
  priceOverride,
}: {
  ticker: TrendingTicker
  priceOverride?: PriceData
}) {
  // Use price override if available (from 2-min refresh), otherwise use original
  const price = priceOverride?.price ?? ticker.price
  const changePercent = priceOverride?.change_percent ?? ticker.change_percent

  const watchlistFormatted = formatWatchlistCount(ticker.watchlist_count)
  const priceFormatted = formatPrice(price)

  const handleClick = useCallback(() => {
    posthog.capture('market_mover_clicked', {
      symbol: ticker.symbol,
      price: price,
      change_percent: changePercent,
      watchlist_count: ticker.watchlist_count,
      source: 'stocktwits',
    })
  }, [ticker.symbol, price, changePercent, ticker.watchlist_count])

  return (
    <Link
      href={`/company/${ticker.symbol}`}
      onClick={handleClick}
      className="flex min-w-[240px] flex-col gap-2 rounded-2xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 p-4 shadow-e2 dark:shadow-none transition duration-base hover:-translate-y-1 motion-reduce:hover:translate-y-0 hover:bg-white dark:hover:bg-white/10 hover:shadow-e2 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark "
    >
      {/* Header: Logo + Symbol + Price */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <CompanyLogo ticker={ticker.symbol} name={ticker.name} size={32} />
          <div className="min-w-0">
            <div className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">{ticker.symbol}</div>
            <div className="truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {ticker.name ?? 'Loading...'}
            </div>
          </div>
        </div>
        {priceFormatted && (
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">{priceFormatted}</div>
            <PriceChangeIndicator changePercent={changePercent} />
          </div>
        )}
      </div>

      {/* Footer: Watchlist count */}
      {watchlistFormatted && (
        <div className="flex items-center gap-1.5 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          <EyeIcon className="h-3.5 w-3.5" />
          <span>{watchlistFormatted} watching</span>
        </div>
      )}
    </Link>
  )
}

export default function TrendingTickers({
  initialData,
}: {
  // Server-fetched payload (ISR) so the first paint shows real tickers
  // instead of skeletons; the client query keeps refreshing as before.
  initialData?: TrendingTickerResponse
} = {}) {
  const [priceOverrides, setPriceOverrides] = useState<Record<string, PriceData>>({})

  // Main query for full trending data (10 min interval)
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: queryKeys.trendingTickers(),
    queryFn: getTrendingTickers,
    initialData,
    staleTime: FULL_REFRESH_INTERVAL,
    refetchInterval: FULL_REFRESH_INTERVAL,
    retry: 1,
  })

  // 2-minute price refresh
  useEffect(() => {
    if (!data?.tickers?.length) return

    const symbols = data.tickers.map((t) => t.symbol)

    const refreshPrices = async () => {
      try {
        const response = await refreshTickerPrices(symbols)
        setPriceOverrides(response.prices)
      } catch (err) {
        // Silently fail price refresh - not critical
        console.debug('Price refresh failed:', err)
      }
    }

    // Initial price refresh after main data loads
    const initialTimeout = setTimeout(refreshPrices, 5000)

    // Set up 2-minute interval
    const interval = setInterval(refreshPrices, PRICE_REFRESH_INTERVAL)

    return () => {
      clearTimeout(initialTimeout)
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.tickers?.map((t) => t.symbol).join(',')])

  // Clear price overrides when main data refreshes
  useEffect(() => {
    if (data?.timestamp) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- resets local price overrides when upstream data refreshes (new timestamp); deliberate sync to external query state
      setPriceOverrides({})
    }
  }, [data?.timestamp])

  const hasTickers = Boolean(data?.tickers?.length)
  // eslint-disable-next-line react-hooks/preserve-manual-memoization -- intentional: recompute only when data?.timestamp changes, not on every data identity change
  const updatedAgo = useMemo(() => {
    if (!data?.timestamp) {
      return null
    }

    try {
      return formatDistanceToNowStrict(new Date(data.timestamp), { addSuffix: true })
    } catch {
      return null
    }
  }, [data?.timestamp])

  if (isLoading) {
    return (
      <section className="mt-12">
        <header className="mb-4 flex items-center justify-between gap-3 text-text-primary-light dark:text-text-primary-dark">
          <div className="flex items-center gap-2">
            <FlameIcon className="h-5 w-5 text-warning-light dark:text-warning-dark" />
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Market Movers</h2>
          </div>
        </header>
        <div role="status" aria-label="Loading market movers" className="flex gap-4 overflow-x-auto pb-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-28 min-w-[240px] rounded-2xl" />
          ))}
          <span className="sr-only">Loading market movers…</span>
        </div>
      </section>
    )
  }

  if (isError) {
    return (
      <section className="mt-12">
        <header className="mb-3 flex items-center gap-2 text-text-primary-light dark:text-text-primary-dark">
          <FlameIcon className="h-5 w-5 text-warning-light dark:text-warning-dark" />
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Market Movers</h2>
        </header>
        <GuidanceCard
          variant="error"
          title="Unable to load trending data"
          description={error instanceof Error ? error.message : 'Please try again soon.'}
        />
      </section>
    )
  }

  let infoTone = 'border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none text-text-secondary-light dark:text-text-secondary-dark'
  if (data?.status === 'stale') {
    infoTone = 'border-warning-light/40 dark:border-warning-dark/40 bg-warning-light/10 dark:bg-warning-dark/10 text-warning-light dark:text-warning-dark'
  } else if (data?.status === 'unavailable') {
    infoTone = 'border-error-light/40 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/10 text-error-light dark:text-error-dark'
  }
  const showInfoMessage = Boolean(data?.message)
  const emptyStateMessage = data?.message ?? DEFAULT_EMPTY_MESSAGE

  return (
    <section className="mt-12">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 text-text-primary-light dark:text-text-primary-dark">
        <div className="flex items-center gap-2">
          <FlameIcon className="h-5 w-5 text-warning-light dark:text-warning-dark" />
          <div>
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Market Movers</h2>
            <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
              What&apos;s moving in the market today
              {updatedAgo && <span className="text-text-tertiary-light dark:text-text-secondary-dark"> • Updated {updatedAgo}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data?.source && (
            <span className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
              Source: {data.source}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            loading={isFetching}
            leftIcon={<ArrowsClockwiseIcon className="h-4 w-4" />}
          >
            Refresh
          </Button>
        </div>
      </header>

      {showInfoMessage && (
        <div className={clsx('mb-4 rounded-xl border px-4 py-3 text-sm', infoTone)}>
          {data?.message}
        </div>
      )}

      {hasTickers ? (
        <>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {data?.tickers.map((ticker) => (
              <TrendingTickerCard
                key={ticker.symbol}
                ticker={ticker}
                priceOverride={priceOverrides[ticker.symbol]}
              />
            ))}
          </div>

          {/* Subtle footer attribution */}
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            <span>Data from</span>
            <a
              href="https://stocktwits.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
            >
              Stocktwits
            </a>
            <span>&</span>
            <a
              href="https://financialmodelingprep.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
            >
              FMP
            </a>
          </div>
        </>
      ) : (
        <GuidanceCard variant="empty" title="No market movers right now" description={emptyStateMessage} />
      )}
    </section>
  )
}

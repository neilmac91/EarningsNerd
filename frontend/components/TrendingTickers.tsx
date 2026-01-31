'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Flame, RefreshCw, TrendingUp, TrendingDown, Minus, Eye } from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNowStrict } from 'date-fns'
import posthog from 'posthog-js'

import {
  getTrendingTickers,
  refreshTickerPrices,
  TrendingTicker,
  PriceData,
} from '@/features/companies/api/companies-api'

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
        isPositive && 'text-emerald-400',
        isNegative && 'text-rose-400',
        !isPositive && !isNegative && 'text-slate-400'
      )}
    >
      {isPositive && <TrendingUp className={iconClass} />}
      {isNegative && <TrendingDown className={iconClass} />}
      {!isPositive && !isNegative && <Minus className={iconClass} />}
      <span>{formatChangePercent(changePercent)}</span>
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
  const change = priceOverride?.change ?? ticker.change
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
      className="flex min-w-[240px] flex-col gap-2 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg transition-all duration-200 hover:-translate-y-1 hover:bg-white/10 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
    >
      {/* Header: Symbol + Price */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold text-white">{ticker.symbol}</div>
          <div className="truncate text-sm text-slate-300">
            {ticker.name ?? 'Loading...'}
          </div>
        </div>
        {priceFormatted && (
          <div className="text-right">
            <div className="text-lg font-semibold text-white">{priceFormatted}</div>
            <PriceChangeIndicator changePercent={changePercent} />
          </div>
        )}
      </div>

      {/* Footer: Watchlist count */}
      {watchlistFormatted && (
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <Eye className="h-3.5 w-3.5" />
          <span>{watchlistFormatted} watching</span>
        </div>
      )}
    </Link>
  )
}

export default function TrendingTickers() {
  const queryClient = useQueryClient()
  const [priceOverrides, setPriceOverrides] = useState<Record<string, PriceData>>({})

  // Main query for full trending data (10 min interval)
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['trending-tickers'],
    queryFn: getTrendingTickers,
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
  }, [data?.tickers])

  // Clear price overrides when main data refreshes
  useEffect(() => {
    if (data?.timestamp) {
      setPriceOverrides({})
    }
  }, [data?.timestamp])

  const hasTickers = Boolean(data?.tickers?.length)
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
        <header className="mb-4 flex items-center justify-between gap-3 text-white">
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-300" />
            <h2 className="text-lg font-semibold">Market Movers</h2>
          </div>
        </header>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="flex min-w-[240px] flex-col gap-3 rounded-2xl border border-white/5 bg-white/5 p-4"
            >
              <div className="flex justify-between">
                <div className="space-y-2">
                  <div className="h-6 w-16 animate-pulse rounded bg-white/10" />
                  <div className="h-4 w-28 animate-pulse rounded bg-white/10" />
                </div>
                <div className="space-y-2 text-right">
                  <div className="h-6 w-20 animate-pulse rounded bg-white/10" />
                  <div className="h-4 w-14 animate-pulse rounded bg-white/10" />
                </div>
              </div>
              <div className="h-4 w-24 animate-pulse rounded bg-white/10" />
            </div>
          ))}
        </div>
      </section>
    )
  }

  if (isError) {
    return (
      <section className="mt-12">
        <header className="mb-3 flex items-center gap-2 text-white">
          <Flame className="h-5 w-5 text-orange-300" />
          <h2 className="text-lg font-semibold">Market Movers</h2>
        </header>
        <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          Unable to load trending data. Please try again soon.
          {error instanceof Error && (
            <span className="mt-2 block text-xs text-rose-300/80">{error.message}</span>
          )}
        </div>
      </section>
    )
  }

  let infoTone = 'border-slate-500/40 bg-slate-500/10 text-slate-200'
  if (data?.status === 'stale') {
    infoTone = 'border-amber-400/40 bg-amber-500/10 text-amber-100'
  } else if (data?.status === 'unavailable') {
    infoTone = 'border-rose-400/40 bg-rose-500/10 text-rose-200'
  }
  const showInfoMessage = Boolean(data?.message)
  const emptyStateMessage = data?.message ?? DEFAULT_EMPTY_MESSAGE

  return (
    <section className="mt-12">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 text-white">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-300" />
          <div>
            <h2 className="text-lg font-semibold">Market Movers</h2>
            <p className="text-xs text-slate-400">
              What's moving in the market today
              {updatedAgo && <span className="text-slate-300/80"> • Updated {updatedAgo}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data?.source && (
            <span className="text-xs uppercase tracking-wide text-slate-300/70">
              Source: {data.source}
            </span>
          )}
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-slate-100 transition hover:border-white/40 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            disabled={isFetching}
            type="button"
          >
            <RefreshCw className={clsx('h-4 w-4', isFetching && 'animate-spin')} />
            Refresh
          </button>
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
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-500">
            <span>Data from</span>
            <a
              href="https://stocktwits.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-slate-300"
            >
              Stocktwits
            </a>
            <span>&</span>
            <a
              href="https://financialmodelingprep.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-slate-300"
            >
              FMP
            </a>
          </div>
        </>
      ) : (
        <div className="rounded-xl border border-slate-500/40 bg-slate-500/10 p-4 text-sm text-slate-200">
          {emptyStateMessage}
        </div>
      )}
    </section>
  )
}

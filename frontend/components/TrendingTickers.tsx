'use client'

import Link from 'next/link'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Flame, RefreshCw, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNowStrict } from 'date-fns'

import { getTrendingTickers, TrendingTicker } from '@/lib/api'

const MENTIONS_REFRESH_INTERVAL = 10 * 60 * 1000 // 10 minutes
const DEFAULT_EMPTY_MESSAGE = 'Trending data is temporarily unavailable. Please check back soon.'

const formatMentions = (volume?: number | null): string | null => {
  if (volume === null || volume === undefined) {
    return null
  }

  if (volume >= 1_000_000) {
    return `${Math.round(volume / 100_000) / 10}M mentions`
  }
  if (volume >= 1_000) {
    return `${Math.round(volume / 100) / 10}K mentions`
  }
  if (volume > 0) {
    return `${volume.toLocaleString()} mentions`
  }
  return null
}

const getSentiment = (score?: number | null) => {
  if (score === undefined || score === null) {
    return { label: 'Sentiment unavailable', tone: 'neutral' as const }
  }

  if (score > 0.15) {
    return { label: 'Bullish', tone: 'positive' as const }
  }
  if (score < -0.15) {
    return { label: 'Bearish', tone: 'negative' as const }
  }
  return { label: 'Neutral', tone: 'neutral' as const }
}

function SentimentBadge({ score }: { score?: number | null }) {
  const sentiment = getSentiment(score)

  const iconClass = 'h-4 w-4'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        sentiment.tone === 'positive' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
        sentiment.tone === 'negative' && 'border-rose-500/40 bg-rose-500/10 text-rose-300',
        sentiment.tone === 'neutral' && 'border-slate-500/40 bg-slate-500/10 text-slate-200'
      )}
    >
      {sentiment.tone === 'positive' && <ArrowUpRight className={iconClass} />}
      {sentiment.tone === 'negative' && <ArrowDownRight className={iconClass} />}
      {sentiment.tone === 'neutral' && <Minus className={iconClass} />}
      <span>{sentiment.label}</span>
    </span>
  )
}

function TrendingTickerCard({ ticker }: { ticker: TrendingTicker }) {
  const mentions = formatMentions(ticker.tweet_volume)

  return (
    <Link
      href={`/company/${ticker.symbol}`}
      className="flex min-w-[200px] flex-col gap-3 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-[0_12px_30px_rgba(15,23,42,0.45)] transition hover:-translate-y-1 hover:bg-white/10 hover:shadow-[0_18px_40px_rgba(56,189,248,0.25)]"
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-white">{ticker.symbol}</div>
          <div className="text-sm text-slate-300 line-clamp-2">{ticker.name ?? 'Loading company name…'}</div>
        </div>
        {mentions && (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-sky-200">
            {mentions}
          </span>
        )}
      </div>
      <SentimentBadge score={ticker.sentiment_score} />
    </Link>
  )
}

export default function TrendingTickers() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['trending-tickers'],
    queryFn: getTrendingTickers,
    staleTime: MENTIONS_REFRESH_INTERVAL,
    refetchInterval: MENTIONS_REFRESH_INTERVAL,
    retry: 1,
  })

  const hasTickers = Boolean(data?.tickers?.length)
  const updatedAgo = useMemo(() => {
    if (!data?.timestamp) {
      return null
    }

    try {
      return formatDistanceToNowStrict(new Date(data.timestamp), { addSuffix: true })
    } catch (e) {
      return null
    }
  }, [data?.timestamp])

  if (isLoading) {
    return (
      <section className="mt-12">
        <header className="mb-4 flex items-center justify-between gap-3 text-white">
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-orange-300" />
            <h2 className="text-lg font-semibold">Trending Tickers</h2>
          </div>
        </header>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="flex min-w-[200px] flex-col gap-3 rounded-2xl border border-white/5 bg-white/5 p-4"
            >
              <div className="h-6 w-20 animate-pulse rounded bg-white/10" />
              <div className="h-4 w-full animate-pulse rounded bg-white/10" />
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
          <h2 className="text-lg font-semibold">Trending Tickers</h2>
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
            <h2 className="text-lg font-semibold">Trending Tickers</h2>
            {updatedAgo && (
              <p className="text-xs text-slate-300/80">Updated {updatedAgo}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data?.source && (
            <span className="text-xs uppercase tracking-wide text-slate-300/70">Source: {data.source}</span>
          )}
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-slate-100 transition hover:border-white/40 hover:bg-white/10"
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
        <div className="flex gap-4 overflow-x-auto pb-2">
          {data?.tickers.map((ticker) => (
            <TrendingTickerCard key={ticker.symbol} ticker={ticker} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-500/40 bg-slate-500/10 p-4 text-sm text-slate-200">
          {emptyStateMessage}
        </div>
      )}
    </section>
  )
}

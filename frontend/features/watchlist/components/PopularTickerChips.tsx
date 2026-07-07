'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CircleNotchIcon, PlusIcon } from '@/lib/icons'
import { addToWatchlist } from '@/features/watchlist/api/watchlist-api'
import { queryKeys } from '@/lib/queryKeys'
import analytics from '@/lib/analytics'

// A static mega-cap list, rendered instantly with no network call — deliberately NOT the trending
// endpoint (which fans out a quote per row for data these chips don't display). One-tap onboarding
// for a beta user arriving with an empty watchlist (§2.5).
const POPULAR_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA'] as const

const CHIP_CLASSES = [
  'inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-sm font-semibold',
  'border-border-light bg-panel-light text-text-primary-light shadow-e1',
  'transition-colors duration-fast hover:bg-brand-weak hover:border-brand-border',
  'focus-visible:outline-none focus-visible:shadow-ring-brand disabled:opacity-50',
  'dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:shadow-none',
  'dark:hover:bg-white/5 dark:hover:border-brand-border-dark dark:focus-visible:shadow-ring-brand-dark',
].join(' ')

export default function PopularTickerChips() {
  const queryClient = useQueryClient()

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (_data, ticker) => {
      // Same watchlist-derived invalidation set as the other add/remove sites (§2.7).
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist() })
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlistInsights() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardFeed() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardCalendar() })
      analytics.watchlistAdded(ticker)
      toast.success(`${ticker} added to your watchlist`)
    },
    onError: () => {
      toast.error("Couldn't add that company. Please try again.")
    },
  })

  const pendingTicker = addMutation.isPending ? addMutation.variables : null

  return (
    <div className="flex flex-wrap justify-center gap-2">
      {POPULAR_TICKERS.map((ticker) => (
        <button
          key={ticker}
          type="button"
          onClick={() => addMutation.mutate(ticker)}
          disabled={addMutation.isPending}
          aria-label={`Add ${ticker} to your watchlist`}
          className={CHIP_CLASSES}
        >
          {pendingTicker === ticker ? (
            <CircleNotchIcon className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <PlusIcon className="h-3.5 w-3.5 text-brand-strong dark:text-brand-strong-dark" />
          )}
          {ticker}
        </button>
      ))}
    </div>
  )
}

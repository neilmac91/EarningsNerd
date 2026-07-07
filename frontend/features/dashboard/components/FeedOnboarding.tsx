'use client'

import { NewspaperIcon } from '@/lib/icons'
import WatchlistAddSearch from '@/features/watchlist/components/WatchlistAddSearch'
import PopularTickerChips from '@/features/watchlist/components/PopularTickerChips'

/**
 * The actionable empty state for a brand-new user with no watched companies (§2.5). Follows the
 * GuidanceCard look (centred panel, brand-tint icon) but hosts the add-search above the copy and the
 * one-tap popular-ticker chips below it, so the "search above or tap a ticker below" line reads
 * literally. Adding a company here invalidates the feed, which then replaces this panel with cards.
 */
export default function FeedOnboarding() {
  return (
    <div
      role="status"
      className="flex flex-col items-center rounded-xl border border-border-light bg-panel-light px-6 py-10 text-center shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark">
        <NewspaperIcon className="h-5 w-5" aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-base font-semibold text-text-primary-light dark:text-text-primary-dark">
        Follow your first company
      </h3>
      <div className="mt-5 w-full max-w-sm text-left">
        <WatchlistAddSearch />
      </div>
      <p className="mt-3 max-w-[42ch] text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
        Search above or tap a ticker below. New filings land here the day they hit EDGAR.
      </p>
      <div className="mt-4">
        <PopularTickerChips />
      </div>
    </div>
  )
}

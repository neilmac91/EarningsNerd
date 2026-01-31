'use client'

import Link from 'next/link'
import { memo, useCallback } from 'react'
import posthog from 'posthog-js'

// Rule 6.2: Hoist static data outside component to prevent recreation
const TOP_COMPANIES = [
  { ticker: 'AAPL', name: 'Apple' },
  { ticker: 'NVDA', name: 'NVIDIA' },
  { ticker: 'TSLA', name: 'Tesla' },
  { ticker: 'MSFT', name: 'Microsoft' },
  { ticker: 'META', name: 'Meta' },
  { ticker: 'GOOGL', name: 'Alphabet' },
  { ticker: 'AMZN', name: 'Amazon' },
  { ticker: 'BABA', name: 'Alibaba' },
] as const

function QuickAccessBar() {
  // Track clicks for analytics
  const handleClick = useCallback((ticker: string) => {
    posthog.capture('quick_access_click', { ticker })
  }, [])

  return (
    <section className="py-6" aria-label="Popular companies">
      <p className="mb-4 text-center text-sm font-medium text-slate-400">
        Popular companies — click to explore
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        {TOP_COMPANIES.map(({ ticker, name }) => (
          <Link
            key={ticker}
            href={`/company/${ticker}`}
            onClick={() => handleClick(ticker)}
            className="group flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:-translate-y-1 hover:border-mint-500 hover:bg-white/10 hover:shadow-lg hover:shadow-mint-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            data-testid={`quick-access-${ticker}`}
          >
            <span className="font-bold text-white">{ticker}</span>
            <span className="hidden text-slate-400 transition-colors group-hover:text-mint-400 sm:inline">
              {name}
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

// Rule 5.4: Memoize to prevent unnecessary re-renders
export default memo(QuickAccessBar)

// Export for testing
export { TOP_COMPANIES }

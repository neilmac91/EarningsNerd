'use client'

import Link from 'next/link'
import { memo, useCallback } from 'react'
import posthog from 'posthog-js'
import CompanyLogo from '@/components/CompanyLogo'

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
      <p className="mb-4 text-center text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark">
        Popular companies — click to explore
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        {TOP_COMPANIES.map(({ ticker, name }) => (
          <Link
            key={ticker}
            href={`/company/${ticker}`}
            onClick={() => handleClick(ticker)}
            className="group flex items-center gap-2 rounded-full border border-border-light bg-panel-light shadow-e1 px-4 py-2.5 text-sm font-medium transition duration-base hover:-translate-y-1 hover:border-brand-strong hover:bg-white hover:shadow-e2 dark:border-white/10 dark:bg-white/5 dark:shadow-none dark:hover:border-brand-dark dark:hover:bg-white/10 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark "
            data-testid={`quick-access-${ticker}`}
          >
            <CompanyLogo ticker={ticker} name={name} size={20} />
            <span className="font-bold text-text-primary-light dark:text-text-primary-dark">{ticker}</span>
            <span className="hidden text-text-secondary-light transition-colors group-hover:text-brand-strong dark:text-text-secondary-dark dark:group-hover:text-brand-strong-dark sm:inline">
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

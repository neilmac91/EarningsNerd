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

/**
 * Popular-company chips under the hero search: monogram/Logo.dev mark, ticker in the data face,
 * company name from `sm` up. Chips are e1 panel pills that brighten on hover (no lift).
 */
function QuickAccessBar() {
  // Track clicks for analytics
  const handleClick = useCallback((ticker: string) => {
    posthog.capture('quick_access_click', { ticker })
  }, [])

  return (
    <section className="mt-3.5 flex flex-wrap gap-2" aria-label="Popular companies">
      {TOP_COMPANIES.map(({ ticker, name }) => (
        <Link
          key={ticker}
          href={`/company/${ticker}`}
          onClick={() => handleClick(ticker)}
          className="inline-flex min-h-9 items-center gap-2 rounded-full border border-border-light bg-panel-light py-1.5 pl-1.5 pr-3 text-[13px] font-medium shadow-e1 transition-colors duration-fast hover:border-brand-border hover:bg-white dark:border-white/10 dark:bg-panel-dark dark:shadow-none dark:hover:border-brand-border-dark dark:hover:bg-white/10 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          data-testid={`quick-access-${ticker}`}
        >
          <CompanyLogo ticker={ticker} name={name} size={24} />
          <span className="font-data text-xs font-semibold text-text-primary-light dark:text-text-primary-dark">{ticker}</span>
          <span className="hidden text-text-secondary-light dark:text-text-secondary-dark sm:inline">{name}</span>
        </Link>
      ))}
    </section>
  )
}

// Rule 5.4: Memoize to prevent unnecessary re-renders
export default memo(QuickAccessBar)

// Export for testing
export { TOP_COMPANIES }

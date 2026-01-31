import { Suspense } from 'react'
import { redirect } from 'next/navigation'
import Link from 'next/link'

// Rule 2.1: Direct imports, no barrel files
import CompanySearch from '@/components/CompanySearch'
import QuickAccessBar from '@/components/QuickAccessBar'
import HotFilings from '@/components/HotFilings'
import TrendingTickers from '@/components/TrendingTickers'

// Rule 6.2: Hoist static values outside component
const CURRENT_YEAR = new Date().getFullYear()

// Rule 6.2: Hoist static skeleton components outside
function HotFilingsSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-label="Loading hot filings">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-28 animate-pulse rounded-xl border border-white/10 bg-white/5"
        />
      ))}
    </div>
  )
}

function TrendingTickersSkeleton() {
  return (
    <div className="mt-12" role="status" aria-live="polite" aria-label="Loading market movers">
      <div className="mb-4 flex items-center gap-2">
        <div className="h-5 w-5 animate-pulse rounded bg-white/10" />
        <div className="h-6 w-32 animate-pulse rounded bg-white/10" />
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-28 w-52 flex-shrink-0 animate-pulse rounded-2xl border border-white/10 bg-white/5"
          />
        ))}
      </div>
    </div>
  )
}

export default function Home() {
  // Waitlist is enabled by default unless explicitly disabled
  const isWaitlistEnabled = process.env.WAITLIST_MODE !== 'false'

  if (isWaitlistEnabled) {
    redirect('/waitlist')
  }

  return (
    <>
      <main className="min-h-screen space-y-12 py-12 md:py-16 lg:py-20">
        {/* Hero Section */}
        <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
              The professional standard for{' '}
              <span className="text-mint-600 dark:text-mint-400">SEC Filing Analysis</span>
            </h1>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
              Go beyond the headlines. Instantly access institutional-grade, AI-powered summaries and insights for any public company.
            </p>
          </div>

          <div className="mx-auto mt-8 max-w-xl sm:mt-10">
            <CompanySearch />
          </div>
        </section>

        {/* Quick Access Bar - Popular Companies */}
        <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <QuickAccessBar />
        </section>

        {/* Hot Filings - Rule 1.3: Independent Suspense boundary */}
        <section className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-xl font-bold text-text-primary-light dark:text-text-primary-dark">
              <span>🔥</span> Hot Filings
            </h2>
          </div>
          <Suspense fallback={<HotFilingsSkeleton />}>
            <HotFilings limit={5} />
          </Suspense>
        </section>

        {/* Market Movers - Rule 1.3: Independent Suspense boundary */}
        <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <Suspense fallback={<TrendingTickersSkeleton />}>
            <TrendingTickers />
          </Suspense>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border-light bg-background-light dark:border-border-dark dark:bg-background-dark">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-12 text-sm text-text-secondary-light dark:text-text-secondary-dark md:flex-row md:items-center md:justify-between">
          <div className="font-medium text-text-tertiary-light dark:text-text-tertiary-dark">
            &copy; {CURRENT_YEAR} EarningsNerd. All rights reserved.
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <Link href="/privacy" className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500">Privacy</Link>
            <Link href="/security" className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500">Security</Link>
            <Link href="mailto:hello@earningsnerd.com" className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500">Contact</Link>
          </div>
        </div>
      </footer>
    </>
  )
}

import Link from 'next/link'
import { Suspense } from 'react'
import WaitlistForm from '@/components/WaitlistForm'
import WaitlistCounter from '@/components/WaitlistCounter'

export default function WaitlistPage() {
  return (
    <>
      <main className="space-y-16 py-12 md:py-20 lg:py-24">
        <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
              Get early access to{' '}
              <span className="text-mint-600 dark:text-mint-400">AI-powered SEC filing summaries</span>
            </h1>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
              Be first to know when we launch. Professional-grade insights designed for retail investors.
            </p>
          </div>

          <div className="mx-auto mt-6 flex justify-center sm:mt-8">
            <WaitlistCounter />
          </div>

          <div className="mx-auto mt-8 max-w-xl sm:mt-10">
            <Suspense
              fallback={
                <div className="rounded-2xl border border-border-light bg-white/90 p-6 shadow-lg dark:border-border-dark dark:bg-slate-900/70">
                  Loading…
                </div>
              }
            >
              <WaitlistForm source="waitlist" />
            </Suspense>
          </div>
        </section>
      </main>

      <footer className="border-t border-border-light bg-background-light dark:border-border-dark dark:bg-background-dark">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-12 text-sm text-text-secondary-light dark:text-text-secondary-dark md:flex-row md:items-center md:justify-between">
          <div className="font-medium text-text-tertiary-light dark:text-text-tertiary-dark">
            &copy; {new Date().getFullYear()} EarningsNerd. All rights reserved.
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <Link
              href="/privacy"
              className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
            >
              Privacy
            </Link>
            <Link
              href="/security"
              className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
            >
              Security
            </Link>
            <Link
              href="mailto:hello@earningsnerd.com"
              className="font-medium transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark"
            >
              Contact
            </Link>
          </div>
        </div>
      </footer>
    </>
  )
}

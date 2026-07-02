import { memo } from 'react'
import Link from 'next/link'
import { ArrowRightIcon } from '@/lib/icons'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'

function CtaBanner() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="overflow-hidden rounded-3xl border border-border-light bg-panel-light shadow-e3 p-10 dark:border-white/10 dark:bg-panel-dark sm:p-14">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-4xl">
            Ready to decode your next filing?
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-lg text-text-secondary-light dark:text-text-secondary-dark">
            Stop spending hours on filings. Get the insights that matter in minutes.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <ExampleCtaLink
              href={exampleFilingHref('cta_banner_example')}
              placement="cta_banner"
              className="inline-flex items-center gap-2 rounded-full bg-brand px-8 py-3.5 text-base font-semibold text-white shadow-e2 transition-all hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              Run your first summary
              <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
            </ExampleCtaLink>
            <Link
              href="/register"
              className="inline-flex items-center gap-1 text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark underline underline-offset-4 decoration-border-light dark:decoration-white/10 transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark hover:decoration-text-primary-light dark:hover:decoration-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              or create a free account — 5 summaries a month
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}

export default memo(CtaBanner)

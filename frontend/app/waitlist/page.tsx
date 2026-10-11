import { Suspense } from 'react'
import type { Metadata } from 'next'
import { ArrowRightIcon } from '@/lib/icons'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import WaitlistCounter from '@/features/waitlist/components/WaitlistCounter'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'
import WaitlistExample, { WaitlistExamplePending } from '@/features/waitlist/components/WaitlistExample'

// While the waitlist gate is up, this page is the de-facto homepage — it needs
// its own metadata and a self-canonical so search engines index something real.
export const metadata: Metadata = {
  title: 'EarningsNerd | The 10-K, read for you, with receipts',
  description:
    'Join the EarningsNerd waitlist. AI summaries of SEC filings: financials, risks, and trends, sourced directly from SEC EDGAR.',
  alternates: {
    canonical: '/waitlist',
  },
}

export default function WaitlistPage() {
  return (
    <main className="space-y-20 py-12 md:py-20 lg:py-24">
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
          <div className="text-center lg:text-left">
            <h1 className="text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
              The 10-K, read for you, <span className="en-mark">with receipts</span>.
            </h1>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
              AI summaries of 10-Ks and 10-Qs for investors who still check the source. Figures are
              checked against the company’s XBRL where they can be, and quotes against the filing’s
              own text.
            </p>

            <div className="mt-6 flex justify-center lg:justify-start">
              <WaitlistCounter />
            </div>

            <div id="waitlist" className="mt-8 max-w-xl lg:mx-0">
              <Suspense
                fallback={
                  <div className="rounded-2xl border border-border-light bg-panel-light p-6 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark">
                    Loading…
                  </div>
                }
              >
                <WaitlistForm source="waitlist" />
              </Suspense>
            </div>

            <p className="mt-4 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
              No spam. Early access invites and product updates only.
            </p>

            <p className="mt-6 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Don&apos;t want to wait?{' '}
              <ExampleCtaLink
                href={exampleFilingHref('waitlist_example')}
                placement="waitlist"
                className="inline-flex items-center gap-1 font-semibold text-brand-strong underline underline-offset-4 transition-colors hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark"
              >
                Try a live example summary
                <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
              </ExampleCtaLink>
            </p>
          </div>

          <Suspense fallback={<WaitlistExamplePending />}>
            <WaitlistExample />
          </Suspense>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {[
            {
              title: 'Filings are long.',
              body: 'A 10-K runs past a hundred pages, and the part you want is spread across six of its sections.',
            },
            {
              title: 'Checking takes an afternoon.',
              body: 'A figure in a summary is only useful once you know where it came from. We point at the fact or the passage.',
            },
            {
              title: 'You still read the filing.',
              body: 'We remove the tedium, not the reading. The summary is the map; the original is one click away.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-light bg-panel-light p-6 shadow-e1 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
            >
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                {item.title}
              </h3>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-border-light bg-panel-light p-8 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark md:p-10">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                How it works
              </h2>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                From the filing to its summary, with the receipts.
              </p>
            </div>
            {/* Server component — buttonVariants() can't be called here (it's a client export),
                so this CTA stays a token-clean hand-rolled secondary pill. */}
            <a
              href="#waitlist"
              className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-weak px-4 py-2 text-sm font-semibold text-brand-strong transition hover:border-brand-border dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark"
            >
              Join the waitlist
            </a>
          </div>
          <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-4">
            {[
              {
                step: '01',
                title: 'Search a company',
                body: 'Any company with a ticker on SEC EDGAR, by name or ticker.',
              },
              {
                step: '02',
                title: 'Select a filing',
                body: 'Pick a 10-K or 10-Q from SEC EDGAR.',
              },
              {
                step: '03',
                title: 'Read the summary',
                body: 'Nine parts, from The Print to Notable Footnotes, in the same order for every filing.',
              },
              {
                step: '04',
                title: 'Check what you like',
                body: 'Risk excerpts open at their passage, and every summary links to the original on SEC EDGAR.',
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-2xl border border-border-light bg-background-light px-5 py-4 dark:border-border-dark dark:bg-background-dark"
              >
                {/* A step number is a number: neutral ink, never sage (the Separate Signals Rule). */}
                <div className="font-data text-xs font-semibold text-text-secondary-light dark:text-text-secondary-dark">
                  {item.step}
                </div>
                <h3 className="mt-2 text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {[
            {
              title: 'One outline, every filing',
              body: 'Nine parts from The Print to Notable Footnotes, in the same order, so the second filing reads faster than the first.',
            },
            {
              title: 'Figures checked against XBRL',
              body: 'Figures the server can check are matched to the company’s XBRL fact, or counted as unmatched.',
            },
            {
              title: 'Risks in the filing’s own words',
              body: 'Risk excerpts are quoted, located in the filing text, and withheld when they cannot be.',
            },
            {
              title: 'The original, one click away',
              body: 'Every summary links to the filing on SEC EDGAR, and each risk excerpt to its passage.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-light bg-panel-light p-6 shadow-e1 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
            >
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                {item.title}
              </h3>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-border-light bg-panel-light p-8 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark md:p-10">
          <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Built for trust and transparency
          </h2>
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Data is sourced directly from SEC EDGAR. We focus on clarity, not hype.
          </p>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              {
                title: 'Source: SEC EDGAR',
                body: 'Official filings, cited and traceable back to the primary source.',
              },
              {
                title: 'Security-first approach',
                body: 'Encrypted data in transit and at rest. No personal financial data stored.',
              },
              {
                title: 'A numbered spot',
                body: 'Join the list and get a position. Each referral moves you up 5 spots.',
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-border-light bg-background-light px-5 py-4 text-sm text-text-secondary-light dark:border-border-dark dark:bg-background-dark dark:text-text-secondary-dark"
              >
                <div className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {item.title}
                </div>
                <p className="mt-2">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}

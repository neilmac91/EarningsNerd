import { Suspense } from 'react'
import type { Metadata } from 'next'
import { ArrowRightIcon } from '@/lib/icons'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import { WaitlistAccessStatus, WaitlistEntryLink } from '@/features/waitlist/components/WaitlistAccess'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import BrandEmphasis from '@/features/marketing/components/BrandEmphasis'
import FormCodeText from '@/features/marketing/components/FormCodeText'
import { exampleFilingHref } from '@/lib/featureFlags'
import WaitlistExample, { WaitlistExamplePending } from '@/features/waitlist/components/WaitlistExample'

// While the waitlist gate is up, this page is the de-facto homepage — it needs
// its own metadata and a self-canonical so search engines index something real.
export const metadata: Metadata = {
  title: 'The 10-K, read for you, with receipts | EarningsNerd',
  description:
    'Explore EarningsNerd and check private beta availability. AI summaries of SEC filings: financials, risks, and trends, sourced directly from SEC EDGAR.',
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
            <h1 className="isolate [container-type:inline-size] text-4xl font-semibold text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
              The <FormCodeText text="10-K, read for you, " /><BrandEmphasis trailingPeriod>with receipts</BrandEmphasis>
            </h1>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
              <FormCodeText text="AI summaries of 10-Ks and 10-Qs for investors who still check the source. Figures are checked against the company’s filed data where they can be, and quotes against the filing’s own text." />
            </p>

            <div className="mt-6 flex justify-center lg:justify-start">
              <WaitlistAccessStatus />
            </div>

            <div id="waitlist" className="mt-8 max-w-xl lg:mx-0">
              <Suspense
                fallback={
                  <div className="rounded-2xl border border-border-light bg-panel-light p-cap-6 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark">
                    Loading…
                  </div>
                }
              >
                <WaitlistForm source="waitlist" />
              </Suspense>
            </div>

            <p className="mt-4 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
              Joining the waitlist does not create an account or guarantee an invitation.
            </p>

            <p className="mt-6 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Don&apos;t want to wait?{' '}
              <ExampleCtaLink
                href={exampleFilingHref('waitlist_example')}
                placement="waitlist"
                className="inline-flex items-center gap-1 rounded-sm font-semibold text-brand-strong underline underline-offset-4 transition-colors hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-strong-dark"
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
              body: 'A 10-K is long, and the part you want is spread across its sections.',
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
              className="rounded-2xl border border-border-light bg-panel-light p-cap-6 shadow-e1 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
            >
              {/* h2: the first headings under the page h1 (the example beside the form has none), at
                  the card scale; an h3 here skipped a level (text-floors.spec.ts visits /waitlist). */}
              <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                {item.title}
              </h2>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark"><FormCodeText text={item.body} /></p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-border-light bg-panel-light p-cap-8 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark md:p-cap-10">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                How it works
              </h2>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                From the filing to its summary, with the receipts.
              </p>
            </div>
            {/* A hand-rolled pill on purpose: this server page cannot call buttonVariants() (a client
                export), and MarketingCta, which renders that recipe for a server section, gives the
                secondary button's own look (transparent at rest, rounded-lg). The pill rests at the
                secondary recipe's hover fill (in dark a shade stronger: brand-dark/15, where the
                recipe's brand-weak-dark is the same sage at 0.14) and takes the recipe's pressed fill
                under the pointer, in both themes (E82): its label measures 5.33:1 on that fill in light
                and 4.50:1 in dark, on this card. tests/e2e/text-floors.spec.ts holds both themes, at
                rest and hovered. */}
            <WaitlistEntryLink
              className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-weak px-4 py-2 text-sm font-semibold text-brand-strong transition-colors duration-fast hover:bg-brand-border/60 focus-visible:outline-none focus-visible:shadow-ring-brand dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark dark:hover:bg-brand-border-dark dark:focus-visible:shadow-ring-brand-dark"
            />
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
                body: 'Up to nine parts, from The Print to Notable Footnotes, in the same order for every filing.',
              },
              {
                step: '04',
                title: 'Check what you like',
                body: 'Risk excerpts open at their passage, and every summary links to the original on SEC.gov.',
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-2xl border border-border-light bg-background-light px-cap-5 py-4 dark:border-border-dark dark:bg-background-dark"
              >
                {/* A step number is a number: neutral ink, never sage (the Separate Signals Rule). */}
                <div className="font-data text-xs font-semibold text-text-secondary-light dark:text-text-secondary-dark">
                  {item.step}
                </div>
                <h3 className="mt-2 text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark"><FormCodeText text={item.body} /></p>
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
              body: 'Up to nine parts from The Print to Notable Footnotes, in the same order, so the second filing reads faster than the first.',
            },
            {
              title: 'Figures checked against the filing',
              body: 'Figures the server can check are matched to the company’s filed data, and replaced with the filed figure where they differ.',
            },
            {
              title: 'Risks in the filing’s own words',
              body: 'Risk excerpts are quoted, located in the filing text, and withheld when they cannot be.',
            },
            {
              title: 'The original, one click away',
              body: 'Every summary links to the filing on SEC.gov, and each risk excerpt to its passage.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-light bg-panel-light p-cap-6 shadow-e1 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
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
        <div className="rounded-3xl border border-border-light bg-panel-light p-cap-8 shadow-e2 dark:shadow-none dark:border-border-dark dark:bg-panel-dark md:p-cap-10">
          <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Before you join
          </h2>
          {/* No lead: the tiles say it, and the first already names the source. */}
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              {
                title: 'Filings from SEC.gov',
                body: 'Official filings, cited and traceable back to the primary source.',
              },
              {
                title: 'Security',
                body: 'HTTPS connections, hashed passwords and card payments handled by Stripe.',
              },
              {
                title: 'A numbered spot',
                body: 'You get a number when you join, and your link moves you up.',
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-border-light bg-background-light px-cap-5 py-4 text-sm text-text-secondary-light dark:border-border-dark dark:bg-background-dark dark:text-text-secondary-dark"
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

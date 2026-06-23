import { Suspense } from 'react'
import type { Metadata } from 'next'
import { ArrowRight } from 'lucide-react'
import WaitlistForm from '@/components/WaitlistForm'
import WaitlistCounter from '@/components/WaitlistCounter'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'

// While the waitlist gate is up, this page is the de-facto homepage — it needs
// its own metadata and a self-canonical so search engines index something real.
export const metadata: Metadata = {
  title: 'EarningsNerd — Read a 10-K in 5 minutes, not 5 hours',
  description:
    'Join the EarningsNerd waitlist. AI-powered summaries turn dense SEC 10-K and 10-Q filings into clear, decision-ready insights — sourced directly from SEC EDGAR.',
  alternates: {
    canonical: '/waitlist',
  },
}

export default function WaitlistPage() {
  return (
    <main className="space-y-20 py-12 md:py-20 lg:py-24">
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
          <div className="text-center lg:text-left">
            <h1 className="text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
              Read a 10-K in{' '}
              <span className="text-brand-strong dark:text-brand-strong-dark">5 minutes</span>, not 5 hours.
            </h1>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
              EarningsNerd turns dense SEC filings into clear, decision-ready insights on business performance,
              risks, and trends. Built for investors who want the signal without the slog.
            </p>

            <div className="mt-6 flex justify-center lg:justify-start">
              <WaitlistCounter />
            </div>

            <div id="waitlist" className="mt-8 max-w-xl lg:mx-0">
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

            <p className="mt-4 text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
              No spam. Early access invites and product updates only.
            </p>

            <p className="mt-6 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Don&apos;t want to wait?{' '}
              <ExampleCtaLink
                href={exampleFilingHref('waitlist_example')}
                placement="waitlist"
                className="inline-flex items-center gap-1 font-semibold text-brand-strong underline underline-offset-4 transition-colors hover:text-brand-light dark:text-brand-strong-dark dark:hover:text-brand-strong-dark"
              >
                Try a live example summary
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </ExampleCtaLink>
            </p>
          </div>

          <div className="relative">
            <div className="rounded-3xl border border-border-light bg-white/90 p-6 shadow-xl backdrop-blur-sm dark:border-border-dark dark:bg-slate-900/80">
              <div className="flex items-center justify-between text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
                <span className="font-semibold text-text-secondary-light dark:text-text-secondary-dark">
                  Product preview
                </span>
                <span>Q3 2025 10-Q Summary</span>
              </div>
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
                  <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-tertiary-dark">
                    Executive summary
                  </div>
                  <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    Revenue grew 11% year-over-year, driven by cloud subscriptions and enterprise expansion.
                    Margins improved as operating expenses scaled slower than sales.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
                    <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-tertiary-dark">
                      Key drivers
                    </div>
                    <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                      <li>Subscription retention 94%</li>
                      <li>International growth +18%</li>
                      <li>R&amp;D spend up 6%</li>
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-border-light bg-background-light px-4 py-3 dark:border-border-dark dark:bg-background-dark">
                    <div className="text-xs uppercase tracking-wide text-text-tertiary-light dark:text-text-tertiary-dark">
                      Risk flags
                    </div>
                    <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                      <li>Customer concentration</li>
                      <li>FX headwinds</li>
                      <li>Regulatory scrutiny</li>
                    </ul>
                  </div>
                </div>
                <div className="rounded-2xl border border-brand-light/40 bg-brand-weak px-4 py-3 text-sm text-brand-strong dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark">
                  See key metrics, risks, and highlights in one concise report.
                </div>
              </div>
            </div>
            <div className="absolute -bottom-6 -right-6 hidden h-24 w-24 rounded-full bg-brand-light/30 blur-2xl dark:bg-brand-dark/30 lg:block" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-6 md:grid-cols-3">
          {[
            {
              title: 'Filings are long and dense.',
              body: '10-Ks average 100+ pages. Most investors skim or skip the details entirely.',
            },
            {
              title: 'The signal is buried.',
              body: 'Material risks, margin shifts, and strategic pivots are spread across sections.',
            },
            {
              title: 'Speed matters.',
              body: 'Markets move fast. You need clarity before the next earnings call.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-light bg-white/90 p-6 shadow-sm dark:border-border-dark dark:bg-slate-900/70"
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
        <div className="rounded-3xl border border-border-light bg-white/90 p-8 shadow-lg dark:border-border-dark dark:bg-slate-900/70 md:p-10">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                How it works
              </h2>
              <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                From SEC filing to actionable insight in minutes.
              </p>
            </div>
            <a
              href="#waitlist"
              className="inline-flex items-center justify-center rounded-full border border-brand-light/40 bg-brand-weak px-4 py-2 text-sm font-semibold text-brand-strong transition hover:border-brand-light/60 dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark"
            >
              Join the waitlist
            </a>
          </div>
          <div className="mt-8 grid gap-6 md:grid-cols-4">
            {[
              {
                step: '01',
                title: 'Search a company',
                body: 'Find any public company by name or ticker.',
              },
              {
                step: '02',
                title: 'Select a filing',
                body: 'Pick a 10-K or 10-Q from SEC EDGAR.',
              },
              {
                step: '03',
                title: 'Get the summary',
                body: 'Read business, financials, risks, and MD&A highlights.',
              },
              {
                step: '04',
                title: 'Act with clarity',
                body: 'Use the summary to ask sharper questions and move faster.',
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-2xl border border-border-light bg-background-light px-5 py-4 dark:border-border-dark dark:bg-background-dark"
              >
                <div className="text-xs font-semibold uppercase tracking-widest text-brand-strong dark:text-brand-strong-dark">
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
        <div className="grid gap-6 md:grid-cols-2">
          {[
            {
              title: 'Structured AI summaries',
              body: 'Consistent sections for business overview, financials, risks, and outlook.',
            },
            {
              title: 'Consistent structure',
              body: 'Uniform sections make it easy to scan what matters fast.',
            },
            {
              title: 'Risk factor signals',
              body: 'Track new or evolving disclosures before the market reacts.',
            },
            {
              title: 'XBRL-aware insights',
              body: 'Key metrics and highlights grounded in SEC filing data.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-border-light bg-white/90 p-6 shadow-sm dark:border-border-dark dark:bg-slate-900/70"
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
        <div className="rounded-3xl border border-border-light bg-white/90 p-8 shadow-lg dark:border-border-dark dark:bg-slate-900/70 md:p-10">
          <h2 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Built for trust and transparency
          </h2>
          <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Data is sourced directly from SEC EDGAR. We focus on clarity, not hype.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
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
                title: 'Momentum is real',
                body: 'Join investors who want faster, clearer insights.',
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

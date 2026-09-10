import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { ArrowRightIcon, BellIcon, ClockCounterClockwiseIcon, FilePdfIcon, FileXlsIcon } from '@/lib/icons'
import { ENABLE_ANALYSIS } from '@/lib/featureFlags'
import { FREE_COPILOT_QUESTIONS, FREE_HISTORY_RETENTION_DAYS } from '@/lib/planLimits'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import AskFilingDemo from '@/features/marketing/components/AskFilingDemo'
import ChangeReportDemo from '@/features/marketing/components/ChangeReportDemo'
import MarketingCta from '@/features/marketing/components/MarketingCta'
import SectionImpression from '@/features/marketing/components/SectionImpression'

const EXTRAS = [
  {
    icon: FileXlsIcon,
    title: 'Excel export',
    description: 'Multi-Period Analysis as a workbook, figures still tied to XBRL.',
    tags: ['XLSX'],
  },
  {
    icon: FilePdfIcon,
    title: 'Summary export',
    description: 'Any summary as a PDF for reading or a CSV for your own model.',
    tags: ['PDF', 'CSV'],
  },
  {
    icon: BellIcon,
    title: 'Filing alerts',
    description: 'Hourly checks for new filings on your watchlist, including 8-Ks.',
    tags: ['10-K', '10-Q', '8-K'],
  },
  {
    icon: ClockCounterClockwiseIcon,
    title: 'Full history',
    description: `Every summary you have read, kept. Free keeps ${FREE_HISTORY_RETENTION_DAYS} days.`,
    tags: ['Unlimited'],
  },
] as const

/** One Pro feature: the PRO chip + title + paragraph (and an optional CTA) beside its product screen. */
function FeatureRow({
  title,
  description,
  cta,
  children,
}: {
  title: string
  description: string
  cta?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="grid items-center gap-6 lg:grid-cols-2 lg:gap-12">
      <div className="min-w-0 max-w-[420px]">
        <div className="flex items-center gap-2.5">
          <Badge variant="pro" className="shrink-0">
            Pro
          </Badge>
          <h3 className="min-w-0 flex-1 text-2xl">{title}</h3>
        </div>
        <p className="mt-3 text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {description}
        </p>
        {cta}
      </div>
      {/* min-w-0: a grid item defaults to min-width:auto, so a wide table inside the frame would
          otherwise widen the page instead of scrolling inside its own container. */}
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/**
 * "What Pro adds" (design section 6): three feature rows, each pairing its pitch with the REAL
 * product screen fed static sample data (Ask this Filing, Multi-Period Analysis, Change Report),
 * then the "Also in Pro" grid of the smaller Pro extras. The Multi-Period CTA renders only while
 * the analysis route exists (ENABLE_ANALYSIS); it 404s otherwise.
 */
export default function ProDepth() {
  return (
    <section
      id="pro"
      aria-labelledby="pro-h"
      className="border-t border-border-light py-20 dark:border-white/10 sm:py-24"
    >
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="pro_depth">
          <div className="max-w-2xl">
            <h2 id="pro-h" className="text-3xl lg:text-4xl">
              What Pro adds
            </h2>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
              Three ways to go deeper than one filing, each grounded in the same SEC data.
            </p>
          </div>

          <div className="mt-12 space-y-12 lg:space-y-16">
            <FeatureRow
              title="Ask this Filing"
              description={`Ask a question of one filing. Every answer cites its source: numbered chips for passages, F-numbered chips for XBRL figures, each marked Verified or Cited. Free accounts get ${FREE_COPILOT_QUESTIONS} questions.`}
            >
              <AskFilingDemo />
            </FeatureRow>

            <FeatureRow
              title="Multi-Period Analysis"
              description="Up to 10 fiscal years or 12 quarters of one company: charts, a metrics grid, and a streamed trend narrative with citations. Export to Excel."
              cta={
                ENABLE_ANALYSIS ? (
                  <MarketingCta variant="secondary" size="md" href="/analysis?ticker=AAPL" className="mt-4">
                    Try it on Apple
                    <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
                  </MarketingCta>
                ) : null
              }
            >
              <AnalysisDemo />
            </FeatureRow>

            <FeatureRow
              title="Change Report"
              description="What changed against the prior filing: metric deltas computed from XBRL, risk factors that are new, and language no longer cited."
            >
              <ChangeReportDemo />
            </FeatureRow>
          </div>

          <div className="mt-12 border-t border-border-light pt-8 dark:border-white/10 lg:mt-16">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <h3 className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Also in Pro</h3>
              <span className="text-[13px] text-text-secondary-light dark:text-text-secondary-dark">
                Watchlists are unlimited on both plans.
              </span>
            </div>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {EXTRAS.map((extra) => {
                const Icon = extra.icon
                return (
                  <Card
                    as="li"
                    key={extra.title}
                    className="flex flex-col gap-3 p-4.5 transition-colors duration-fast hover:bg-white dark:hover:bg-white/10"
                  >
                    <span
                      aria-hidden="true"
                      className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-weak text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark"
                    >
                      <Icon className="h-6 w-6" />
                    </span>
                    <div>
                      <h4 className="text-[15px] leading-5">{extra.title}</h4>
                      <p className="mt-1 text-[13px] leading-[18px] text-text-secondary-light dark:text-text-secondary-dark">
                        {extra.description}
                      </p>
                    </div>
                    <div className="mt-auto flex flex-wrap gap-1.5">
                      {extra.tags.map((tag) => (
                        <Badge key={tag} variant="neutral" className="font-data">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </Card>
                )
              })}
            </ul>
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}

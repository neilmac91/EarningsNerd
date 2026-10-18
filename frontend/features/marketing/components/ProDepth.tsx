import { Fragment, type ReactNode } from 'react'
import { Badge } from '@/components/ui/Badge'
import { ArrowRightIcon } from '@/lib/icons'
import { ENABLE_ANALYSIS } from '@/lib/featureFlags'
import { ANALYSIS_MAX_ANNUAL_PERIODS, ANALYSIS_MAX_QUARTERLY_PERIODS, FREE_COPILOT_QUESTIONS, FREE_HISTORY_RETENTION_DAYS } from '@/lib/planLimits'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import AskFilingDemo from '@/features/marketing/components/AskFilingDemo'
import ChangeReportDemo from '@/features/marketing/components/ChangeReportDemo'
import LandingRow from '@/features/marketing/components/LandingRow'
import MarketingCta from '@/features/marketing/components/MarketingCta'

// The Excel tile exports Multi-Period Analysis, so it ships with the analysis route (ENABLE_ANALYSIS).
const EXCEL_EXTRA = 'Excel export'

// Each extra names its file kinds or forms in the data face, as text: a form code is never a chip (DESIGN.md).
const EXTRAS = [
  {
    title: EXCEL_EXTRA,
    description: 'Multi-Period Analysis as a workbook, with XBRL-backed metrics.',
    tags: ['XLSX'],
  },
  {
    title: 'Summary export',
    description: 'Any summary as a PDF for reading or a CSV for your own model.',
    tags: ['PDF', 'CSV'],
  },
  {
    title: 'Filing alerts',
    description: 'Hourly checks for new filings on your watchlist, including 8-Ks.',
    tags: ['10-K', '10-Q', '8-K'],
  },
  {
    title: 'Full history',
    description: `Every summary you have read, kept. Free keeps ${FREE_HISTORY_RETENTION_DAYS} days.`,
    tags: ['Unlimited'],
  },
] as const

/** One feature: its title (with the Pro chip when Pro has it in full and Free does not) + paragraph (and an
 *  optional CTA) above its product screen, the same order for every feature (D-045: no alternating rows). */
function FeatureRow({
  title,
  pro = false,
  description,
  cta,
  children,
}: {
  title: string
  pro?: boolean
  description: string
  cta?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="py-10 first:pt-0 last:pb-0">
      <div className="max-w-2xl">
        <div className="flex items-center gap-2.5">
          {pro && (
            <Badge variant="pro" className="shrink-0">
              Pro
            </Badge>
          )}
          <h3 className="min-w-0 flex-1 text-xl">{title}</h3>
        </div>
        <p className="mt-3 text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {description}
        </p>
        {cta}
      </div>
      {/* min-w-0: a wide table inside the frame scrolls inside its own container instead of widening the page. */}
      <div className="mt-6 min-w-0">{children}</div>
    </div>
  )
}

/**
 * "More ways to read one filing" as a ruled row (D-045): the feature screens one under another in the content
 * column, each pitch above the REAL product screen fed static sample data (Ask this Filing, Multi-Period Analysis,
 * Change Report), then the "Also in Pro" extras as a ruled list, two across from 40rem at the reader's text
 * size, never the four-up grid of tiles the template skeleton had (T4). The Pro chip marks the two features Pro
 * has in full (Free asks a few questions and sees the analysis demo); the Change Report carries none, since both
 * plans read the same report while production ships no wording diff (entitlements.py, ENABLE_SECTION_CHANGES;
 * tests/unit/changeReportPlanClaims.spec.ts). Multi-Period Analysis (its row, its
 * CTA, the Excel extra and its mention in the lead) renders only while the analysis route exists
 * (ENABLE_ANALYSIS): the route 404s otherwise, so the page never sells a feature that ships off.
 */
export default function ProDepth() {
  const extras = ENABLE_ANALYSIS ? EXTRAS : EXTRAS.filter((extra) => extra.title !== EXCEL_EXTRA)
  return (
    <LandingRow
      id="pro"
      title="More ways to read one filing."
      line={
        ENABLE_ANALYSIS
          ? 'Ask it a question, read its periods side by side, see what changed since the last one.'
          : 'Ask it a question, then see what changed since the last one.'
      }
      impression="pro_depth"
    >
      <div className="divide-y divide-border-light dark:divide-white/10">
        <FeatureRow
          title="Ask this Filing"
          pro
          description={`Ask a question of one filing. The answer comes from that filing, with cited passages you can check, and each chip says whether we matched the source or only cited it. Free accounts get ${FREE_COPILOT_QUESTIONS} questions.`}
        >
          <AskFilingDemo />
        </FeatureRow>

        {ENABLE_ANALYSIS && (
          <FeatureRow
            title="Multi-Period Analysis"
            pro
            description={`Up to ${ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years or ${ANALYSIS_MAX_QUARTERLY_PERIODS} quarters of one company: charts, a metrics grid, and a streamed trend narrative with citations. Export to Excel.`}
            cta={
              <MarketingCta variant="secondary" size="md" href="/analysis?ticker=AAPL" className="mt-4">
                Try it on Apple
                <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
              </MarketingCta>
            }
          >
            <AnalysisDemo />
          </FeatureRow>
        )}

        <FeatureRow
          title="Change Report"
          description="What changed against the prior filing: metric deltas computed from XBRL, risk factors that are new, and language no longer cited. Both plans include it."
        >
          <ChangeReportDemo />
        </FeatureRow>
      </div>

      <div className="mt-12 border-t border-border-light pt-8 dark:border-white/10">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h3 className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Also in Pro</h3>
          <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Watchlists are unlimited on both plans.
          </span>
        </div>
        <ul className="mt-4 grid grid-cols-1 gap-x-10 [@media(min-width:40rem)]:grid-cols-2">
          {extras.map((extra) => (
            <li key={extra.title} className="flex flex-col gap-1 border-t border-border-light py-4 dark:border-white/10">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h4 className="text-base leading-5">{extra.title}</h4>
                <span className="font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                  {extra.tags.map((tag, index) => (
                    <Fragment key={tag}>
                      {index > 0 && (
                        <>
                          {' '}
                          <span aria-hidden="true">·</span>{' '}
                        </>
                      )}
                      <span className="whitespace-nowrap">{tag}</span>
                    </Fragment>
                  ))}
                </span>
              </div>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{extra.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </LandingRow>
  )
}

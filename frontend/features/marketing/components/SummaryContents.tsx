import { Card, CardHeader, CardTitle } from '@/components/ui/Card'
import HowItWorks from '@/features/marketing/components/HowItWorks'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import { SAMPLE_FILING } from '@/features/marketing/lib/landing-samples'

/** The nine summary sections as the schema names them (backend/app/services/summary_schema.py,
 *  SECTION_SPECS), in its order. The live page adds "What changed" from the change report and omits a
 *  part the filing has nothing for (Segments), so this list is the outline, not one filing's rail. */
const SECTIONS = [
  'The Print',
  'Results That Matter',
  'Earnings Quality & Cash Conversion',
  'Value Drivers & Capital Allocation',
  'Forward Signals',
  'Risks',
  'Segments',
  'Balance Sheet & Liquidity',
  'Notable Footnotes',
] as const

// The contents card is labelled with the same sample filing every product screen on the page uses.
const FILING_NOTE = `${SAMPLE_FILING.companyName} · ${SAMPLE_FILING.filingType} · ${SAMPLE_FILING.fiscalYear}`

/**
 * "What a summary contains" (design section 5): the intro, a contents card listing the nine
 * sections as a navigation landmark, and the compact how-it-works row beneath it. The design
 * opens this section with no hairline and no top padding: it continues straight on from the
 * Evidence section's bottom padding, and the next hairline belongs to Pro Depth.
 */
export default function SummaryContents() {
  return (
    <section id="contents" aria-labelledby="contents-h" className="pb-20 sm:pb-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="summary_contents">
          <div className="max-w-2xl">
            <h2 id="contents-h" className="text-3xl lg:text-4xl">
              Nine parts, in the order you would read them.
            </h2>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
              Every summary follows the same outline, so the second filing reads faster than the
              first. A fresh summary appears part by part while it is written; a cached one loads at
              once.
            </p>
          </div>

          <Card as="nav" aria-label="Summary sections" className="mt-10 overflow-hidden">
            <CardHeader className="flex-wrap justify-between gap-x-3 gap-y-2">
              <CardTitle>Contents</CardTitle>
              <span className="whitespace-nowrap font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                {FILING_NOTE}
              </span>
            </CardHeader>
            <ol className="grid grid-cols-1 gap-x-6 px-3 py-2 sm:grid-cols-2">
              {SECTIONS.map((name, index) => (
                <li
                  key={name}
                  className="flex items-center gap-3.5 border-b border-border-light px-2 py-3 dark:border-white/10"
                >
                  <span className="w-5 shrink-0 font-data tnum text-xs text-text-secondary-light dark:text-text-secondary-dark">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="text-base font-medium text-text-primary-light dark:text-text-primary-dark">
                    {name}
                  </span>
                </li>
              ))}
            </ol>
          </Card>

          <div className="mt-8">
            <HowItWorks />
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}

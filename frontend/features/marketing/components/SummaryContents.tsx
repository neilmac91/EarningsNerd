import HowItWorks from '@/features/marketing/components/HowItWorks'
import LandingRow from '@/features/marketing/components/LandingRow'

/** The nine summary sections as the schema names them (backend/app/services/summary_schema.py,
 *  SECTION_META), in its order. The live page adds "What changed" from the change report and omits a
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

// The list is the schema's outline, not one filing's rail (the Apple sample omits Segments), so it is
// labelled as the outline: a filing shows up to these nine.
const OUTLINE_NOTE = 'Up to nine parts'

/**
 * "What a summary contains" as a ruled row (D-045): the label column's line is one short sentence, and what follows
 * from it opens the content column, above the contents as a navigation landmark, a hairline list in the filing's
 * own table-of-contents manner rather than a card, two across from 40rem at the reader's text size, then the
 * compact how-it-works steps beneath it.
 */
export default function SummaryContents() {
  return (
    <LandingRow
      id="contents"
      title="Nine parts, in the order you would read them."
      line="Every summary follows the same outline."
      impression="summary_contents"
    >
      <p className="mb-6 max-w-2xl text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
        The second filing reads faster than the first, and a part the filing has nothing for is left out. A fresh
        summary appears part by part while it is written; a cached one loads at once.
      </p>
      <nav aria-label="Summary sections">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2 pb-3">
          <h3 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Contents</h3>
          <span className="whitespace-nowrap font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
            {OUTLINE_NOTE}
          </span>
        </div>
        <ol className="grid grid-cols-1 gap-x-8 border-t border-border-light dark:border-white/10 [@media(min-width:40rem)]:grid-cols-2">
          {SECTIONS.map((name, index) => (
            <li
              key={name}
              className="flex items-center gap-3.5 border-b border-border-light py-3 dark:border-white/10"
            >
              <span className="w-5 shrink-0 font-data tnum text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className="min-w-0 text-base font-medium text-text-primary-light dark:text-text-primary-dark">
                {name}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      <div className="mt-10">
        <HowItWorks />
      </div>
    </LandingRow>
  )
}

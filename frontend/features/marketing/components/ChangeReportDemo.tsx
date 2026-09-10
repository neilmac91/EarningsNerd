import { Skeleton } from '@/components/ui/Skeleton'
import { WhatChanged } from '@/features/filings/components/WhatChanged'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'

const EYEBROW = 'mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em]'
const SKELETON_LABEL = 'Risk factor text loads from the live report'

/**
 * The Change Report product screen for the landing page: the REAL WhatChanged component fed
 * static FY2022-vs-FY2021 XBRL deltas. WhatChanged draws its own card chrome; inside the frame
 * that would read as a card within a card, so the wrapper flattens it (radius, hairline, shadow
 * and fill), leaving the frame as the only chrome. The risk-factor columns are left to the live
 * report (the sample carries none), so they render as skeleton bones with the design's +/- glyphs.
 * Raw <Skeleton> bones are aria-hidden; each column's wrapper carries the role and label instead
 * (DESIGN_SYSTEM §4).
 */
export default function ChangeReportDemo() {
  return (
    <div className="mockup-frame shadow-e3 dark:shadow-none" data-capture="change-report">
      <div className="[&>section]:rounded-none [&>section]:border-0 [&>section]:bg-transparent [&>section]:shadow-none dark:[&>section]:bg-transparent">
        <WhatChanged report={SAMPLE_CHANGE_REPORT} headingLevel="h4" />
      </div>

      <div className="grid gap-4 px-6 pb-6 sm:grid-cols-2">
        <div>
          <div className={`${EYEBROW} text-text-tertiary-light dark:text-text-secondary-dark`}>New risk factors</div>
          <div role="status" aria-label={SKELETON_LABEL} className="flex flex-col gap-2">
            {['w-[88%]', 'w-[70%]'].map((width) => (
              <div key={width} className="flex items-center gap-2">
                <span aria-hidden="true" className="text-text-tertiary-light dark:text-text-secondary-dark">
                  +
                </span>
                <Skeleton className={`h-3 ${width}`} />
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className={`${EYEBROW} text-brand-strong dark:text-brand-strong-dark`}>No longer cited</div>
          <div role="status" aria-label={SKELETON_LABEL} className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className="text-brand-strong dark:text-brand-strong-dark">
                −
              </span>
              <Skeleton className="h-3 w-[76%]" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

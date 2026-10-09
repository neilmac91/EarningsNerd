import { WhatChanged } from '@/features/filings/components/WhatChanged'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'

/**
 * The Change Report product screen for the landing page: the REAL WhatChanged component fed static
 * FY2022-vs-FY2021 XBRL deltas. WhatChanged draws its own card chrome; inside the frame that would
 * read as a card within a card, so the wrapper flattens it (radius, hairline, shadow and fill),
 * leaving the frame as the only chrome.
 *
 * No placeholder risk columns (design review 2026-10-08): the sample carries no risk lines, so none
 * render. A sales surface never shows a loading state that cannot resolve. When verbatim risk lines
 * are captured from the live report, add them to SAMPLE_CHANGE_REPORT.risks and WhatChanged renders
 * them like any payload.
 */
export default function ChangeReportDemo() {
  return (
    <div className="mockup-frame shadow-e3 dark:shadow-none" data-capture="change-report">
      <div className="[&>section]:rounded-none [&>section]:border-0 [&>section]:bg-transparent [&>section]:shadow-none dark:[&>section]:bg-transparent">
        <WhatChanged report={SAMPLE_CHANGE_REPORT} headingLevel="h4" />
      </div>
    </div>
  )
}

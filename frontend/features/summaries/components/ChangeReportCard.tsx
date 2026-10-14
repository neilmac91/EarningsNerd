'use client'

import { type ChangeReport } from '@/features/summaries/api/summaries-api'
import { WHAT_CHANGED_ID, WhatChanged, reportHasContent } from '@/features/filings/components/WhatChanged'
import type { WordingContext } from '@/features/filings/components/WordingChanges'
import { useSectionArrival } from '@/features/summaries/hooks/useSectionArrival'
import { useWhatChanged } from '@/features/summaries/hooks/useWhatChanged'

/**
 * The change report as a card of its own, wherever the filing page has no structured summary to hold
 * it as a section: under a legacy markdown summary, under a stored summary that failed, under the
 * signup gate, and under a run that ended without a summary (an error, the monthly limit). The report
 * is computed from stored XBRL and stored filing text, so it needs no summary. The card carries the
 * section's id and lands a link that names it (the company page's "Open change report"), as the
 * section would. It shares the section's read (useWhatChanged: the viewer's own entry, seeded from
 * the page's server read), so a seeded or cached report shows at once. Renders nothing unless the
 * report has something to say.
 */
export function ChangeReportCard({
  filingId,
  initialReport,
  context,
}: {
  filingId: number
  initialReport?: ChangeReport
  /** Who is reading, for the wording block; the card marks the seed as provisional itself. */
  context?: Omit<WordingContext, 'provisional'>
}) {
  const { report, provisional } = useWhatChanged(filingId, initialReport)
  const shown = reportHasContent(report)
  useSectionArrival(shown ? WHAT_CHANGED_ID : '')
  return shown && report ? <WhatChanged report={report} id={WHAT_CHANGED_ID} context={context && { ...context, provisional }} /> : null
}

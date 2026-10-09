'use client'

import { useQuery } from '@tanstack/react-query'
import { getWhatChanged, type ChangeReport } from '@/features/summaries/api/summaries-api'
import { WHAT_CHANGED_ID, WhatChanged } from '@/features/filings/components/WhatChanged'
import { useSectionArrival } from '@/features/summaries/hooks/useSectionArrival'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The change report as a card of its own, wherever the filing page has no structured summary to hold
 * it as a section: under a legacy markdown summary, under the signup gate, and under a run that ended
 * without a summary (an error, the monthly limit). The report is computed from stored XBRL, so it
 * needs no summary. The card carries the section's id and lands a link that names it (the company
 * page's "Open change report"), as the section would. It shares the section's GET and query key, so a
 * seeded or cached report shows at once. Renders nothing unless the report has something to say.
 */
export function ChangeReportCard({ filingId, initialReport }: { filingId: number; initialReport?: ChangeReport }) {
  const { data: report } = useQuery({
    queryKey: queryKeys.whatChanged(filingId),
    queryFn: () => getWhatChanged(filingId),
    staleTime: 10 * 60 * 1000,
    initialData: initialReport,
  })
  const shown = Boolean(report?.has_changes)
  useSectionArrival(shown ? WHAT_CHANGED_ID : '')
  return shown && report ? <WhatChanged report={report} id={WHAT_CHANGED_ID} /> : null
}

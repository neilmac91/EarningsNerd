'use client'

import { Fragment, type ReactNode } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { ANALYSIS_MODE_LABEL, formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { useSourceDate } from '@/features/analysis/lib/useSourceDate'
import { formatCompanyName } from '@/lib/formatCompanyName'

/**
 * The results header (coherence §4.1 N1, §4.4): one line on the page ground, no card, at the top of a run's results,
 * tying the KPI strip, the charts, the commentary and the table below it to their run. Every clause comes from the
 * dataset on screen, never the picker, which the reader may have changed since running: the company's display name
 * (formatCompanyName), its ticker in the data face as the page's company row sets it, the mode with the period range
 * the chart PNG header prints (formatAnalysisPeriod of the run's window), and the source data's day as the data notes
 * print it (useSourceDate). "Regeneron Pharmaceuticals, Inc. · REGN · Annual FY2016–FY2025 · data as of October 24,
 * 2026".
 *
 * It labels the results' region (the page passes `id` to the section's aria-labelledby), so the module headings keep
 * their level: each stays an h2 under the page h1. A phone wraps it between clauses, never inside one: each clause is
 * an inline-block that carries the separator after it, joined to its last word by a no-break space, so a line ends on
 * "·" and none starts with it; a clause wraps inside itself only where it alone is wider than the line (a long name
 * under 200% text). The floating feedback launcher steps aside from it as from the KPI strip under it
 * (lib/launcherKeepClear): at 390x844 a run made after a 60px scroll lands the header, not the strip, under the
 * launcher, which rested opaque over "Quarterly" and "data as of" there. Only the page renders it: the Free teaser's
 * caption and the landing demo's title bar name their sample, and a sample has no live date to print. Gates: tests/unit/analysis-results-header.spec.tsx, and
 * tests/e2e/analysis-layout.spec.ts "analysis results header" (12px over the KPI strip, clauses whole on a phone).
 */
export default function ResultsHeader({ dataset, id }: { dataset: AnalysisDataset; id: string }) {
  const sourceDate = useSourceDate(dataset.data_as_of)
  const company = formatCompanyName(dataset.company_name)
  const clauses: ReactNode[] = [
    ...(company ? [<span key="company" className="font-semibold text-text-primary-light dark:text-text-primary-dark">{company}</span>] : []),
    <span key="ticker" className="tnum font-data">{dataset.ticker}</span>,
    `${ANALYSIS_MODE_LABEL[dataset.mode]} ${formatAnalysisPeriod(dataset.period_key)}`,
    sourceDate ? `data as of ${sourceDate}` : 'source refresh time unavailable',
  ]
  return (
    <p id={id} className="text-sm text-text-secondary-light dark:text-text-secondary-dark" data-analysis-results-header data-launcher-keep-clear>
      {clauses.map((clause, index) => (
        <Fragment key={index}>
          {index > 0 && ' '}
          <span className="inline-block max-w-full" data-results-clause>
            {clause}
            {index < clauses.length - 1 && '\u00A0·'}
          </span>
        </Fragment>
      ))}
    </p>
  )
}

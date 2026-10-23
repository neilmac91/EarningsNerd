import { Fragment } from 'react'
import { Card, CardTitle } from '@/components/ui/Card'
import FormCodeText from '@/features/marketing/components/FormCodeText'
import { ArrowSquareOutIcon, BracketsCurlyIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { FIGURE_LINKED, FIGURE_MATCHED } from '@/features/filings/lib/evidenceLabels'
import { sourceTraceLabelClass } from '@/features/filings/lib/sourceTraceChip'
import { formatMetricValue } from '@/features/summaries/lib/metricValue'
import type { FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'
import type { SAMPLE_RECEIPT } from '@/features/marketing/lib/landing-samples'

const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const SCALE_WORDS: Record<string, string> = { T: 'trillions', B: 'billions', M: 'millions', K: 'thousands' }

/**
 * "Follow one figure to the filing" (the founder's review, 2026-10-22; it replaces the catch card, which struck
 * through a correct filed figure): one row of the highlights traced, step by step, to the line the 10-K prints and the
 * value its data tags, so "Matches filing" is shown being checked rather than asserted. Step one is the row exactly as
 * the table shows it; the rest are read from the filing (SAMPLE_RECEIPT). It says what the table cannot: the figure in
 * the filing's own units, the company's own name for the line, its statement and page, and the period's end.
 *
 * Each step reads down: its label, the amount, a note. An amount breaks only after a thousands separator or at a space,
 * never inside a digit group, so no line reads "416,161,000,00" over "0" (320px under a 200% root font; chief design on
 * #1530): tests/e2e/figure-receipt-reflow.spec.ts. A form code stays whole (FormCodeText; tests/e2e/reflow-200.spec.ts).
 */

/** An amount with a break opportunity after each thousands separator and nowhere else inside its digits. */
const groupedFigure = (figure: string) =>
  figure.split(',').map((group, i, groups) => (
    <Fragment key={i}>
      {group}
      {i < groups.length - 1 && (
        <>
          ,<wbr />
        </>
      )}
    </Fragment>
  ))
export default function FigureReceipt({
  row,
  receipt,
  company,
  form,
  fiscalYear,
}: {
  row: FinancialMetric
  receipt: typeof SAMPLE_RECEIPT
  company: string
  form: string
  fiscalYear: string
}) {
  const shown = formatMetricValue(row.current_period)
  const scale = SCALE_WORDS[shown.slice(-1)]
  const matched = row.source_verified === true
  // The product chip's glyph for the state (SourceTrace): braces for a matched figure, the link arrow for a linked one.
  const Glyph = matched ? BracketsCurlyIcon : ArrowSquareOutIcon
  const steps = [
    { label: 'In the highlights', figure: shown, note: scale ? `${fiscalYear}, rounded to ${scale}` : fiscalYear },
    { label: `In ${company}’s ${form}`, figure: receipt.filed, note: `${receipt.statement} · page ${receipt.page}` },
    {
      label: 'In the filing’s data',
      figure: `${receipt.tagged} ${receipt.currency}`,
      note: `Year ended ${formatLocalDate(receipt.periodEnd, 'MMM d, yyyy')}`,
    },
  ]

  return (
    <Card className="p-cap-5">
      <CardTitle>Follow one figure to the filing</CardTitle>
      <p className={`mt-1.5 text-sm ${MUTED}`}>
        {row.metric} in the table above, traced to the line {company} filed.
      </p>
      <ol className="mt-4 space-y-3">
        {steps.map((step) => (
          <li key={step.label} className="min-w-0">
            <p className="text-xs font-medium text-text-primary-light dark:text-text-primary-dark">
              <FormCodeText text={step.label} />
            </p>
            <p className="font-data text-base font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
              {groupedFigure(step.figure)}
            </p>
            <p className={`text-xs ${MUTED}`}>{step.note}</p>
          </li>
        ))}
      </ol>
      <details className={`mt-3 text-xs ${MUTED}`}>
        <summary className="cursor-pointer rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          Show the data tag
        </summary>
        <p className="mt-1 break-all font-data">{receipt.tag}</p>
      </details>
      <p className={`mt-3 flex flex-wrap items-center gap-2 text-sm ${MUTED}`}>
        <span className={sourceTraceLabelClass()}>
          <Glyph className="h-3 w-3 shrink-0" aria-hidden="true" />
          {matched ? FIGURE_MATCHED : FIGURE_LINKED}
        </span>
        {matched ? (scale ? `Same number, rounded to ${scale}.` : 'Same number.') : 'This figure is linked, not checked.'}
      </p>
      <a
        href={receipt.url}
        target="_blank"
        rel="noopener noreferrer"
        className={`mt-3 inline-flex items-center gap-1 rounded-sm text-sm font-medium ${MUTED} transition-colors hover:text-brand-strong focus-visible:outline-none focus-visible:shadow-ring-brand dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark`}
      >
        <ArrowSquareOutIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          <FormCodeText text={`Open the ${form} on SEC.gov`} />
        </span>
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    </Card>
  )
}

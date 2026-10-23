import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import LandingRow from '@/features/marketing/components/LandingRow'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import FigureReceipt from '@/features/marketing/components/FigureReceipt'
import FormCodeText from '@/features/marketing/components/FormCodeText'
import { ArrowSquareOutIcon, BracketsCurlyIcon, QuotesIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { FIGURE_LINKED, FIGURE_MATCHED, PASSAGE_FOUND } from '@/features/filings/lib/evidenceLabels'
import { sourceTraceLabelClass } from '@/features/filings/lib/sourceTraceChip'
import { SAMPLE_FILING, SAMPLE_FINANCIAL_METRICS, SAMPLE_RECEIPT, SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'

const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const day = (iso: string) => formatLocalDate(iso, 'MMM d, yyyy')
/** "Apple Inc." -> "Apple": the company as the legend's sentences name it. */
const COMPANY = SAMPLE_FILING.companyName.replace(/[,\s]+(?:Inc|Corp|Corporation|Co|Ltd|plc|LLC)\.?$/i, '')

// What each label means, in the order a reader meets them in the table, each beside the label itself. The figure
// check's scope is stated here once (docs/voice-and-style.md, "Scope once, as a behaviour").
const LEGEND = [
  {
    label: FIGURE_MATCHED,
    Icon: BracketsCurlyIcon,
    meaning: `Both years’ figures match the numbers ${COMPANY} reported in the filing’s data, after rounding.`,
  },
  {
    label: FIGURE_LINKED,
    Icon: ArrowSquareOutIcon,
    meaning: 'We link to where the figure is reported but don’t check it. We don’t check per-share figures, ratios or segment results.',
  },
  { label: PASSAGE_FOUND, Icon: QuotesIcon, meaning: 'The quoted words appear in the filing, word for word.' },
] as const

const TABLE_NOTES = 'Amounts in US dollars; B = billions.'
const CHANGE_NOTE = `Calculated from the two figures, to one decimal. ${COMPANY}’s filing rounds changes to whole percentages.`

/**
 * "Figures with their receipts": the evidence row of the landing page (D-045), rebuilt on the founder's review of
 * 2026-10-22 (tasks/evidence-row-ux-plan-2026-10-22.md). The label column's line says what the labels are for; the
 * content column opens with what each label means, shown beside the label itself, then the sample's filing identity,
 * the REAL FinancialMetricsTable fed four of the live example's own rows (landing-example.json, snapshotted by
 * scripts/snapshot-landing-example.mjs), and beneath it the Trace-to-Source demo on one of those rows' takeaways and
 * one figure followed to the line the filing prints. Nothing here is fetched at request time; see landing-samples.
 */
export default function EvidenceSection() {
  const receiptRow = SAMPLE_FINANCIAL_METRICS.find((row) => row.metric === SAMPLE_RECEIPT.metric)

  return (
    <LandingRow
      id="evidence"
      title="Figures with their receipts."
      line="Each label says what we checked, and each link opens the filing."
      impression="evidence"
    >
      <h3 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">What the labels mean</h3>
      <dl className="mt-3 max-w-2xl space-y-3">
        {LEGEND.map(({ label, Icon, meaning }) => (
          <div key={label} className="grid grid-cols-1 gap-1 [@media(min-width:40rem)]:grid-cols-[12.5rem_minmax(0,1fr)] [@media(min-width:40rem)]:gap-3">
            <dt>
              <span className={sourceTraceLabelClass()}>
                <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
                {label}
              </span>
            </dt>
            <dd className={`text-sm leading-relaxed ${MUTED}`}>{meaning}</dd>
          </div>
        ))}
      </dl>
      <details className={`mt-4 max-w-2xl text-sm ${MUTED}`}>
        <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
          How we check
        </summary>
        <p className="mt-2 leading-relaxed">
          Companies file their financial statements with machine-readable tags on the figures, a format called XBRL. We
          compare the figures we can check with {COMPANY}’s tagged values for the same line and year: rounding is
          allowed, a different scale or digit is not, and where our figure differs we show the filed one instead. Quotes
          are matched word for word, ignoring capital letters, spacing and quote styles. The investor takeaways are
          interpretation; where one cites a passage, its label says whether the passage was found.
        </p>
      </details>
      <p className={`mb-2 mt-8 font-data text-xs ${MUTED}`}>
        <FormCodeText
          text={`Sample filing · ${SAMPLE_FILING.companyName} (${SAMPLE_FILING.ticker}) · ${SAMPLE_FILING.filingType} · fiscal year ended ${day(SAMPLE_FILING.periodEnd)} · filed ${day(SAMPLE_FILING.filed)}`}
        />
      </p>
      <FinancialMetricsTable
        metrics={SAMPLE_FINANCIAL_METRICS}
        notes={TABLE_NOTES}
        changeNote={CHANGE_NOTE}
        periods={{
          current: { label: SAMPLE_FILING.fiscalYear, detail: `to ${day(SAMPLE_FILING.periodEnd)}` },
          prior: { label: SAMPLE_FILING.priorFiscalYear, detail: `to ${day(SAMPLE_FILING.priorPeriodEnd)}` },
        }}
        caption={`${SAMPLE_FILING.companyName} financial highlights for ${SAMPLE_FILING.fiscalYear} and ${SAMPLE_FILING.priorFiscalYear}: figures, change and investor takeaway`}
        layoutBy="container"
      />
      {/* The demo and the receipt side by side from 48rem at the reader's text size, one above the other below it:
          each holds words and a figure that cannot shrink below their own width. */}
      <div className="mt-6 grid grid-cols-1 gap-6 [@media(min-width:48rem)]:grid-cols-2">
        <TraceToSourceDemo trace={SAMPLE_TRACE} />
        {receiptRow && (
          <FigureReceipt
            row={receiptRow}
            receipt={SAMPLE_RECEIPT}
            company={COMPANY}
            form={SAMPLE_FILING.filingType}
            fiscalYear={SAMPLE_FILING.fiscalYear}
          />
        )}
      </div>
    </LandingRow>
  )
}

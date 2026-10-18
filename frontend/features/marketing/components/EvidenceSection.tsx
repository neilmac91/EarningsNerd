import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import LandingRow from '@/features/marketing/components/LandingRow'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import CatchCard from '@/features/marketing/components/CatchCard'
import { SAMPLE_CATCH, SAMPLE_FILING, SAMPLE_FINANCIAL_METRICS, SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'

// The card footer explains the one row that does not read SEC XBRL (the lead beside it already says what
// each label means); FinancialMetricsTable renders it in its own CardFooter.
const TABLE_NOTES = 'Diluted EPS reads Cited: per-share figures are not matched to XBRL.'

/**
 * "Figures with their receipts": the evidence row of the landing page (D-045). The REAL
 * FinancialMetricsTable fed static, XBRL-verified sample rows takes the content column's width; beneath
 * it, the Trace-to-Source chip with its provenance panel open and the catch: the figure a reader
 * remembers beside the one in the filing, two real years of one XBRL fact. Nothing here is drawn live;
 * see landing-samples.
 */
export default function EvidenceSection() {
  return (
    <LandingRow
      id="evidence"
      title="Figures with their receipts."
      line="Each row in the highlights carries a label: SEC XBRL when its value matched the company’s XBRL fact, Cited when it points to the filing without that match. A quote reads Verified in filing only when its words were found there."
      impression="evidence"
    >
      {/* FinancialMetricsTable owns its card header, so the period note renders as a data-register line
          above the card instead of inside it. */}
      <p className="mb-2 flex items-center justify-end font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
        <span className="sr-only">Periods compared: </span>
        {`${SAMPLE_FILING.fiscalYear} vs ${SAMPLE_FILING.priorFiscalYear}`}
      </p>
      <FinancialMetricsTable metrics={SAMPLE_FINANCIAL_METRICS} notes={TABLE_NOTES} />
      {/* The trace and the catch side by side from 48rem at the reader's text size, one above the other below it:
          each holds words and a figure that cannot shrink below their own width. */}
      <div className="mt-6 grid grid-cols-1 gap-6 [@media(min-width:48rem)]:grid-cols-2">
        <TraceToSourceDemo trace={SAMPLE_TRACE} />
        <CatchCard sample={SAMPLE_CATCH} />
      </div>
    </LandingRow>
  )
}

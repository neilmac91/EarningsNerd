import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import CatchCard from '@/features/marketing/components/CatchCard'
import { SAMPLE_CATCH, SAMPLE_FILING, SAMPLE_FINANCIAL_METRICS, SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'

// The design's card footer sentence; FinancialMetricsTable renders it in its own CardFooter.
const TABLE_NOTES = (
  <>
    Each row carries its own source label. A metric reads{' '}
    <span className="font-data text-brand-strong dark:text-brand-strong-dark">SEC XBRL</span> only when the
    value matched the SEC-filed XBRL figure.
  </>
)

/**
 * "Figures with their receipts": the evidence block of the landing page. Left, the REAL
 * FinancialMetricsTable fed static, XBRL-verified sample rows; right, the Trace-to-Source chip
 * with its provenance panel open and, beneath it, the catch: the figure a reader remembers beside
 * the one in the filing, two real years of one XBRL fact. Nothing here is drawn live; see
 * landing-samples.
 */
export default function EvidenceSection() {
  // No hairline of its own: the measured-claims strip above already draws one.
  return (
    <section id="evidence" aria-labelledby="evidence-h" className="py-20 sm:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="evidence">
          <div className="max-w-2xl">
            <h2 id="evidence-h" className="text-3xl lg:text-4xl">
              Figures with their receipts.
            </h2>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
              Each figure carries a label that says whether it matched the company’s XBRL. Each quote
              carries the passage it came from. Where we could not match one, we say so.
            </p>
          </div>

          {/* The real five-column table needs the wider column; the trace card takes the rest. */}
          <div className="mt-10 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="min-w-0">
              {/* FinancialMetricsTable owns its card header, so the design's right-aligned period
                  note renders as a data-register line above the card instead of inside it. */}
              <p className="mb-2 flex items-center justify-end font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                <span className="sr-only">Periods compared: </span>
                {`${SAMPLE_FILING.fiscalYear} vs ${SAMPLE_FILING.priorFiscalYear}`}
              </p>
              <FinancialMetricsTable metrics={SAMPLE_FINANCIAL_METRICS} notes={TABLE_NOTES} />
            </div>
            <div className="flex min-w-0 flex-col gap-6">
              <TraceToSourceDemo trace={SAMPLE_TRACE} />
              <CatchCard sample={SAMPLE_CATCH} />
            </div>
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}

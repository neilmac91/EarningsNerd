import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import { SAMPLE_FILING, SAMPLE_FINANCIAL_METRICS, SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'

// The design's card footer sentence; FinancialMetricsTable renders it in its own CardFooter.
const TABLE_NOTES =
  'Each row carries its own source label. A metric reads SEC XBRL only when the value matched the SEC-filed XBRL figure.'

/**
 * "Where the numbers come from": the evidence block of the landing page. Left, the REAL
 * FinancialMetricsTable fed static, XBRL-verified sample rows; right, the Trace-to-Source chip
 * with its provenance panel open. Nothing here is drawn live; see landing-samples.
 */
export default function EvidenceSection() {
  return (
    <section
      id="evidence"
      aria-labelledby="evidence-h"
      className="border-t border-border-light py-20 dark:border-white/10 sm:py-24"
    >
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="evidence">
          <div className="max-w-2xl">
            <h2 id="evidence-h" className="text-3xl lg:text-4xl">
              Where the numbers come from
            </h2>
            <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark">
              Every figure is matched to the filing&apos;s own XBRL data. Every claim links to the
              passage it came from. Nothing is drawn from outside the document you chose.
            </p>
          </div>

          {/* The real five-column table needs the wider column; the trace card takes the rest. */}
          <div className="mt-10 grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="min-w-0">
              {/* FinancialMetricsTable owns its card header, so the design's right-aligned period
                  note renders as a data-register line above the card instead of inside it. */}
              <p className="mb-2 flex items-center justify-end font-data text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
                <span className="sr-only">Periods compared: </span>
                {`${SAMPLE_FILING.fiscalYear} vs ${SAMPLE_FILING.priorFiscalYear}`}
              </p>
              <FinancialMetricsTable metrics={SAMPLE_FINANCIAL_METRICS} notes={TABLE_NOTES} />
            </div>
            <TraceToSourceDemo trace={SAMPLE_TRACE} />
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}

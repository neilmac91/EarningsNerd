import SectionImpression from '@/features/marketing/components/SectionImpression'

/**
 * Four bounded product capabilities. These describe supported behavior without turning one
 * evaluation corpus or one latency observation into a universal quality promise.
 */
const CLAIMS = [
  {
    figure: '9-part format',
    label: 'A consistent outline spanning financials, risks, strategy, liquidity, and footnotes',
  },
  { figure: 'Streams', label: 'Fresh summaries appear section by section while generation runs' },
  {
    figure: 'XBRL + text',
    label: 'Source labels distinguish matched financial data from cited filing passages',
  },
  { figure: '10-K · 10-Q', label: 'Core filing types retrieved from SEC EDGAR' },
] as const

/**
 * Product capabilities strip (landing section 3): a full-width band between two hairlines
 * holding a definition list of figure + label pairs. No icons, no card chrome: the figure in the
 * data face carries the weight, and the label beneath it explains the capability.
 */
export default function MeasuredClaims() {
  return (
    <section aria-label="Product capabilities" className="border-y border-border-light dark:border-white/10">
      <div className="mx-auto max-w-5xl px-4 py-7 sm:px-6 lg:px-8 lg:py-10">
        <SectionImpression section="measured_claims">
          <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:gap-10">
            {CLAIMS.map((claim) => (
              <div key={claim.figure} className="flex min-w-0 flex-col gap-1.5">
                <dt className="font-data tnum text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark lg:text-3xl">
                  {claim.figure}
                </dt>
                <dd className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{claim.label}</dd>
              </div>
            ))}
          </dl>
        </SectionImpression>
      </div>
    </section>
  )
}

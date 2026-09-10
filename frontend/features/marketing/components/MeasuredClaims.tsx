import SectionImpression from '@/features/marketing/components/SectionImpression'

/**
 * The four claims the product can back with a measurement (design/landing-redesign/RATIONALE.md,
 * "Measured-claims strip publishes"): eval-set numeric accuracy, streaming time, the XBRL trace and
 * SEC EDGAR coverage. Copy is verbatim from the design data block. Citation fidelity is
 * deliberately not on the page.
 */
const CLAIMS = [
  { figure: '100%', label: 'Numeric accuracy against XBRL on a 26-filing evaluation set, 3 runs each' },
  { figure: '~30 s', label: 'From a fresh filing to a streamed nine-section summary' },
  { figure: 'XBRL', label: 'Every financial figure traced to the filing’s SEC XBRL data' },
  { figure: '10-K · 10-Q · 20-F', label: 'Pulled from SEC EDGAR for every company that files with the SEC' },
] as const

/**
 * Measured claims strip (landing section 3): a full-width band between two hairlines holding a
 * definition list of figure + label pairs. No icons, no card chrome: the figure in the data face
 * carries the weight, the label beneath it says what was measured.
 */
export default function MeasuredClaims() {
  return (
    <section aria-label="Measured claims" className="border-y border-border-light dark:border-white/10">
      <div className="mx-auto max-w-5xl px-4 py-7 sm:px-6 lg:px-8 lg:py-10">
        <SectionImpression section="measured_claims">
          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:gap-10">
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

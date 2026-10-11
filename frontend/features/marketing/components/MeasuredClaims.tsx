import SectionImpression from '@/features/marketing/components/SectionImpression'

/**
 * Four behaviours in the product's own words (docs/brand/03-strategy.md, S2): what a summary does
 * with a figure, a quote, its own scope and its source. No invented statistics: the lead of each
 * pair is the subject, set in the data face, and the label is the behaviour the product performs.
 */
const CLAIMS = [
  { figure: 'Figures', label: 'Matched to the company\u2019s XBRL where the server can check them, or counted as unmatched' },
  { figure: 'Quotes', label: 'Located in the filing text, in the filing\u2019s own words, or withheld' },
  { figure: 'Nine parts', label: 'One outline for every 10-K and 10-Q, from The Print to Notable Footnotes, skipping any part the filing has nothing for' },
  { figure: 'SEC EDGAR', label: 'Every summary links to the original filing, one click away' },
] as const

/**
 * Behaviours strip (landing section 3): a full-width band between two hairlines holding a
 * definition list of subject + behaviour pairs. No icons, no card chrome: the subject in the data
 * face carries the weight, and the label beneath it says what the product does with it.
 */
export default function MeasuredClaims() {
  return (
    <section aria-label="What a summary does" className="border-y border-border-light dark:border-white/10">
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

import FormCodeText from '@/features/marketing/components/FormCodeText'
import LandingRow from '@/features/marketing/components/LandingRow'

/**
 * Four behaviours in the product's own words (docs/brand/03-strategy.md, S2): what a summary does
 * with a figure, a risk excerpt, its own scope and its source. No invented statistics: the lead of
 * each pair is the subject, set in the data face, and the label is the behaviour the product
 * performs. Of a summary's quotes, only risk excerpts are withheld when the filing's text does not
 * match them; a Forward Signals quote stays on the page, labelled Section linked, while
 * AI_FORWARD_QUOTE_GATE is off (brandCopyRules.spec.ts, rule 1c).
 */
const CLAIMS = [
  { figure: 'Figures', label: 'Matched to the company’s filed data where the server can check them, and replaced with the filed figure where they differ' },
  { figure: 'Risks', label: 'Excerpts located in the filing’s own text, or withheld and counted' },
  { figure: 'Nine parts', label: 'One outline for every 10-K and 10-Q, from The Print to Notable Footnotes, skipping any part the filing has nothing for' },
  { figure: 'SEC.gov', label: 'Every summary links to the original filing, one click away' },
] as const

/**
 * The first ruled row after the hero (D-045): a definition list of subject + behaviour pairs, two
 * across from 40rem at the reader's text size and one above another below it, never the four-up strip
 * the template skeleton had (T4). No icons, no card chrome: the subject in the data face carries the
 * weight, and the label beneath it says what the product does with it, each form code in it one unbroken run.
 */
export default function MeasuredClaims() {
  return (
    <LandingRow id="claims" title="What a summary does" impression="measured_claims">
      <dl className="grid grid-cols-1 gap-x-10 gap-y-6 [@media(min-width:40rem)]:grid-cols-2">
        {CLAIMS.map((claim) => (
          <div key={claim.figure} className="flex min-w-0 flex-col gap-1.5">
            <dt className="font-data tnum text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              {claim.figure}
            </dt>
            <dd className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              <FormCodeText text={claim.label} />
            </dd>
          </div>
        ))}
      </dl>
    </LandingRow>
  )
}

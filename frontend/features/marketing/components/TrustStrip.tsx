import { ShieldCheckIcon } from '@/lib/icons'

/**
 * The hero's trust strip (2026-10 critique, homepage 1d): plain statements of what the product does
 * and does not do, set as chrome under the hero rather than as a footnote. Each claim is scoped to
 * what the implementation establishes ("where a match is found"), and "generated" stays distinct
 * from "the filing's own words".
 */
const STATEMENTS = [
  'Figures cite their XBRL fact or filing passage where a match is found',
  'Summaries are generated; quoted excerpts are the filing’s own words',
  'Not investment advice',
]

export default function TrustStrip() {
  return (
    <ul
      aria-label="About the data"
      className="mt-12 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border-light pt-5 text-sm text-text-secondary-light dark:border-white/10 dark:text-text-secondary-dark sm:mt-16"
    >
      <li className="flex items-center gap-1.5 font-medium text-text-primary-light dark:text-text-primary-dark">
        <ShieldCheckIcon aria-hidden="true" className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
        Data sourced from SEC EDGAR
      </li>
      {STATEMENTS.map((statement) => (
        <li key={statement}>{statement}</li>
      ))}
    </ul>
  )
}

import { CheckCircleIcon, InfoIcon } from '@/lib/icons'
import type { VerificationTally } from '@/features/summaries/lib/verificationTally'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/**
 * One data-face line under the filing identity: what the server matched, in scoped words —
 * "6 of 6 highlighted figures matched the company’s XBRL · 3 of 4 risk excerpts located in the
 * filing text · 1 withheld". The check glyph appears only when nothing was left unmatched; otherwise
 * a neutral info glyph, so the icon never claims more than the counts beside it.
 */
export function VerificationTallyLine({ tally }: { tally: VerificationTally }) {
  const { figures, excerpts } = tally
  const complete =
    (!figures || figures.matched === figures.total) && (!excerpts || (excerpts.located === excerpts.total && excerpts.withheld === 0))
  const Icon = complete ? CheckCircleIcon : InfoIcon
  const facts = [
    figures && `${figures.matched} of ${plural(figures.total, 'highlighted figure', 'highlighted figures')} matched the company’s XBRL`,
    excerpts && `${excerpts.located} of ${plural(excerpts.total, 'risk excerpt', 'risk excerpts')} located in the filing text`,
    excerpts && excerpts.withheld > 0 && `${excerpts.withheld} withheld`,
  ].filter((fact): fact is string => Boolean(fact))

  return (
    <p className="mt-1 flex items-start gap-2 font-data text-xs tabular-nums text-text-secondary-light sm:text-sm dark:text-text-secondary-dark">
      <Icon
        aria-hidden="true"
        className={
          complete
            ? 'mt-px h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark'
            : 'mt-px h-4 w-4 shrink-0 text-text-secondary-light dark:text-text-secondary-dark'
        }
      />
      <span>
        {facts.map((fact, i) => (
          <span key={fact}>
            {i > 0 && (
              <>
                <span aria-hidden="true"> · </span>
                <span className="sr-only">, </span>
              </>
            )}
            {fact}
          </span>
        ))}
      </span>
    </p>
  )
}

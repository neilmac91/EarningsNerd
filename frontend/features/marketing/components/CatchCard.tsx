import { Card, CardTitle } from '@/components/ui/Card'
import { BracketsCurlyIcon } from '@/lib/icons'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'
import type { SAMPLE_CATCH } from '@/features/marketing/lib/landing-samples'

/**
 * The catch (docs/brand/04-directions.md, D-012; docs/brand/01-interview.md, A4): the figure a reader
 * remembers beside the one in the filing. Both are real XBRL totals of the same concept from two
 * fiscal years, so no chatbot is named and no wrong number is invented: the remembered figure is
 * simply last year's. The in-filing figure carries the brand device's marker and the product's
 * XBRL chip, so the card is the receipt in miniature.
 */
export default function CatchCard({ sample }: { sample: typeof SAMPLE_CATCH }) {
  return (
    <Card className="p-5">
      <CardTitle>The number you remember</CardTitle>
      <dl className="mt-4 grid grid-cols-2 gap-4">
        <div className="min-w-0">
          <dt className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">From memory</dt>
          <dd className="mt-1 font-data text-2xl font-semibold tabular-nums text-text-tertiary-light line-through decoration-1 dark:text-text-secondary-dark">
            {sample.remembered}
          </dd>
          <dd className="mt-0.5 font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">{sample.rememberedPeriod}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">In the filing</dt>
          <dd className="mt-1 font-data text-2xl font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">
            {sample.inFiling}
          </dd>
          <dd className="mt-0.5 font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">{sample.inFilingPeriod}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
        The first is last year’s {sample.metric.toLowerCase()}. The second is this year’s, with its fact. That is the
        whole point.
      </p>
      <div className="mt-3">
        <a href={sample.url} target="_blank" rel="noopener noreferrer" className={sourceTraceChipClass()}>
          <BracketsCurlyIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
          {sample.metric} · SEC XBRL
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      </div>
    </Card>
  )
}

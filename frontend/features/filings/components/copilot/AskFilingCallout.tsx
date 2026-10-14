'use client'

import { ChatCircleTextIcon } from '@/lib/icons'
import { starterQuestions } from './starterQuestions'
import { COPILOT_CLAIM } from './copilotClaim'
import { Button } from '@/components/ui'

interface AskFilingCalloutProps {
  filingType: string
  /** "AAPL’s 10-K" when the issuer is known, else "this 10-K". */
  subjectLabel: string
  /** Opens the Copilot rail; an empty prefill just opens it (FREE users land on the teaser). */
  onAsk: (prefill: string, surface: string) => void
}

/**
 * End-of-summary discovery surface: a calm, on-brand callout placed directly under the analysis that
 * turns the just-finished read into the next action: ask the filing a question. Doubles as a
 * capability hint via 3 broad starter prompts (NN/g: persistent labeled affordance + suggested
 * prompts is the highest-leverage, lowest-annoyance way to surface a chat feature). FREE users open
 * the same rail and land on the existing upsell teaser, so the gating is preserved.
 */
export default function AskFilingCallout({ filingType, subjectLabel, onAsk }: AskFilingCalloutProps) {
  const starters = starterQuestions(filingType).slice(0, 3)
  // The form code wraps whole: at an enlarged text size "10-K" never breaks at its hyphen.
  const at = subjectLabel.lastIndexOf(filingType)
  const subject =
    at < 0 ? subjectLabel : (
      <>
        {subjectLabel.slice(0, at)}
        <span className="whitespace-nowrap">{filingType}</span>
        {subjectLabel.slice(at + filingType.length)}
      </>
    )

  return (
    <section
      aria-labelledby="ask-filing-callout-heading"
      // An inset well inside the summary (DESIGN.md › Cards): panel fill, one hairline, 8px radius, no
      // shadow; the heading carries the tone, so no icon tile sits beside it.
      className="rounded border border-border-light bg-panel-light dark:border-white/10 dark:bg-panel-dark p-6"
    >
      {/* h2: a sibling of the summary's sections (each an h2), not a subsection of the last one. */}
      <h2
        id="ask-filing-callout-heading"
        className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark"
      >
        Ask {subject} anything
      </h2>
      <p className="mt-0.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {COPILOT_CLAIM} Try one:
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {starters.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onAsk(q, 'summary_starter')}
            className="rounded-full border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 px-3 py-1.5 text-left text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-border hover:text-brand-strong dark:hover:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            {q}
          </button>
        ))}
      </div>
      {/* wrap: at an enlarged text size the label wraps inside the well instead of running past it. */}
      <Button wrap className="mt-4 max-w-full" onClick={() => onAsk('', 'summary_cta')} leftIcon={<ChatCircleTextIcon className="h-4 w-4" aria-hidden="true" />}>
        Ask this filing
      </Button>
    </section>
  )
}

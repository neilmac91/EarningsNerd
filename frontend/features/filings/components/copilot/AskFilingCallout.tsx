'use client'

import { SparkleIcon } from '@/lib/icons'
import { starterQuestions } from './starterQuestions'

interface AskFilingCalloutProps {
  filingType: string
  /** "AAPL’s 10-K" when the issuer is known, else "this 10-K". */
  subjectLabel: string
  /** Opens the Copilot rail; an empty prefill just opens it (FREE users land on the teaser). */
  onAsk: (prefill: string, surface: string) => void
}

/**
 * End-of-summary discovery surface: a calm, on-brand callout placed directly under the analysis that
 * turns the just-finished read into the next action — ask the filing a question. Doubles as a
 * capability hint via 3 broad starter prompts (NN/g: persistent labeled affordance + suggested
 * prompts is the highest-leverage, lowest-annoyance way to surface a chat feature). FREE users open
 * the same rail and land on the existing upsell teaser, so the gating is preserved.
 */
export default function AskFilingCallout({ filingType, subjectLabel, onAsk }: AskFilingCalloutProps) {
  const starters = starterQuestions(filingType).slice(0, 3)

  return (
    <section
      aria-labelledby="ask-filing-callout-heading"
      className="rounded-xl border border-brand-light/30 bg-brand-weak dark:bg-white/5 p-6"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-strong text-white dark:bg-brand-dark dark:text-background-dark">
          <SparkleIcon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h3
            id="ask-filing-callout-heading"
            className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark"
          >
            Ask {subjectLabel} anything
          </h3>
          <p className="mt-0.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Get plain-English answers, each cited to the exact filing text. Try a starter question:
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {starters.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onAsk(q, 'summary_starter')}
                className="rounded-full border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-800/40 px-3 py-1.5 text-left text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-light/40 hover:text-brand-strong dark:hover:text-brand-strong-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
              >
                {q}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => onAsk('', 'summary_cta')}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand-strong px-4 py-2 text-sm font-semibold text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
          >
            <SparkleIcon className="h-4 w-4" aria-hidden="true" />
            Ask this filing
          </button>
        </div>
      </div>
    </section>
  )
}

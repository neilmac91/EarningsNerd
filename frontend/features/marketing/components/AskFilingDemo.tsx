import { Button } from '@/components/ui/Button'
import { CheckCircleIcon, QuotesIcon } from '@/lib/icons'
import { injectCitationMarkers } from '@/lib/citationMarkers'
import { isXbrlCitation, xbrlTag, type CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import { SAMPLE_ASK, SAMPLE_FILING } from '@/features/marketing/lib/landing-samples'

// The mono answer register (DS §3: Ask-this-Filing output renders in the data face).
const ANSWER_REGISTER =
  'copilot-answer tnum font-data text-[13px] leading-relaxed text-text-primary-light dark:text-text-primary-dark'

// Inside-card eyebrow (11px uppercase tracked, tertiary on the white field surface).
const EYEBROW =
  'text-[11px] font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark'

const FIELD = 'rounded-lg border border-border-light bg-white dark:border-white/10 dark:bg-white/5'

const FILING_NOTE = `${SAMPLE_FILING.ticker} · ${SAMPLE_FILING.filingType} · ${SAMPLE_FILING.fiscalYear}`

// A mutable copy: the sample is frozen `as const`, and the marker walker takes a plain array.
const CITATIONS: CopilotCitation[] = [...SAMPLE_ASK.citations]

/**
 * The "Ask this Filing" product screen for the landing page: one question, one completed answer
 * whose `[F1]` / `[1]` markers are the REAL CitationChip (injected through the same
 * lib/citationMarkers walker CopilotMessage uses), and a footnote row per citation that names the
 * chip kind in plain words ("XBRL figure" / "Passage"). No FilingViewerProvider is mounted, so
 * each chip degrades to its EDGAR anchor, which keeps both reachable. The composer beneath is a
 * static shell, hidden from assistive tech because it accepts nothing. Server-rendered: only
 * CitationChip is a client boundary, and it receives plain citation data.
 */
export default function AskFilingDemo() {
  const answer = injectCitationMarkers(SAMPLE_ASK.answer, CITATIONS, (citation, key) => (
    <CitationChip key={key} citation={citation} />
  ))

  return (
    <div className="mockup-frame shadow-e3 dark:shadow-none" data-capture="ask-this-filing">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 border-b border-border-light px-4 py-3 dark:border-white/10">
        <span
          aria-hidden="true"
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-brand-weak text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark"
        >
          <QuotesIcon className="h-4 w-4" />
        </span>
        <span className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
          Ask this Filing
        </span>
        <span className="whitespace-nowrap font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
          {FILING_NOTE}
        </span>
      </div>

      <div className="flex flex-col gap-3 p-4">
        <div className="max-w-[85%] self-end rounded-lg border border-brand-border bg-brand-weak px-3.5 py-2.5 text-sm text-text-primary-light dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-text-primary-dark">
          {SAMPLE_ASK.question}
        </div>

        <div className={`${FIELD} p-3.5`}>
          <p className={ANSWER_REGISTER}>{answer}</p>

          <ul className="mt-3 flex flex-col gap-1.5 border-t border-border-light pt-2.5 dark:border-white/10">
            {CITATIONS.map((citation) => {
              const isFact = isXbrlCitation(citation)
              const locator = isFact ? xbrlTag(citation) : citation.section_ref
              return (
                <li
                  key={String(citation.n)}
                  className="flex flex-wrap items-center gap-2 text-xs text-text-secondary-light dark:text-text-secondary-dark"
                >
                  <span className="font-data font-semibold text-brand-strong dark:text-brand-strong-dark">
                    [{String(citation.n).toUpperCase()}]
                  </span>
                  <span className={EYEBROW}>{isFact ? 'XBRL figure' : 'Passage'}</span>
                  {locator && (
                    <span className={isFact ? 'min-w-0 break-all font-data text-data-xs' : undefined}>{locator}</span>
                  )}
                  {citation.verified && (
                    <span className="inline-flex items-center gap-1 font-medium text-brand-strong dark:text-brand-strong-dark">
                      <CheckCircleIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
                      Verified
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>

        {/* Decorative composer: hidden from assistive tech and out of the tab order (a server
            component may render the client <Button>, but not call its class factory). */}
        <div aria-hidden="true" className={`${FIELD} flex items-center gap-2 py-1.5 pl-3.5 pr-1.5`}>
          <span className="flex-1 text-sm text-text-tertiary-light dark:text-text-secondary-dark">Ask this filing…</span>
          <Button size="sm" tabIndex={-1}>
            Ask
          </Button>
        </div>
      </div>
    </div>
  )
}

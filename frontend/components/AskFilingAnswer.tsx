'use client'

/* =============================================================================
   AskFilingAnswer — components/AskFilingAnswer.tsx
   -----------------------------------------------------------------------------
   The "Ask this Filing" answer block. Evidence-first identity: the header tile
   is the QUOTES glyph (the product's proof marker) — sparkles are reserved for
   small AI chips elsewhere. The answer body and citation excerpts render in the
   data face (mono + tabular-nums), matching the .copilot-answer rule in
   globals.css. `[n]` markers in the answer text become tappable brand-tint
   chips (brand.weak bg + brand.strong text); every claim deep-links back to
   the filing. Persistent compliance footer.
   Citations come in two kinds — verbatim EXCERPTS (quote rail) and XBRL
   ANCHORS (tag glyph + concept in the data face + tabular value/period,
   deep-linked to the EDGAR inline viewer). Inline [n] chips are identical
   regardless of kind; both resolve the same way while streaming.
   States: loading (mono skeleton) / streaming (caret; citations pending) /
   complete (answer + evidence footnotes) / error (retry — quota preserved).
============================================================================= */

import { type ReactNode, useEffect, useRef, useState } from 'react'
import { cx } from './ui/cx'
import { Badge } from './ui/Badge'
import { Button } from './ui/Button'
import { SkeletonText } from './ui/Skeleton'

export type AskFilingStatus = 'loading' | 'streaming' | 'complete' | 'error'

export interface ExcerptCitation {
  id: number
  kind?: 'excerpt'
  /** Verbatim filing excerpt. */
  excerpt: string
  /** e.g. "10-K · Item 1A · p. 24" */
  source: string
  href?: string
}

export interface XbrlCitation {
  id: number
  kind: 'xbrl'
  /** Tagged concept, e.g. "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" */
  concept: string
  /** Reported value, pre-formatted — e.g. "$130,497M" */
  value: string
  /** e.g. "USD" — omit when the formatted value already carries it */
  unit?: string
  /** e.g. "FY2025 · 12 mo ended Jan 26, 2025" */
  period: string
  /** EDGAR inline-viewer deep link to the tagged fact. */
  href: string
}

export type FilingCitation = ExcerptCitation | XbrlCitation

export interface AskFilingAnswerProps {
  question: string
  status: AskFilingStatus
  /** Plain text with [1] [2] citation markers. */
  answer?: string
  citations?: FilingCitation[]
  /** e.g. "NVDA · 10-K · FY2025" */
  filingLabel?: string
  errorMessage?: string
  onRetry?: () => void
  onCitationClick?: (id: number) => void
  className?: string
}

const CHIP = cx(
  'border border-brand-border bg-brand-weak text-brand-strong',
  'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
)

/** Split answer text on [n] markers and render them as citation chips. */
function renderAnswer(text: string | undefined, onCitationClick?: (id: number) => void): ReactNode[] {
  // Streaming starts with no answer text yet (and API fields can be nullish at
  // runtime) — render nothing instead of crashing on .split.
  if (!text) return []
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/)
    if (!m) return part
    const id = Number(m[1])
    return (
      <button
        key={i}
        type="button"
        onClick={() => onCitationClick?.(id)}
        aria-label={`Citation ${id}`}
        // Inline citation markers fall under the WCAG 2.5.8 "inline" exception
        // (targets within a line of text) — sized 18px for comfort, no fake
        // 44px overlay that would collide with neighboring prose.
        className={cx(
          'mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-0.5 items-center justify-center rounded px-1 align-middle text-[10px] font-semibold',
          CHIP,
          'hover:bg-brand-border/60 focus-visible:outline-none focus-visible:shadow-ring-brand',
          'dark:hover:bg-brand-border-dark dark:focus-visible:shadow-ring-brand-dark',
        )}
      >
        {id}
      </button>
    )
  })
}

/** XBRL anchor marker — outline tag, matches Phosphor regular weight. */
function TagIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5 flex-none" aria-hidden="true">
      <path
        d="M11.6 3.4h6.2a1.8 1.8 0 0 1 1.8 1.8v6.2c0 .48-.19.94-.53 1.27l-7.4 7.4a1.8 1.8 0 0 1-2.54 0l-6.2-6.2a1.8 1.8 0 0 1 0-2.54l7.4-7.4c.33-.34.79-.53 1.27-.53Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="15.2" cy="8.8" r="1.4" fill="currentColor" />
    </svg>
  )
}

function QuotesIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M10.4 7.2c-3 .8-4.9 3-4.9 6.1 0 2 1.3 3.5 3.1 3.5 1.6 0 2.9-1.2 2.9-2.9 0-1.5-1-2.6-2.5-2.8.3-1.2 1.3-2.2 2.7-2.7l-1.3-1.2z" />
      <path d="M18.4 7.2c-3 .8-4.9 3-4.9 6.1 0 2 1.3 3.5 3.1 3.5 1.6 0 2.9-1.2 2.9-2.9 0-1.5-1-2.6-2.5-2.8.3-1.2 1.3-2.2 2.7-2.7l-1.3-1.2z" />
    </svg>
  )
}

export function AskFilingAnswer({
  question,
  status,
  answer = '',
  citations = [],
  filingLabel,
  errorMessage,
  onRetry,
  onCitationClick,
  className,
}: AskFilingAnswerProps) {
  const busy = status === 'loading' || status === 'streaming'

  // Skeleton→content handoff (same pattern as DataTable): when status leaves
  // 'loading', the replacing body — answer or error card — crossfades in at
  // duration-base / ease-standard; instant under reduced motion.
  const wasLoading = useRef(status === 'loading')
  const [entered, setEntered] = useState(false)
  useEffect(() => {
    const isLoading = status === 'loading'
    if (wasLoading.current && !isLoading) setEntered(true)
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot skeleton→content crossfade armed on the loading flip; intentional sync with the status prop
    if (isLoading) setEntered(false)
    wasLoading.current = isLoading
  }, [status])
  const enterClass = entered ? 'animate-content-in motion-reduce:animate-none' : undefined

  return (
    <section
      aria-busy={busy || undefined}
      className={cx(
        'flex flex-col overflow-hidden rounded-xl border border-border-light bg-panel-light shadow-e2',
        'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        className,
      )}
    >
      <header className="flex items-center gap-2.5 border-b border-border-light px-5 py-3.5 dark:border-border-dark">
        <span className={cx('flex h-7 w-7 flex-none items-center justify-center rounded-lg border', CHIP)}>
          <QuotesIcon />
        </span>
        <h3 className="text-sm font-semibold">Ask this Filing</h3>
        <Badge variant="pro">Pro</Badge>
        {filingLabel ? (
          <span className="ml-auto font-data text-[11px] text-text-tertiary-light dark:text-text-secondary-dark">
            {filingLabel}
          </span>
        ) : null}
      </header>

      <div className="flex-1 px-5 py-4">
        <p className="mb-3 text-sm font-semibold">{question}</p>

        {status === 'loading' ? <SkeletonText lines={4} mono /> : null}

        {status === 'streaming' || status === 'complete' ? (
          <div
            className={cx(
              'copilot-answer tnum font-data text-sm leading-7 text-text-primary-light dark:text-text-primary-dark',
              enterClass,
            )}
          >
            {renderAnswer(answer, onCitationClick)}
            {status === 'streaming' ? (
              <span
                aria-hidden="true"
                className="ml-0.5 inline-block h-4 w-[7px] translate-y-0.5 animate-pulse bg-brand-strong motion-reduce:animate-none dark:bg-brand-strong-dark"
              />
            ) : null}
          </div>
        ) : null}

        {status === 'streaming' ? (
          <p className="mt-3 text-[11px] text-text-tertiary-light dark:text-text-secondary-dark">
            Citations resolve as each claim verifies against the filing.
          </p>
        ) : null}

        {status === 'complete' && citations.length > 0 ? (
          <ol className="mt-4 space-y-3 border-t border-border-light pt-4 dark:border-border-dark">
            {citations.map((c) => (
              <li key={c.id} className="flex gap-2.5">
                <span
                  className={cx(
                    'flex h-[18px] w-[18px] flex-none items-center justify-center rounded border text-[10px] font-semibold',
                    CHIP,
                  )}
                >
                  {c.id}
                </span>
                {c.kind === 'xbrl' ? (
                  <div className="min-w-0">
                    {/* Same brand-tint rail as excerpts; tag glyph replaces the quote register. */}
                    <div className="border-l-2 border-brand-border pl-3 dark:border-brand-border-dark">
                      <div className="flex items-start gap-1.5">
                        <span className="mt-px text-brand-strong dark:text-brand-strong-dark">
                          <TagIcon />
                        </span>
                        <span className="min-w-0 break-all font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                          {c.concept}
                        </span>
                      </div>
                      <p className="tnum mt-1 font-data text-xs leading-relaxed text-text-primary-light dark:text-text-primary-dark">
                        {c.value}
                        {c.unit ? (
                          <span className="text-text-tertiary-light dark:text-text-secondary-dark"> {c.unit}</span>
                        ) : null}
                        <span className="text-text-tertiary-light dark:text-text-secondary-dark"> · {c.period}</span>
                      </p>
                    </div>
                    <a
                      href={c.href}
                      onClick={() => onCitationClick?.(c.id)}
                      className="mt-1 inline-block text-xs font-semibold text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
                    >
                      XBRL · EDGAR viewer ↗
                    </a>
                  </div>
                ) : (
                <div className="min-w-0">
                  <blockquote className="border-l-2 border-brand-border pl-3 font-data text-xs leading-relaxed text-text-secondary-light dark:border-brand-border-dark dark:text-text-secondary-dark">
                    “{c.excerpt}”
                  </blockquote>
                  {c.href ? (
                    <a
                      href={c.href}
                      onClick={() => onCitationClick?.(c.id)}
                      className="mt-1 inline-block text-xs font-semibold text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
                    >
                      {c.source} ↗
                    </a>
                  ) : (
                    <span className="mt-1 inline-block text-xs font-medium text-text-tertiary-light dark:text-text-secondary-dark">
                      {c.source}
                    </span>
                  )}
                </div>
                )}
              </li>
            ))}
          </ol>
        ) : null}

        {status === 'error' ? (
          <div
            role="alert"
            className={cx(
              'flex flex-col items-start gap-3 rounded-lg border border-error-light/25 bg-error-light/[0.06] px-4 py-3.5 dark:border-error-dark/25 dark:bg-error-dark/10',
              enterClass,
            )}
          >
            <p className="text-sm font-medium text-error-light dark:text-error-dark">
              {errorMessage ?? 'The answer could not be generated. Your quota was not used.'}
            </p>
            {onRetry ? (
              <Button variant="secondary" size="sm" onClick={onRetry}>
                Retry
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      <footer className="flex items-center justify-between gap-3 border-t border-border-light px-5 py-2.5 text-[11px] text-text-tertiary-light dark:border-border-dark dark:text-text-secondary-dark">
        <span>Data sourced from SEC EDGAR. Not investment advice.</span>
        {status === 'complete' && citations.length > 0 ? (
          <span className="font-data">
            {citations.length} citation{citations.length === 1 ? '' : 's'}
          </span>
        ) : null}
      </footer>
    </section>
  )
}

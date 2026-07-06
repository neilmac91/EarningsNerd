'use client'

/* =============================================================================
   AskFilingAnswer — components/AskFilingAnswer.tsx
   -----------------------------------------------------------------------------
   v2.2 REWORK — rebuilt against the SHIPPED copilot data model. The v2 pack
   shipped an `id: number`/plain-text model that predated the API and had zero
   importers; the live renderer (CopilotMessage, pinned by 9 test suites)
   defines the contract this file now matches:

     - CopilotCitation { n, excerpt, section_ref, verified, fragment_url } —
       marker ids are `n` (1, 2… for excerpts; "F1"/"F 2" for XBRL facts).
     - status: 'reading' | 'streaming' | 'done' | 'error'.
     - answer is GFM MARKDOWN — react-markdown + remark-gfm (already app deps
       via the live copilot; this file adds no new dependency to the app).
     - Marker grammar: [n] AND [F1]/[f1]/[F 1] — case/whitespace tolerant.
       UNMATCHED markers stay literal text (never a dead button). Chips show
       the bracketed marker "[1]" / "[F1]", not a bare superscript number.
     - `verified` is the product's TRUST MARKER — never drop it. Each citation
       carries a Verified badge (brand tint + check: the excerpt re-matched the
       filing server-side) or a quiet Cited badge (linked, not machine-
       verified); the footer counts verified claims.

   Evidence-first identity: the header tile is the QUOTES glyph (sparkles stay
   reserved for the "AI summary" chip). Answer + excerpts render in the data
   face (mono + tabular-nums; the .copilot-answer rule in globals.css). XBRL
   facts — `section_ref` starting with "XBRL" — swap the quote rail for the
   tag glyph + concept anchor. Persistent compliance footer.
   States: reading (mono skeleton) / streaming (caret; citations pending) /
   done (markdown + chips + evidence footnotes) / error (retry — quota
   preserved).
============================================================================= */

import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cx } from '@/components/ui/cx'
import { SEC_EDGAR_NOT_ADVICE } from '@/components/AiDisclaimer'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { SkeletonText } from '@/components/ui/Skeleton'

export type CopilotStatus = 'reading' | 'streaming' | 'done' | 'error'

export interface CopilotCitation {
  /** Marker id as the API emits it — 1, 2… for excerpts; "F1" / "F 2" (any
      case/spacing) for XBRL facts. NOT an `id: number`. */
  n: number | string
  /** Verbatim filing excerpt — or the fact's value/period line for XBRL anchors. */
  excerpt: string
  /** Locator, e.g. "10-K · Item 1A · p. 24". XBRL anchors START WITH "XBRL". */
  section_ref: string | null
  /** true = the excerpt re-matched the filing text server-side. Drives the
      Verified/Cited trust badge — the product's trust marker. */
  verified: boolean
  /** EDGAR deep link; null renders a non-linked locator, never a dead anchor. */
  fragment_url: string | null
}

export interface AskFilingAnswerProps {
  question: string
  status: CopilotStatus
  /** GFM markdown with [n] / [F#] citation markers. */
  answer?: string
  citations?: CopilotCitation[]
  /** e.g. "NVDA · 10-K · FY2025" */
  filingLabel?: string
  errorMessage?: string
  onRetry?: () => void
  /** Receives the matched citation's `n` (1 · "F1" · …). */
  onCitationClick?: (n: CopilotCitation['n']) => void
  className?: string
}

const CHIP = cx(
  'border border-brand-border bg-brand-weak text-brand-strong',
  'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
)

const LINK = cx(
  'text-xs font-semibold text-brand-strong underline-offset-4 hover:underline',
  'focus-visible:outline-none focus-visible:shadow-ring-brand',
  'dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark',
)

/* ------------------------------------------------------- marker grammar -- */

/** [1] · [F1] · [f1] · [F 1] — case/whitespace tolerant (split, capturing). */
const MARKER_SPLIT = /(\[\s*[Ff]?\s*\d+\s*\])/g
const MARKER_EXACT = /^\[\s*[Ff]?\s*\d+\s*\]$/

/** Normalize both sides of the match: "[F 1]" → "F1", "[3]" → "3". */
function markerKey(raw: string): string {
  return raw.replace(/[[\]\s]/g, '').toUpperCase()
}

type CitationIndex = Map<string, CopilotCitation>

function buildIndex(citations: CopilotCitation[]): CitationIndex {
  const index: CitationIndex = new Map()
  for (const c of citations) index.set(markerKey(`[${String(c.n)}]`), c)
  return index
}

/** Split a text run on citation markers; matched markers become chips showing
    the bracketed marker ("[1]" / "[F1]"); unmatched markers stay literal text —
    never a dead button. */
function renderMarkers(
  text: string,
  index: CitationIndex,
  onCitationClick?: (n: CopilotCitation['n']) => void,
): ReactNode {
  const parts = text.split(MARKER_SPLIT)
  if (parts.length === 1) return text
  return parts.map((part, i) => {
    if (!MARKER_EXACT.test(part)) return part
    const key = markerKey(part)
    const c = index.get(key)
    if (!c) return part
    return (
      <button
        key={i}
        type="button"
        onClick={() => onCitationClick?.(c.n)}
        aria-label={`Citation ${key}${c.verified ? ', verified' : ''}`}
        // Inline citation markers fall under the WCAG 2.5.8 "inline" exception
        // (targets within a line of text) — sized 18px for comfort, no fake
        // 44px overlay that would collide with neighboring prose.
        className={cx(
          'mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-0.5 items-center justify-center rounded px-1 align-middle font-data text-[10px] font-semibold',
          CHIP,
          'hover:bg-brand-border/60 focus-visible:outline-none focus-visible:shadow-ring-brand',
          'dark:hover:bg-brand-border-dark dark:focus-visible:shadow-ring-brand-dark',
        )}
      >
        {`[${key}]`}
      </button>
    )
  })
}

/** Map string children (and string items of arrays) through renderMarkers;
    element children are handled by their own component overrides. */
function withMarkers(
  children: ReactNode,
  index: CitationIndex,
  onCitationClick?: (n: CopilotCitation['n']) => void,
): ReactNode {
  if (typeof children === 'string') return renderMarkers(children, index, onCitationClick)
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string' ? (
        <Fragment key={i}>{renderMarkers(child, index, onCitationClick)}</Fragment>
      ) : (
        child
      ),
    )
  }
  return children
}

/* --------------------------------------------------- markdown components -- */

type MdExtra = { node?: unknown }

/** GFM answer manners inside the mono register: quiet block rhythm, reader-
    style hairline tables, brand links. Every text-bearing element routes its
    string children through the marker grammar. Markers inside `code` stay
    literal by design (verbatim register). */
function buildMdComponents(index: CitationIndex, onCitationClick?: (n: CopilotCitation['n']) => void) {
  const marked = (children: ReactNode) => withMarkers(children, index, onCitationClick)
  return {
    p: ({ node: _n, children, ...rest }: ComponentProps<'p'> & MdExtra) => (
      <p {...rest} className="mb-3 last:mb-0">
        {marked(children)}
      </p>
    ),
    ul: ({ node: _n, children, ...rest }: ComponentProps<'ul'> & MdExtra) => (
      <ul {...rest} className="mb-3 list-disc space-y-1 pl-5 last:mb-0">
        {children}
      </ul>
    ),
    ol: ({ node: _n, children, ...rest }: ComponentProps<'ol'> & MdExtra) => (
      <ol {...rest} className="tnum mb-3 list-decimal space-y-1 pl-5 last:mb-0">
        {children}
      </ol>
    ),
    li: ({ node: _n, children, ...rest }: ComponentProps<'li'> & MdExtra) => (
      <li {...rest}>{marked(children)}</li>
    ),
    strong: ({ node: _n, children, ...rest }: ComponentProps<'strong'> & MdExtra) => (
      <strong {...rest} className="font-semibold">
        {marked(children)}
      </strong>
    ),
    em: ({ node: _n, children, ...rest }: ComponentProps<'em'> & MdExtra) => (
      <em {...rest}>{marked(children)}</em>
    ),
    del: ({ node: _n, children, ...rest }: ComponentProps<'del'> & MdExtra) => (
      <del {...rest}>{marked(children)}</del>
    ),
    a: ({ node: _n, children, ...rest }: ComponentProps<'a'> & MdExtra) => (
      <a {...rest} className={cx(LINK, 'text-sm underline')}>
        {marked(children)}
      </a>
    ),
    blockquote: ({ node: _n, children, ...rest }: ComponentProps<'blockquote'> & MdExtra) => (
      <blockquote
        {...rest}
        className="mb-3 border-l-2 border-brand-border pl-3 text-text-secondary-light last:mb-0 dark:border-brand-border-dark dark:text-text-secondary-dark"
      >
        {children}
      </blockquote>
    ),
    table: ({ node: _n, children, ...rest }: ComponentProps<'table'> & MdExtra) => (
      <table {...rest} className="mb-3 w-full border-collapse text-xs last:mb-0">
        {children}
      </table>
    ),
    th: ({ node: _n, children, ...rest }: ComponentProps<'th'> & MdExtra) => (
      // Reader-table manners: hairline rows only, 12px-register uppercase header.
      <th
        {...rest}
        className="border-b border-border-light px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:border-border-dark dark:text-text-secondary-dark"
      >
        {marked(children)}
      </th>
    ),
    td: ({ node: _n, children, ...rest }: ComponentProps<'td'> & MdExtra) => (
      // GFM column alignment arrives as the `align` attribute via ...rest.
      <td {...rest} className="tnum border-b border-border-light px-2 py-1.5 align-top dark:border-border-dark">
        {marked(children)}
      </td>
    ),
  }
}

/* ------------------------------------------------------------------ svg -- */

function QuotesIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M10.4 7.2c-3 .8-4.9 3-4.9 6.1 0 2 1.3 3.5 3.1 3.5 1.6 0 2.9-1.2 2.9-2.9 0-1.5-1-2.6-2.5-2.8.3-1.2 1.3-2.2 2.7-2.7l-1.3-1.2z" />
      <path d="M18.4 7.2c-3 .8-4.9 3-4.9 6.1 0 2 1.3 3.5 3.1 3.5 1.6 0 2.9-1.2 2.9-2.9 0-1.5-1-2.6-2.5-2.8.3-1.2 1.3-2.2 2.7-2.7l-1.3-1.2z" />
    </svg>
  )
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

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-2.5 w-2.5" aria-hidden="true">
      <path d="m5 12.5 4.5 4.5L19 7.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** The trust marker. Verified = the excerpt re-matched the filing (brand tint —
    trust reads as evidence, not success-green); Cited = linked, not machine-
    verified (quiet chip). */
function TrustBadge({ verified }: { verified: boolean }) {
  return verified ? (
    <span className={cx('inline-flex items-center gap-1 rounded-full border px-2 py-px text-[10.5px] font-semibold', CHIP)}>
      <CheckIcon />
      Verified
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full border border-border-light bg-white px-2 py-px text-[10.5px] font-medium text-text-secondary-light dark:border-border-dark dark:bg-white/5 dark:text-text-secondary-dark">
      Cited
    </span>
  )
}

/* ------------------------------------------------------------ component -- */

/** Streaming caret, kept INLINE at the end of the last markdown block. */
const STREAM_CARET = cx(
  "[&>:last-child]:after:ml-1 [&>:last-child]:after:inline-block [&>:last-child]:after:h-4 [&>:last-child]:after:w-[7px] [&>:last-child]:after:translate-y-0.5 [&>:last-child]:after:content-['']",
  '[&>:last-child]:after:animate-pulse motion-reduce:[&>:last-child]:after:animate-none',
  '[&>:last-child]:after:bg-brand-strong dark:[&>:last-child]:after:bg-brand-strong-dark',
)

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
  const busy = status === 'reading' || status === 'streaming'

  // Skeleton→content handoff (same pattern as DataTable): when status leaves
  // 'reading', the replacing body — answer or error card — crossfades in at
  // duration-base / ease-standard; instant under reduced motion.
  const wasReading = useRef(status === 'reading')
  const [entered, setEntered] = useState(false)
  useEffect(() => {
    const isReading = status === 'reading'
    if (wasReading.current && !isReading) setEntered(true)
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot skeleton→content crossfade armed on the reading flip; intentional sync
    if (isReading) setEntered(false)
    wasReading.current = isReading
  }, [status])
  const enterClass = entered ? 'animate-content-in motion-reduce:animate-none' : undefined

  const index = useMemo(() => buildIndex(citations), [citations])
  const mdComponents = useMemo(() => buildMdComponents(index, onCitationClick), [index, onCitationClick])
  const verifiedCount = citations.filter((c) => c.verified).length

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

        {status === 'reading' ? <SkeletonText lines={4} mono /> : null}

        {status === 'streaming' || status === 'done' ? (
          <div
            className={cx(
              'copilot-answer tnum font-data text-sm leading-7 text-text-primary-light dark:text-text-primary-dark',
              status === 'streaming' ? STREAM_CARET : undefined,
              enterClass,
            )}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {answer}
            </ReactMarkdown>
          </div>
        ) : null}

        {status === 'streaming' ? (
          <p className="mt-3 text-[11px] text-text-tertiary-light dark:text-text-secondary-dark">
            Citations resolve as each claim verifies against the filing.
          </p>
        ) : null}

        {status === 'done' && citations.length > 0 ? (
          <ol className="mt-4 space-y-3 border-t border-border-light pt-4 dark:border-border-dark">
            {citations.map((c, i) => {
              const key = markerKey(`[${String(c.n)}]`)
              const xbrl = c.section_ref?.startsWith('XBRL') ?? false
              return (
                <li key={`${key}-${i}`} className="flex gap-2.5">
                  <span
                    className={cx(
                      'flex h-[18px] min-w-[18px] flex-none items-center justify-center rounded border px-1 font-data text-[10px] font-semibold',
                      CHIP,
                    )}
                  >
                    {`[${key}]`}
                  </span>
                  {xbrl ? (
                    <div className="min-w-0">
                      {/* Same brand-tint rail as excerpts; tag glyph replaces the quote register. */}
                      <div className="border-l-2 border-brand-border pl-3 dark:border-brand-border-dark">
                        <div className="flex items-start gap-1.5">
                          <span className="mt-px text-brand-strong dark:text-brand-strong-dark">
                            <TagIcon />
                          </span>
                          <span className="min-w-0 break-all font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                            {c.section_ref}
                          </span>
                        </div>
                        <p className="tnum mt-1 font-data text-xs leading-relaxed text-text-primary-light dark:text-text-primary-dark">
                          {c.excerpt}
                        </p>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        {c.fragment_url ? (
                          <a href={c.fragment_url} onClick={() => onCitationClick?.(c.n)} className={LINK}>
                            XBRL · EDGAR viewer ↗
                          </a>
                        ) : null}
                        <TrustBadge verified={c.verified} />
                      </div>
                    </div>
                  ) : (
                    <div className="min-w-0">
                      <blockquote className="border-l-2 border-brand-border pl-3 font-data text-xs leading-relaxed text-text-secondary-light dark:border-brand-border-dark dark:text-text-secondary-dark">
                        “{c.excerpt}”
                      </blockquote>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        {c.fragment_url ? (
                          <a href={c.fragment_url} onClick={() => onCitationClick?.(c.n)} className={LINK}>
                            {c.section_ref ?? 'View in filing'} ↗
                          </a>
                        ) : c.section_ref ? (
                          <span className="text-xs font-medium text-text-tertiary-light dark:text-text-secondary-dark">
                            {c.section_ref}
                          </span>
                        ) : null}
                        <TrustBadge verified={c.verified} />
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
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
        <span>{SEC_EDGAR_NOT_ADVICE}</span>
        {status === 'done' && citations.length > 0 ? (
          <span className="font-data">
            {citations.length} citation{citations.length === 1 ? '' : 's'} · {verifiedCount} verified
          </span>
        ) : null}
      </footer>
    </section>
  )
}

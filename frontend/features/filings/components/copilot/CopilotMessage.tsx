'use client'

import { type ComponentProps, type ReactNode } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import { Button } from '@/components/ui'
import AiDisclaimer, { SEC_EDGAR_NOT_ADVICE } from '@/components/AiDisclaimer'
import remarkGfm from 'remark-gfm'
import { ArrowClockwiseIcon, ArrowRightIcon, CheckCircleIcon, ProhibitIcon, SparkleIcon } from '@/lib/icons'
import { injectCitationMarkers } from '@/lib/citationMarkers'
import { isXbrlCitation, xbrlTag, type CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip, { isHttpUrl } from './CitationChip'

/* Visual language: the v2.2 "Ask answer" evidence block (see
   components/AskFilingAnswer.tsx, the DS reference implementation) — panel
   card chrome, mono answer register (.copilot-answer — DS type roles put
   Ask-this-Filing output in the data face), brand-tint bracket markers,
   footnote evidence rows with the Verified/Cited trust badge, and the
   citations · verified compliance counts. The MACHINERY here (streaming fast
   path, citation-chip injection, viewer deep-links, follow-ups) is
   the shipped contract pinned by the copilot test suites — restyle only.
   The assistant's background tool activity is deliberately never surfaced:
   the reading state shows a single calm indicator, then the clean answer. */

export interface CopilotMessageData {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: CopilotCitation[]
  grounded?: number
  kind?: 'answer' | 'not_disclosed'
  // 'reading' (pre-token), 'streaming' (tokens arriving), 'done', 'error'
  status?: 'reading' | 'streaming' | 'done' | 'error'
  error?: string
  // 2-3 suggested next questions, shown as tappable chips under the latest answer.
  followups?: string[]
}

/* The brand-tint chip recipe shared by footnote markers (mirrors the DS CHIP). */
const CHIP =
  'border border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark'

/* The assistant evidence-block chrome: cards lift, not tint (panel + hairline
   + e2; dark drops the shadow). rounded-bl-sm keeps the thread tail. */
const ANSWER_CARD =
  'rounded-xl rounded-bl-sm border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none px-4 py-3 text-sm'

interface CopilotMessageProps {
  message: CopilotMessageData
  onRetry?: () => void
  isPaywallError?: boolean
  // Opens the contextual upgrade modal (used by the paywall error bubble instead of a raw link).
  onUpgrade?: () => void
  // Issuer ticker + filing type — used by the "not disclosed" card to point to the right filing.
  ticker?: string | null
  filingType?: string
  // Tapping a suggested follow-up asks it. Only shown for the latest completed answer.
  onFollowup?: (question: string) => void
  showFollowups?: boolean
}

// When an answer isn't in THIS filing, nudge toward where it usually lives (annual vs. quarterly).
function notDisclosedHint(filingType?: string): string | null {
  if (!filingType) return null
  if (/10-?q/i.test(filingType))
    return 'Annual-only details — full risk factors, executive compensation, the business overview — usually live in the company’s 10-K.'
  if (/10-?k/i.test(filingType))
    return 'Quarter-specific updates usually appear in the company’s most recent 10-Q.'
  return null
}

// Tappable "ask next" chips generated per answer.
function FollowupChips({
  followups,
  onFollowup,
}: {
  followups: string[]
  onFollowup: (question: string) => void
}) {
  return (
    <div className="mt-3 border-t border-border-light dark:border-white/10 pt-2.5">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">Ask next</p>
      <div className="flex flex-col gap-1.5">
        {followups.map((q, i) => (
          <button
            key={`${q}-${i}`}
            type="button"
            onClick={() => onFollowup(q)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border-light dark:border-white/10 bg-brand-weak dark:bg-white/5 px-2.5 py-1.5 text-left text-xs text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-border hover:bg-brand-weak/70 dark:hover:bg-white/10"
          >
            <SparkleIcon className="h-3 w-3 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

/* --------------------------------------------------- markdown components -- */

type MdExtra = { node?: unknown }

/** v2.2 GFM manners for the mono answer register: mb-3 block rhythm, tnum
    numerals, reader-style hairline tables, brand links. `inject` routes a
    text-bearing element's children through the citation-chip walker — the
    SAME coverage set as before the restyle (p/li/strong/em/td); everything
    else is style-only. */
function buildMdComponents(inject: (children: ReactNode) => ReactNode) {
  return {
    p: ({ node: _n, children, ...rest }: ComponentProps<'p'> & MdExtra) => (
      <p {...rest} className="mb-3 last:mb-0">
        {inject(children)}
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
      <li {...rest}>{inject(children)}</li>
    ),
    strong: ({ node: _n, children, ...rest }: ComponentProps<'strong'> & MdExtra) => (
      <strong {...rest} className="font-semibold text-text-primary-light dark:text-text-primary-dark">
        {inject(children)}
      </strong>
    ),
    em: ({ node: _n, children, ...rest }: ComponentProps<'em'> & MdExtra) => (
      <em {...rest}>{inject(children)}</em>
    ),
    a: ({ node: _n, children, ...rest }: ComponentProps<'a'> & MdExtra) => (
      <a
        {...rest}
        className="font-semibold text-brand-strong underline underline-offset-4 dark:text-brand-strong-dark"
      >
        {children}
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
      <th
        {...rest}
        className="border-b border-border-light px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:border-border-dark dark:text-text-secondary-dark"
      >
        {children}
      </th>
    ),
    td: ({ node: _n, children, ...rest }: ComponentProps<'td'> & MdExtra) => (
      <td {...rest} className="tnum border-b border-border-light px-2 py-1.5 align-top dark:border-border-dark">
        {inject(children)}
      </td>
    ),
  }
}

/* The mono answer register — DS type roles render Ask-this-Filing output in
   the data face (.copilot-answer in globals.css). */
const ANSWER_REGISTER =
  'copilot-answer tnum break-words font-data text-sm leading-7 text-text-primary-light dark:text-text-primary-dark'

function MarkdownProse({ children }: { children: string }) {
  return (
    <div className={ANSWER_REGISTER}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildMdComponents((c) => c)}>
        {children}
      </ReactMarkdown>
    </div>
  )
}

// While tokens are still arriving we render the raw text (whitespace-preserving) instead of
// re-parsing the growing markdown on every frame — markdown (with citation chips) is rendered once
// the `complete` event lands. Re-parsing a markdown string that grows by a token each frame is the
// O(n²) cost the streaming view used to pay; a plain text node is a near-free update. `pre-wrap`
// keeps paragraph breaks readable mid-stream; the formatted answer snaps in when the stream ends.
function StreamingText({ children }: { children: string }) {
  return <div className={`whitespace-pre-wrap ${ANSWER_REGISTER}`}>{children}</div>
}

// Replace inline `[n]`/`[F#]` markers with interactive CitationChips via the shared walker (also
// used by the Multi-Period Analysis narrative renderer — see lib/citationMarkers.tsx).
function injectCitations(children: ReactNode, citations: CopilotCitation[]): ReactNode {
  return injectCitationMarkers(children, citations, (citation, key) => (
    <CitationChip key={key} citation={citation} />
  ))
}

// Markdown rendering for a completed answer with citation chips injected at `[n]`. The text-bearing
// element overrides run injectCitations around their rendered children so chips appear inline.
function MarkdownProseWithCitations({
  children,
  citations,
}: {
  children: string
  citations: CopilotCitation[]
}) {
  return (
    <div className={ANSWER_REGISTER}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={buildMdComponents((c) => injectCitations(c, citations))}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}


/** XBRL anchor marker — outline tag matching Phosphor regular weight (mirrors
    the DS reference; not in lib/icons). */
function TagIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
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

/** The trust marker (v2.2): Verified = the excerpt re-matched the filing
    server-side (brand tint — trust reads as evidence, not success-green);
    Cited = linked, not machine-verified (quiet pill). */
function TrustBadge({ verified }: { verified: boolean }) {
  return verified ? (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-px text-[10.5px] font-semibold ${CHIP}`}>
      <CheckCircleIcon className="h-2.5 w-2.5" aria-hidden="true" />
      Verified
    </span>
  ) : (
    <span className="inline-flex shrink-0 items-center rounded-full border border-border-light bg-white px-2 py-px text-[10.5px] font-medium text-text-secondary-light dark:border-border-dark dark:bg-white/5 dark:text-text-secondary-dark">
      Cited
    </span>
  )
}

/* Footnote evidence rows (v2.2): bracket marker chip + brand-rail excerpt
   blockquote (XBRL facts swap the quote register for the tag glyph + concept
   anchor + tabular figure) + locator link + trust badge. The decorative curly
   quotes are pseudo-elements so the excerpt stays an exact text node. */
function SourcesList({ citations }: { citations: CopilotCitation[] }) {
  if (!citations.length) return null
  const linkClass =
    'text-xs font-semibold text-brand-strong underline-offset-4 hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'
  return (
    <div className="mt-3 border-t border-border-light dark:border-white/10 pt-2.5">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">Sources</p>
      <ol className="space-y-3">
        {citations.map((c, i) => {
          const isFact = isXbrlCitation(c)
          const tag = isFact ? xbrlTag(c) : null
          return (
            <li key={`${c.n}-${i}`} className="flex gap-2.5 text-xs">
              <span
                className={`flex h-[18px] min-w-[18px] flex-none items-center justify-center rounded border px-1 font-data text-[10px] font-semibold ${CHIP}`}
              >
                [{String(c.n).toUpperCase()}]
              </span>
              {isFact ? (
                <div className="min-w-0 flex-1">
                  <div className="border-l-2 border-brand-border pl-3 dark:border-brand-border-dark">
                    {tag && (
                      <div className="flex items-start gap-1.5">
                        <span className="mt-px text-brand-strong dark:text-brand-strong-dark">
                          <TagIcon className="h-3.5 w-3.5 flex-none" />
                        </span>
                        <span className="min-w-0 break-all font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">{tag}</span>
                      </div>
                    )}
                    <p className="tnum mt-1 font-data text-xs leading-relaxed text-text-primary-light dark:text-text-primary-dark">
                      {c.excerpt}
                    </p>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {isHttpUrl(c.fragment_url) ? (
                      <a href={c.fragment_url} target="_blank" rel="noopener noreferrer" className={linkClass}>
                        {c.section_ref ?? 'XBRL'} · EDGAR ↗
                      </a>
                    ) : c.section_ref ? (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">{c.section_ref}</span>
                    ) : null}
                    <TrustBadge verified={c.verified} />
                  </div>
                </div>
              ) : (
                <div className="min-w-0 flex-1">
                  <blockquote className="border-l-2 border-brand-border pl-3 font-data text-xs leading-relaxed text-text-secondary-light before:content-['“'] after:content-['”'] dark:border-brand-border-dark dark:text-text-secondary-dark">
                    {c.excerpt}
                  </blockquote>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {isHttpUrl(c.fragment_url) ? (
                      <a href={c.fragment_url} target="_blank" rel="noopener noreferrer" className={linkClass}>
                        {c.section_ref ?? 'View in filing'} ↗
                      </a>
                    ) : c.section_ref ? (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">{c.section_ref}</span>
                    ) : (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">Excerpt {c.n}</span>
                    )}
                    <TrustBadge verified={c.verified} />
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default function CopilotMessage({
  message,
  onRetry,
  isPaywallError,
  onUpgrade,
  ticker,
  filingType,
  onFollowup,
  showFollowups,
}: CopilotMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-weak dark:bg-white/5 px-3.5 py-2 text-sm text-text-primary-light dark:text-text-primary-dark ring-1 ring-brand-border">
          {message.content}
        </div>
      </div>
    )
  }

  // --- Assistant: error bubble ---
  if (message.status === 'error') {
    return (
      <div
        role="alert"
        className="rounded-xl rounded-bl-sm border border-error-light/25 bg-error-light/[0.06] px-4 py-3 text-sm dark:border-error-dark/25 dark:bg-error-dark/10"
      >
        <p className="font-medium text-error-light dark:text-error-dark">{message.error || 'Something went wrong.'}</p>
        <div className="mt-2.5">
          {isPaywallError ? (
            onUpgrade && (
              <Button size="sm" onClick={onUpgrade} leftIcon={<SparkleIcon className="h-3.5 w-3.5" />}>
                Upgrade to Pro
              </Button>
            )
          ) : (
            onRetry && (
              <Button variant="secondary" size="sm" onClick={onRetry} leftIcon={<ArrowClockwiseIcon className="h-3.5 w-3.5" />}>
                Retry
              </Button>
            )
          )}
        </div>
      </div>
    )
  }

  // --- Assistant: "not disclosed" card (distinct state: quiet panel, no brand tint) ---
  if (message.kind === 'not_disclosed') {
    const hint = notDisclosedHint(filingType)
    return (
      <div className={ANSWER_CARD}>
        <div className="mb-1.5 flex items-center gap-2 text-text-secondary-light dark:text-text-secondary-dark">
          <ProhibitIcon className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">Not disclosed in this filing</span>
        </div>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">{message.content}</p>
        {(hint || ticker) && (
          <div className="mt-2.5 border-t border-border-light dark:border-white/10 pt-2.5">
            {hint && <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{hint}</p>}
            {ticker && (
              <Link
                href={`/company/${encodeURIComponent(ticker)}`}
                className={`${hint ? 'mt-1.5 ' : ''}inline-flex items-center gap-1 text-xs font-medium text-brand-strong dark:text-brand-strong-dark hover:underline`}
              >
                Browse {ticker}’s other filings
                <ArrowRightIcon className="h-3 w-3" />
              </Link>
            )}
          </div>
        )}
        {/* A dead end without a next step strands the user — surface the "questions this
            filing CAN answer" follow-ups the backend now sends with not_disclosed verdicts. */}
        {showFollowups && onFollowup && message.followups && message.followups.length > 0 && (
          <FollowupChips followups={message.followups} onFollowup={onFollowup} />
        )}
      </div>
    )
  }

  // --- Assistant: reading / streaming / done answer ---
  const isReading = message.status === 'reading' && message.content.length === 0
  const isStreaming = message.status === 'streaming'
  const isDone = message.status === 'done'
  // Inject interactive citation chips only once citations are known (a completed `answer`). While
  // streaming, `[n]` markers stay plain text via MarkdownProse until the `complete` event lands.
  // (The not_disclosed branch already returned above, so this is always an `answer`.)
  const citations = message.citations
  const showChips = isDone && !!citations && citations.length > 0
  const verifiedCount = citations?.filter((c) => c.verified).length ?? 0

  return (
    <div className={ANSWER_CARD}>
      {isReading ? (
        // A single calm indicator while the answer is grounded — the assistant's
        // background tool activity is deliberately not surfaced to the user.
        <p className="flex items-center gap-2 text-text-secondary-light dark:text-text-secondary-dark">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong dark:bg-brand-strong-dark" />
          Reading the filing…
        </p>
      ) : (
        <>
          <div className="flex items-start">
            <div className="min-w-0 flex-1">
              {showChips ? (
                <MarkdownProseWithCitations citations={citations!}>
                  {message.content}
                </MarkdownProseWithCitations>
              ) : isStreaming ? (
                <StreamingText>{message.content}</StreamingText>
              ) : (
                <MarkdownProse>{message.content}</MarkdownProse>
              )}
            </div>
            {isStreaming && (
              <span className="ml-0.5 inline-block animate-pulse text-brand-strong dark:text-brand-strong-dark" aria-hidden="true">
                ▍
              </span>
            )}
          </div>

          {message.status === 'done' && (
            <>
              {typeof message.grounded === 'number' && message.grounded > 0 && (
                // The compliance row (v2.2 footer-counts treatment): grounding
                // on the left, citations · verified tally on the right.
                <p className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                  <span className="flex items-center gap-1.5">
                    <CheckCircleIcon className="h-3.5 w-3.5 text-brand-strong/70 dark:text-brand-strong-dark/70" />
                    Grounded in {message.grounded} excerpt{message.grounded === 1 ? '' : 's'}
                  </span>
                  {!!citations?.length && (
                    <span className="ml-auto font-data">
                      {citations.length} citation{citations.length === 1 ? '' : 's'} · {verifiedCount} verified
                    </span>
                  )}
                </p>
              )}
              {message.citations && <SourcesList citations={message.citations} />}
              {/* Per-answer disclaimer (audit F7): the DS reference component always carried
                  this line — the wired renderer had dropped it. */}
              <AiDisclaimer lead={false} className="mt-2">
                {SEC_EDGAR_NOT_ADVICE}
              </AiDisclaimer>
              {showFollowups && onFollowup && message.followups && message.followups.length > 0 && (
                <FollowupChips followups={message.followups} onFollowup={onFollowup} />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

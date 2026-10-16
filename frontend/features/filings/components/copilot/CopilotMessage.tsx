'use client'

import { type ComponentProps, type ReactNode } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import { Button, countControlClass, cx } from '@/components/ui'
import AiDisclaimer, { SEC_EDGAR_NOT_ADVICE } from '@/components/AiDisclaimer'
import remarkGfm from 'remark-gfm'
import { citationVerificationLabel, SOURCE_MATCH_SCOPE } from './citationVerification'
import {
  ArrowClockwiseIcon,
  ArrowRightIcon,
  ArrowSquareOutIcon,
  BracketsCurlyIcon,
  ChatCircleTextIcon,
  CheckCircleIcon,
  LightningIcon,
  ProhibitIcon,
} from '@/lib/icons'
import { injectCitationMarkers } from '@/lib/citationMarkers'
import { isCopilotFairUseLimit, isXbrlCitation, xbrlTag, type CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip, { isHttpUrl } from './CitationChip'

/* Visual language: the v2.2 "Ask answer" evidence block (frontend/DESIGN_SYSTEM.md,
   "Ask answer"): panel card chrome, mono answer register (.copilot-answer: DS
   type roles put Ask-this-Filing output in the data face), brand-tint bracket
   markers, footnote evidence rows with scoped source-check labels, and the
   matched-source count. The MACHINERY here (citation-chip
   injection, viewer deep-links, follow-ups) is the shipped contract pinned
   by the copilot test suites: restyle only.
   Answers arrive whole: the API publishes an answer only once its citations
   are admitted, and AskCopilotRail moves a message from 'reading' straight to
   'done' or 'error' (its token callback is a no-op). So the reading state's
   single calm indicator stays until the complete answer replaces it, and the
   assistant's background tool activity is never surfaced. There is no
   token-by-token state, so no raw-text view and no caret. */

export interface CopilotMessageData {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: CopilotCitation[]
  grounded?: number
  kind?: 'answer' | 'not_disclosed'
  // 'reading' (waiting for the admitted answer), then 'done' or 'error': answers arrive whole.
  status?: 'reading' | 'done' | 'error'
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
  // Issuer ticker + filing type: used by the "not disclosed" card to point to the right filing.
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
    return 'Full risk factors and the business overview usually live in the company’s 10-K. Executive pay is usually in its proxy statement.'
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
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-eyebrow text-text-secondary-light dark:text-text-secondary-dark">Ask next</p>
      <div className="flex flex-col gap-1.5">
        {followups.map((q, i) => (
          <button
            key={`${q}-${i}`}
            type="button"
            onClick={() => onFollowup(q)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border-light dark:border-white/10 bg-brand-weak dark:bg-white/5 px-2.5 py-1.5 text-left text-xs text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-border hover:bg-brand-weak/70 dark:hover:bg-white/10 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            <ChatCircleTextIcon className="h-3 w-3 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
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
    numerals, reader-style hairline tables, prose links. `inject` routes a
    text-bearing element's children through the citation-chip walker: the
    SAME coverage set as before the restyle (p/li/strong/em/td); everything
    else is style-only. A link prints what the model wrote, a figure or a
    date included, so it takes the prose links' rule in globals.css (the
    answer's own ink, underlined, sage under the pointer; D-030) and adds
    only its weight. */
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
      <a {...rest} className="font-semibold">
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
        className="border-b border-border-light px-2 py-1.5 text-left text-data-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:border-border-dark dark:text-text-secondary-dark"
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

/* The mono answer register: DS type roles render Ask-this-Filing output in
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

// Replace inline `[n]`/`[F#]` markers with interactive CitationChips via the shared walker (also
// used by the Multi-Period Analysis narrative renderer: see lib/citationMarkers.tsx).
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


/** Attribute the existing source check; excerpt matching is not whole-answer verification. A label
    that carries a verification claim is 12px, never data-xs (tests/unit/dataXsAllowlist.spec.ts, which
    reads both states because both render through citationVerificationLabel). The badge may shrink and
    wrap its words, so at an enlarged text size it stays inside the card (it wraps onto its own line first). */
function TrustBadge({ citation }: { citation: CopilotCitation }) {
  return citation.verified ? (
    <span className={`inline-flex max-w-full items-center gap-1 rounded-full px-2 py-px text-xs font-semibold ${CHIP}`}>
      <CheckCircleIcon className="h-2.5 w-2.5" aria-hidden="true" />
      {citationVerificationLabel(citation)}
    </span>
  ) : (
    <span className="inline-flex max-w-full items-center rounded-full border border-border-light bg-white px-2 py-px text-xs font-medium text-text-secondary-light dark:border-border-dark dark:bg-white/5 dark:text-text-secondary-dark">
      {citationVerificationLabel(citation)}
    </span>
  )
}

/* Footnote evidence rows (v2.2): bracket marker chip + brand-rail excerpt
   blockquote (XBRL facts swap the quote register for the braces glyph, the
   XBRL fact's reserved mark, + concept
   anchor + tabular figure) + locator link + trust badge. The decorative curly
   quotes are pseudo-elements so the excerpt stays an exact text node. A
   locator prints the citation's section name as the model wrote it ("Item 7.
   MD&A"), so it is the count control's link (D-030): the secondary ink at
   rest, sage and the underline under the pointer, the brand ring on focus. */
const LOCATOR_LINK = cx('inline-flex min-w-0 max-w-full items-center gap-1 rounded-sm text-xs font-semibold', countControlClass('link'))

/** The locator's new-tab cue, as the app's other links to the original draw it. */
function OpensOriginal() {
  return (
    <>
      <ArrowSquareOutIcon aria-hidden="true" className="h-3 w-3 shrink-0" />
      <span className="sr-only"> (opens in a new tab)</span>
    </>
  )
}

function SourcesList({ citations }: { citations: CopilotCitation[] }) {
  if (!citations.length) return null
  return (
    <div className="mt-3 border-t border-border-light dark:border-white/10 pt-2.5">
      <p className="mb-2 text-xs font-semibold uppercase tracking-eyebrow text-text-secondary-light dark:text-text-secondary-dark">Sources</p>
      {citations.some((c) => c.verified) && (
        <p className="mb-2 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          {SOURCE_MATCH_SCOPE}
        </p>
      )}
      <ol className="space-y-3">
        {citations.map((c, i) => {
          const isFact = isXbrlCitation(c)
          const tag = isFact ? xbrlTag(c) : null
          return (
            <li key={`${c.n}-${i}`} className="flex gap-2.5 text-xs">
              <span
                className={`flex h-[18px] min-w-[18px] flex-none items-center justify-center rounded border px-1 font-data text-data-xs font-semibold ${CHIP}`}
              >
                [{String(c.n).toUpperCase()}]
              </span>
              {isFact ? (
                <div className="min-w-0 flex-1">
                  <div className="border-l-2 border-brand-border pl-3 dark:border-brand-border-dark">
                    {tag && (
                      <div className="flex items-start gap-1.5">
                        <span className="mt-px text-brand-strong dark:text-brand-strong-dark">
                          <BracketsCurlyIcon className="h-3.5 w-3.5 flex-none" aria-hidden="true" />
                        </span>
                        <span className="min-w-0 break-all font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">{tag}</span>
                      </div>
                    )}
                    <p className="tnum mt-1 break-words font-data text-xs leading-relaxed text-text-primary-light dark:text-text-primary-dark">
                      {c.excerpt}
                    </p>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {isHttpUrl(c.fragment_url) ? (
                      <a href={c.fragment_url} target="_blank" rel="noopener noreferrer" className={LOCATOR_LINK}>
                        <span className="min-w-0 break-words">{c.section_ref ?? 'XBRL'} · EDGAR</span>
                        <OpensOriginal />
                      </a>
                    ) : c.section_ref ? (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">{c.section_ref}</span>
                    ) : null}
                    <TrustBadge citation={c} />
                  </div>
                </div>
              ) : (
                <div className="min-w-0 flex-1">
                  <blockquote className="break-words border-l-2 border-brand-border pl-3 font-data text-xs leading-relaxed text-text-secondary-light before:content-['“'] after:content-['”'] dark:border-brand-border-dark dark:text-text-secondary-dark">
                    {c.excerpt}
                  </blockquote>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {isHttpUrl(c.fragment_url) ? (
                      <a href={c.fragment_url} target="_blank" rel="noopener noreferrer" className={LOCATOR_LINK}>
                        <span className="min-w-0 break-words">{c.section_ref ?? 'View in filing'}</span>
                        <OpensOriginal />
                      </a>
                    ) : c.section_ref ? (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">{c.section_ref}</span>
                    ) : (
                      <span className="font-medium text-text-tertiary-light dark:text-text-secondary-dark">Excerpt {c.n}</span>
                    )}
                    <TrustBadge citation={c} />
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

  // --- Assistant: plan card. A spent allowance, a Pro-only gate or the Pro fair-use cap is a plan
  // fact, not a failure: the quiet answer card (panel, hairline, secondary ink, role="status"), never
  // the error tint or role="alert" (CopilotMessage.spec.tsx, statusTintsOnlyForStatus). The server's
  // sentence says what happened; upgrading cannot lift the fair-use cap, so that card has no button. The
  // rail turns the reading card into this one, and React keeps the element, so the reading card is already
  // this status region and a screen reader announces the sentence when it arrives (below).
  if (message.status === 'error' && isPaywallError) {
    const fairUse = isCopilotFairUseLimit(message.error || '')
    return (
      <div role="status" className={ANSWER_CARD}>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">{message.error}</p>
        {!fairUse && onUpgrade && (
          <div className="mt-2.5">
            <Button size="sm" onClick={onUpgrade} leftIcon={<LightningIcon className="h-3.5 w-3.5" aria-hidden="true" />}>
              Upgrade to Pro
            </Button>
          </div>
        )}
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
          {onRetry && (
            <Button variant="secondary" size="sm" onClick={onRetry} leftIcon={<ArrowClockwiseIcon className="h-3.5 w-3.5" />}>
              Retry
            </Button>
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
          <span className="text-xs font-semibold uppercase tracking-eyebrow">Not disclosed in this filing</span>
        </div>
        <p className="text-text-secondary-light dark:text-text-secondary-dark">{message.content}</p>
        {(hint || ticker) && (
          <div className="mt-2.5 border-t border-border-light dark:border-white/10 pt-2.5">
            {hint && <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{hint}</p>}
            {ticker && (
              <Link
                href={`/company/${encodeURIComponent(ticker)}`}
                className={`${hint ? 'mt-1.5 ' : ''}inline-flex items-center gap-1 text-xs font-medium text-brand-strong dark:text-brand-strong-dark hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark`}
              >
                Browse {ticker}’s other filings
                <ArrowRightIcon className="h-3 w-3" />
              </Link>
            )}
          </div>
        )}
        {/* A dead end without a next step strands the user: surface the "questions this
            filing CAN answer" follow-ups the backend now sends with not_disclosed verdicts. */}
        {showFollowups && onFollowup && message.followups && message.followups.length > 0 && (
          <FollowupChips followups={message.followups} onFollowup={onFollowup} />
        )}
      </div>
    )
  }

  // --- Assistant: reading / done answer ---
  const isReading = message.status === 'reading' && message.content.length === 0
  const isDone = message.status === 'done'
  // Inject interactive citation chips only once citations are known (a completed `answer`).
  // (The not_disclosed branch already returned above, so this is always an `answer`.)
  const citations = message.citations
  const showChips = isDone && !!citations && citations.length > 0

  return (
    // While it reads, the card is a status region: a status region announces text added to it, never text it was
    // created with, so the plan card's sentence (above) is heard because it lands in this element. A done answer
    // drops the role and is not announced.
    <div role={isReading ? 'status' : undefined} className={ANSWER_CARD}>
      {isReading ? (
        // A single calm indicator while the answer is grounded: the assistant's
        // background tool activity is deliberately not surfaced to the user.
        <p className="flex items-center gap-2 text-text-secondary-light dark:text-text-secondary-dark">
          <span aria-hidden="true" className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong motion-reduce:animate-none dark:bg-brand-strong-dark" />
          Reading the filing…
        </p>
      ) : (
        <>
          <div>
            {showChips ? (
              <MarkdownProseWithCitations citations={citations!}>
                {message.content}
              </MarkdownProseWithCitations>
            ) : (
              <MarkdownProse>{message.content}</MarkdownProse>
            )}
          </div>

          {message.status === 'done' && (
            <>
              {typeof message.grounded === 'number' && message.grounded > 0 && (
                // One count, said once: it describes located evidence, not verified answer claims.
                <p className="mt-2.5 flex items-center gap-1.5 text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                  <CheckCircleIcon className="h-3.5 w-3.5 text-brand-strong/70 dark:text-brand-strong-dark/70" />
                  {message.grounded} matched source{message.grounded === 1 ? '' : 's'}
                </p>
              )}
              {message.citations && <SourcesList citations={message.citations} />}
              {/* Per-answer disclaimer (audit F7): the line is part of the answer card's contract,
                  so every done answer carries it. */}
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

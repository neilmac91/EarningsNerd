'use client'

import { Children, cloneElement, Fragment, isValidElement, type ReactElement, type ReactNode } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowRight, Ban, CheckCircle2, ExternalLink, Loader2, Minus, RotateCw, Sparkles } from 'lucide-react'
import { isXbrlCitation, xbrlTag, type CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip, { isHttpUrl } from './CitationChip'

// A single "show the work" step (a numeric/XBRL tool call) shown live while the answer is forming.
export interface CopilotStep {
  label: string
  done: boolean
  ok: boolean
}

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
  // Live tool-activity steps ("Looking up revenue… ✓"), surfaced while reading/streaming.
  steps?: CopilotStep[]
  // 2-3 suggested next questions, shown as tappable chips under the latest answer.
  followups?: string[]
}

// Live "show the work" ticker: the numeric tools the assistant is calling as it grounds its answer.
function ActivityTicker({ steps }: { steps: CopilotStep[] }) {
  return (
    <ul className="mb-2 space-y-1" aria-label="Working">
      {steps.map((s, i) => (
        <li key={`${s.label}-${i}`} className="flex items-center gap-2 text-[12px]">
          {!s.done ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
          ) : s.ok ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
          ) : (
            <Minus className="h-3.5 w-3.5 shrink-0 text-text-secondary-light dark:text-text-secondary-dark" aria-hidden="true" />
          )}
          <span className={s.done ? 'text-text-secondary-light dark:text-text-secondary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}>
            {s.label}
            {s.done ? '' : '…'}
            <span className="sr-only">{s.done ? (s.ok ? ' (completed)' : ' (failed)') : ' (in progress)'}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

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
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">Ask next</p>
      <div className="flex flex-col gap-1.5">
        {followups.map((q, i) => (
          <button
            key={`${q}-${i}`}
            type="button"
            onClick={() => onFollowup(q)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border-light dark:border-white/10 bg-brand-weak dark:bg-slate-800/40 px-2.5 py-1.5 text-left text-xs text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-light/30 hover:bg-brand-weak/70 dark:hover:bg-slate-800"
          >
            <Sparkles className="h-3 w-3 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function MarkdownProse({ children }: { children: string }) {
  return (
    <div className="prose dark:prose-invert prose-sm max-w-none break-words text-text-secondary-light dark:text-text-secondary-dark prose-p:my-2 prose-headings:text-text-primary-light dark:prose-headings:text-text-primary-dark prose-strong:text-text-primary-light dark:prose-strong:text-text-primary-dark prose-a:text-brand-strong dark:prose-a:text-brand-strong-dark">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}

// While tokens are still arriving we render the raw text (whitespace-preserving) instead of
// re-parsing the growing markdown on every frame — markdown (with citation chips) is rendered once
// the `complete` event lands. Re-parsing a markdown string that grows by a token each frame is the
// O(n²) cost the streaming view used to pay; a plain text node is a near-free update. `pre-wrap`
// keeps paragraph breaks readable mid-stream; the formatted answer snaps in when the stream ends.
function StreamingText({ children }: { children: string }) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
      {children}
    </div>
  )
}

// Walk a react-markdown subtree and replace inline `[n]` markers with interactive CitationChips.
// Only `[n]` whose number matches a known citation becomes a chip; any other `[n]` stays literal
// text (e.g. the model emitted a bracket that isn't a real citation). Recurses into arrays and
// into element children so chips render inside <strong>, <em>, <li>, <td>, etc.
function injectCitations(children: ReactNode, citations: CopilotCitation[]): ReactNode {
  // Key by uppercased string so both numeric excerpt markers ([1]) and "F#" tool-figure markers
  // ([F1]) match. Normalization here MUST mirror the backend's cited-marker matcher.
  const byN = new Map(citations.map((c) => [String(c.n).toUpperCase(), c]))

  const walk = (node: ReactNode, keyPrefix: string): ReactNode => {
    if (typeof node === 'string') {
      // Split keeping the captured marker; even indices are literal text, odd are `[n]`/`[F n]` ids.
      // Case-insensitive + whitespace-tolerant so a minor LLM variation ([f1], [F 1]) still renders.
      const parts = node.split(/\[(F?\s*\d+)\]/gi)
      if (parts.length === 1) return node
      const out: ReactNode[] = []
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i]
        if (i % 2 === 1) {
          const citation = byN.get(part.replace(/\s+/g, '').toUpperCase())
          if (citation) {
            out.push(<CitationChip key={`${keyPrefix}-cite-${i}`} citation={citation} />)
          } else {
            // No matching citation — preserve the literal marker.
            out.push(`[${part}]`)
          }
        } else if (part) {
          out.push(part)
        }
      }
      return out
    }

    if (Array.isArray(node)) {
      return node.map((child, i) => (
        <Fragment key={`${keyPrefix}-${i}`}>{walk(child, `${keyPrefix}-${i}`)}</Fragment>
      ))
    }

    if (isValidElement(node)) {
      const el = node as ReactElement<{ children?: ReactNode }>
      if (el.props?.children == null) return node
      return cloneElement(el, undefined, walk(el.props.children, `${keyPrefix}-c`))
    }

    return node
  }

  return Children.toArray(children).map((child, i) => (
    <Fragment key={`cite-root-${i}`}>{walk(child, `root-${i}`)}</Fragment>
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
    <div className="prose dark:prose-invert prose-sm max-w-none break-words text-text-secondary-light dark:text-text-secondary-dark prose-p:my-2 prose-headings:text-text-primary-light dark:prose-headings:text-text-primary-dark prose-strong:text-text-primary-light dark:prose-strong:text-text-primary-dark prose-a:text-brand-strong dark:prose-a:text-brand-strong-dark">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children: c }) => <p>{injectCitations(c, citations)}</p>,
          li: ({ children: c }) => <li>{injectCitations(c, citations)}</li>,
          strong: ({ children: c }) => <strong>{injectCitations(c, citations)}</strong>,
          em: ({ children: c }) => <em>{injectCitations(c, citations)}</em>,
          td: ({ children: c }) => <td>{injectCitations(c, citations)}</td>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}

function SourcesList({ citations }: { citations: CopilotCitation[] }) {
  if (!citations.length) return null
  return (
    <div className="mt-3 border-t border-border-light dark:border-white/10 pt-2.5">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">Sources</p>
      <ul className="space-y-1">
        {citations.map((c) => {
          const label = c.section_ref || `Excerpt ${c.n}`
          const rowClass =
            'flex items-start gap-2 rounded-md px-1.5 py-1 text-xs text-text-secondary-light dark:text-text-secondary-dark'
          const badge = c.verified ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-brand-strong dark:text-brand-strong-dark">
              <CheckCircle2 className="h-3 w-3" />
              Verified
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-text-secondary-light dark:text-text-secondary-dark">
              <ExternalLink className="h-3 w-3" />
              Cited
            </span>
          )
          const isFact = isXbrlCitation(c)
          const tag = isFact ? xbrlTag(c) : null
          // XBRL facts are figures, not quotes — render them as a dense data row: the value in
          // monospace tabular figures (so digits align) with the source tag beneath, rather than
          // the prose excerpt treatment used for filing-text citations.
          const content = isFact ? (
            <>
              <span className="mt-px font-mono text-[11px] font-semibold text-brand-strong dark:text-brand-strong-dark">[{c.n}]</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-mono text-[12px] tabular-nums text-text-primary-light dark:text-text-primary-dark">
                    {c.excerpt}
                  </span>
                  {badge}
                </span>
                {tag && (
                  <span className="mt-0.5 block truncate font-mono text-[10px] text-text-secondary-light dark:text-text-secondary-dark">{tag}</span>
                )}
              </span>
            </>
          ) : (
            <>
              <span className="mt-px font-mono text-[11px] font-semibold text-brand-strong dark:text-brand-strong-dark">[{c.n}]</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate">{label}</span>
                  {badge}
                </span>
                <span className="mt-0.5 block line-clamp-2 text-[11px] text-text-secondary-light dark:text-text-secondary-dark">{c.excerpt}</span>
              </span>
            </>
          )
          return (
            <li key={c.n}>
              {isHttpUrl(c.fragment_url) ? (
                <a
                  href={c.fragment_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${rowClass} transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:hover:bg-white/5 dark:hover:text-text-primary-dark`}
                >
                  {content}
                  <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-text-secondary-light dark:text-text-secondary-dark" />
                </a>
              ) : (
                <div className={rowClass}>{content}</div>
              )}
            </li>
          )
        })}
      </ul>
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
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-weak dark:bg-white/5 px-3.5 py-2 text-sm text-text-primary-light dark:text-text-primary-dark ring-1 ring-brand-light/30">
          {message.content}
        </div>
      </div>
    )
  }

  // --- Assistant: error bubble ---
  if (message.status === 'error') {
    return (
      <div className="rounded-2xl rounded-bl-sm border border-error-light/30 dark:border-error-dark/30 bg-error-light/10 dark:bg-error-dark/10 px-3.5 py-3 text-sm">
        <p className="text-error-light dark:text-error-dark">{message.error || 'Something went wrong.'}</p>
        <div className="mt-2.5">
          {isPaywallError ? (
            onUpgrade && (
              <button
                type="button"
                onClick={onUpgrade}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-3 py-1.5 text-xs font-semibold transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Upgrade to Pro
              </button>
            )
          ) : (
            onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border-light dark:border-white/15 bg-panel-light dark:bg-white/5 px-3 py-1.5 text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-brand-weak dark:hover:bg-white/10"
              >
                <RotateCw className="h-3.5 w-3.5" />
                Retry
              </button>
            )
          )}
        </div>
      </div>
    )
  }

  // --- Assistant: "not disclosed" card (visually distinct: slate, no mint) ---
  if (message.kind === 'not_disclosed') {
    const hint = notDisclosedHint(filingType)
    return (
      <div className="rounded-2xl rounded-bl-sm border border-border-light dark:border-white/10 bg-brand-weak dark:bg-slate-800/60 px-3.5 py-3 text-sm">
        <div className="mb-1.5 flex items-center gap-2 text-text-secondary-light dark:text-text-secondary-dark">
          <Ban className="h-4 w-4" />
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
                <ArrowRight className="h-3 w-3" />
              </Link>
            )}
          </div>
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
  const steps = message.steps ?? []
  // Show the live work ticker while the answer is forming (reading or streaming), not once done.
  const showTicker = (isReading || isStreaming) && steps.length > 0

  return (
    <div className="rounded-2xl rounded-bl-sm border border-border-light dark:border-white/10 bg-brand-weak dark:bg-slate-800/40 px-3.5 py-3 text-sm">
      {showTicker && <ActivityTicker steps={steps} />}
      {isReading ? (
        steps.length > 0 ? null : (
          <p className="flex items-center gap-2 text-text-secondary-light dark:text-text-secondary-dark">
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong dark:bg-brand-strong-dark" />
            Reading the filing…
          </p>
        )
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
                <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
                  <CheckCircle2 className="h-3.5 w-3.5 text-brand-strong/70 dark:text-brand-strong-dark/70" />
                  Grounded in {message.grounded} excerpt{message.grounded === 1 ? '' : 's'}
                </p>
              )}
              {message.citations && <SourcesList citations={message.citations} />}
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

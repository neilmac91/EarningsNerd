'use client'

import { Children, cloneElement, Fragment, isValidElement, type ReactElement, type ReactNode } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Ban, CheckCircle2, ExternalLink, RotateCw, Sparkles } from 'lucide-react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip, { isHttpUrl } from './CitationChip'

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
}

interface CopilotMessageProps {
  message: CopilotMessageData
  onRetry?: () => void
  isPaywallError?: boolean
}

function MarkdownProse({ children }: { children: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none break-words text-slate-200 prose-p:my-2 prose-headings:text-white prose-strong:text-white prose-a:text-mint-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}

// Walk a react-markdown subtree and replace inline `[n]` markers with interactive CitationChips.
// Only `[n]` whose number matches a known citation becomes a chip; any other `[n]` stays literal
// text (e.g. the model emitted a bracket that isn't a real citation). Recurses into arrays and
// into element children so chips render inside <strong>, <em>, <li>, <td>, etc.
function injectCitations(children: ReactNode, citations: CopilotCitation[]): ReactNode {
  const byN = new Map(citations.map((c) => [c.n, c]))

  const walk = (node: ReactNode, keyPrefix: string): ReactNode => {
    if (typeof node === 'string') {
      // Split keeping the captured number; even indices are literal text, odd are `[n]` numbers.
      const parts = node.split(/\[(\d+)\]/g)
      if (parts.length === 1) return node
      const out: ReactNode[] = []
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i]
        if (i % 2 === 1) {
          const citation = byN.get(Number(part))
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
    <div className="prose prose-invert prose-sm max-w-none break-words text-slate-200 prose-p:my-2 prose-headings:text-white prose-strong:text-white prose-a:text-mint-300">
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
    <div className="mt-3 border-t border-white/10 pt-2.5">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Sources</p>
      <ul className="space-y-1">
        {citations.map((c) => {
          const label = c.section_ref || `Excerpt ${c.n}`
          const rowClass =
            'flex items-start gap-2 rounded-md px-1.5 py-1 text-xs text-slate-300'
          const badge = c.verified ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-mint-300">
              <CheckCircle2 className="h-3 w-3" />
              Verified
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-slate-500">
              <ExternalLink className="h-3 w-3" />
              Cited
            </span>
          )
          const content = (
            <>
              <span className="mt-px font-mono text-[11px] font-semibold text-mint-300">[{c.n}]</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate">{label}</span>
                  {badge}
                </span>
                <span className="mt-0.5 block line-clamp-2 text-[11px] text-slate-400">{c.excerpt}</span>
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
                  className={`${rowClass} transition-colors hover:bg-white/5 hover:text-white`}
                >
                  {content}
                  <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-slate-500" />
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

export default function CopilotMessage({ message, onRetry, isPaywallError }: CopilotMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-mint-500/15 px-3.5 py-2 text-sm text-slate-100 ring-1 ring-mint-500/20">
          {message.content}
        </div>
      </div>
    )
  }

  // --- Assistant: error bubble ---
  if (message.status === 'error') {
    return (
      <div className="rounded-2xl rounded-bl-sm border border-rose-500/30 bg-rose-500/10 px-3.5 py-3 text-sm">
        <p className="text-rose-200">{message.error || 'Something went wrong.'}</p>
        <div className="mt-2.5">
          {isPaywallError ? (
            <Link
              href="/pricing"
              className="inline-flex items-center gap-1.5 rounded-lg bg-mint-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-mint-400"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Upgrade to Pro
            </Link>
          ) : (
            onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-white/10"
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
    return (
      <div className="rounded-2xl rounded-bl-sm border border-white/10 bg-slate-800/60 px-3.5 py-3 text-sm">
        <div className="mb-1.5 flex items-center gap-2 text-slate-400">
          <Ban className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">Not disclosed in this filing</span>
        </div>
        <p className="text-slate-300">{message.content}</p>
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

  return (
    <div className="rounded-2xl rounded-bl-sm border border-white/10 bg-slate-800/40 px-3.5 py-3 text-sm">
      {isReading ? (
        <p className="flex items-center gap-2 text-slate-400">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-mint-400" />
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
              ) : (
                <MarkdownProse>{message.content}</MarkdownProse>
              )}
            </div>
            {isStreaming && (
              <span className="ml-0.5 inline-block animate-pulse text-mint-400" aria-hidden="true">
                ▍
              </span>
            )}
          </div>

          {message.status === 'done' && (
            <>
              {typeof message.grounded === 'number' && message.grounded > 0 && (
                <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <CheckCircle2 className="h-3.5 w-3.5 text-mint-500/70" />
                  Grounded in {message.grounded} excerpt{message.grounded === 1 ? '' : 's'}
                </p>
              )}
              {message.citations && <SourcesList citations={message.citations} />}
            </>
          )}
        </>
      )}
    </div>
  )
}

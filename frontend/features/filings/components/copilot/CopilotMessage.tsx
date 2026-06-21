'use client'

import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Ban, CheckCircle2, ExternalLink, RotateCw, Sparkles } from 'lucide-react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

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

// Only render a citation as an active link when it's an http(s) URL. Defense-in-depth against a
// malicious/unexpected scheme (e.g. javascript:) reaching the href — the backend builds these from
// SEC URLs, but the excerpt portion is model-influenced, so we validate before linking.
const isHttpUrl = (url: string | null): url is string =>
  !!url && (url.startsWith('https://') || url.startsWith('http://'))

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
          const content = (
            <>
              <span className="mt-px font-mono text-[11px] font-semibold text-mint-300">[{c.n}]</span>
              <span className="min-w-0 flex-1 truncate">{label}</span>
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
              <MarkdownProse>{message.content}</MarkdownProse>
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

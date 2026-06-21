'use client'

import { useEffect, useRef, useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import {
  askFilingStream,
  isCopilotPaywallError,
  type CopilotCompletion,
  type CopilotTurn,
} from '@/features/filings/api/copilot-api'
import CopilotComposer from './CopilotComposer'
import CopilotMessage, { type CopilotMessageData } from './CopilotMessage'
import CopilotTeaser from './CopilotTeaser'
import { analytics } from '@/lib/analytics'

interface AskCopilotRailProps {
  filingId: number
  filingType: string
  ticker: string | null
  companyName: string | null
  summaryAvailable: boolean
  isPro: boolean
  isAuthenticated: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Number of prior turns sent back as `history` so the model has conversational context
// without ballooning the prompt.
const HISTORY_LIMIT = 6

const isTenQ = (filingType: string): boolean => /10-?q/i.test(filingType)

function starterQuestions(filingType: string): string[] {
  if (isTenQ(filingType)) {
    return [
      'How did revenue and margins change this quarter?',
      'What are the top risks?',
      'What did management say about demand?',
      'Any changes to guidance?',
    ]
  }
  // 10-K (and any non-10-Q) defaults
  return [
    'What are the biggest risks this year?',
    'How did revenue and profitability trend?',
    'What is the company’s competitive position?',
    'What did management highlight in the MD&A?',
  ]
}

let messageSeq = 0
const nextId = () => `copilot-${Date.now()}-${messageSeq++}`

export default function AskCopilotRail({
  filingId,
  filingType,
  ticker,
  companyName,
  summaryAvailable,
  isPro,
  isAuthenticated,
  open,
  onOpenChange,
}: AskCopilotRailProps) {
  const [messages, setMessages] = useState<CopilotMessageData[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  // Keep the last asked question so the Retry button can re-run it.
  const lastQuestionRef = useRef<string | null>(null)
  // Mirror of `messages` so handlers/submit can read the latest list synchronously without
  // nesting state setters (which React drops) or stale closures.
  const messagesRef = useRef<CopilotMessageData[]>([])
  const setMessagesTracked = (
    updater: CopilotMessageData[] | ((prev: CopilotMessageData[]) => CopilotMessageData[])
  ) => {
    const next = typeof updater === 'function' ? updater(messagesRef.current) : updater
    messagesRef.current = next
    setMessages(next)
  }

  // Abort any in-flight stream when the panel closes or the component unmounts.
  const abortStream = () => {
    abortRef.current?.abort()
    abortRef.current = null
  }
  useEffect(() => {
    if (!open) abortStream()
  }, [open])
  useEffect(() => {
    return () => abortStream()
  }, [])

  // Auto-scroll to the newest message as content streams in.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const updateAssistant = (
    id: string,
    patch: Partial<CopilotMessageData> | ((prev: CopilotMessageData) => Partial<CopilotMessageData>)
  ) => {
    setMessagesTracked((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m))
    )
  }

  const runQuestion = (question: string, priorMessages: CopilotMessageData[]) => {
    lastQuestionRef.current = question
    // Build history from finalized turns only (user + completed assistant answers).
    const history: CopilotTurn[] = priorMessages
      .filter((m) => (m.role === 'user' || m.status === 'done') && m.content.trim().length > 0)
      .map((m) => ({ role: m.role, content: m.content }))
      .slice(-HISTORY_LIMIT)

    const assistantId = nextId()
    setMessagesTracked([
      ...priorMessages,
      { id: nextId(), role: 'user', content: question },
      { id: assistantId, role: 'assistant', content: '', status: 'reading' },
    ])
    setIsStreaming(true)
    analytics.copilotQuestionAsked({ filingId, ticker, filingType })

    const controller = new AbortController()
    abortRef.current = controller

    askFilingStream(
      filingId,
      question,
      history,
      {
        onProgress: () => {
          updateAssistant(assistantId, (m) => (m.status === 'reading' ? { status: 'reading' } : {}))
        },
        onActivity: (a) => {
          updateAssistant(assistantId, (m) => {
            const steps = m.steps ? [...m.steps] : []
            if (a.phase === 'start') {
              steps.push({ label: a.label, done: false, ok: true })
            } else {
              // Mark the most recent in-progress step as finished (tools run sequentially).
              for (let i = steps.length - 1; i >= 0; i--) {
                if (!steps[i].done) {
                  steps[i] = { ...steps[i], done: true, ok: a.ok }
                  break
                }
              }
            }
            return { steps }
          })
        },
        onToken: (text) => {
          updateAssistant(assistantId, (m) => ({
            content: m.content + text,
            status: 'streaming',
          }))
        },
        onNotDisclosed: (answer) => {
          updateAssistant(assistantId, {
            content: answer,
            kind: 'not_disclosed',
            status: 'done',
          })
        },
        onComplete: (c: CopilotCompletion) => {
          updateAssistant(assistantId, {
            content: c.answer,
            citations: c.citations,
            grounded: c.grounded,
            kind: c.kind,
            followups: c.followups,
            status: 'done',
          })
          analytics.copilotAnswerCompleted({
            filingId,
            ticker,
            filingType,
            kind: c.kind,
            grounded: c.grounded,
            citations: c.citations.length,
            usedXbrl: c.citations.some(
              (cit) => cit?.section_ref?.toUpperCase().startsWith('XBRL') ?? false,
            ),
          })
          setIsStreaming(false)
          abortRef.current = null
        },
        onError: (msg) => {
          updateAssistant(assistantId, { status: 'error', error: msg })
          analytics.copilotAnswerErrored({ filingId, message: msg })
          setIsStreaming(false)
          abortRef.current = null
        },
      },
      controller.signal
    )
  }

  const handleSubmit = (question: string) => {
    if (isStreaming) return
    runQuestion(question, messagesRef.current)
  }

  const handleRetry = () => {
    const last = lastQuestionRef.current
    if (!last || isStreaming) return
    // Drop the trailing errored assistant turn (and its user turn) before re-asking.
    let trimmed = messagesRef.current
    if (trimmed.length && trimmed[trimmed.length - 1].role === 'assistant') {
      trimmed = trimmed.slice(0, -1)
    }
    if (trimmed.length && trimmed[trimmed.length - 1].role === 'user') {
      trimmed = trimmed.slice(0, -1)
    }
    runQuestion(last, trimmed)
  }

  // Need a summary to cite against — don't render the rail at all without one.
  if (!summaryAvailable) return null

  // --- Launcher (closed) ---
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-mint-500 px-4 py-3 text-sm font-semibold text-slate-950 shadow-glow-mint transition-colors hover:bg-mint-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-300"
        aria-label="Ask this Filing"
      >
        <Sparkles className="h-4 w-4" />
        Ask this Filing
      </button>
    )
  }

  const subjectLabel = ticker || companyName || 'this filing'

  // --- Panel (open) ---
  return (
    <div
      role="dialog"
      aria-label="Ask this Filing"
      className="fixed inset-x-0 bottom-0 z-40 flex max-h-[80vh] flex-col rounded-t-2xl border border-white/10 bg-slate-900 text-slate-100 shadow-2xl lg:inset-x-auto lg:bottom-0 lg:right-0 lg:top-16 lg:max-h-none lg:w-[420px] lg:rounded-none lg:border-y-0 lg:border-l"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Sparkles className="h-4 w-4 shrink-0 text-mint-400" />
          <h2 className="truncate text-sm font-semibold text-white">Ask this Filing</h2>
          <span className="hidden shrink-0 items-center gap-1.5 rounded-full bg-mint-500/10 px-2 py-0.5 text-[11px] font-medium text-mint-300 ring-1 ring-mint-500/20 sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-mint-400" aria-hidden="true" />
            Scoped to this filing
          </span>
        </div>
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Close"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* FREE locked teaser (blurred sample + value props + upsell + paywall analytics). */}
      {!isPro ? (
        <CopilotTeaser
          filingId={filingId}
          filingType={filingType}
          ticker={ticker}
          companyName={companyName}
          isAuthenticated={isAuthenticated}
        />
      ) : (
        <>
          {/* Messages / empty state */}
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div>
                <p className="text-sm text-slate-300">
                  Ask anything about {subjectLabel}’s {filingType}. Answers are grounded in the filing and
                  cite the excerpts they came from.
                </p>
                <p className="mt-4 mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Try asking
                </p>
                <div className="flex flex-col gap-2">
                  {starterQuestions(filingType).map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSubmit(q)}
                      className="rounded-xl border border-white/10 bg-slate-800/40 px-3 py-2 text-left text-sm text-slate-200 transition-colors hover:border-mint-500/40 hover:bg-slate-800"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, idx) => (
                <CopilotMessage
                  key={m.id}
                  message={m}
                  onRetry={handleRetry}
                  isPaywallError={m.status === 'error' && isCopilotPaywallError(m.error || '')}
                  onFollowup={handleSubmit}
                  // Only the latest answer offers follow-ups (and not mid-stream).
                  showFollowups={idx === messages.length - 1 && !isStreaming}
                />
              ))
            )}
          </div>

          {/* Composer */}
          <CopilotComposer onSubmit={handleSubmit} disabled={isStreaming} />
        </>
      )}
    </div>
  )
}

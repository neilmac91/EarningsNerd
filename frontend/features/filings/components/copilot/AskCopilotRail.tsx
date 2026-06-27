'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { SparkleIcon, XIcon } from '@/lib/icons'
import {
  askFilingStream,
  isCopilotPaywallError,
  type CopilotCompletion,
  type CopilotTurn,
} from '@/features/filings/api/copilot-api'
import CopilotComposer, { type CopilotComposerHandle } from './CopilotComposer'
import CopilotMessage, { type CopilotMessageData } from './CopilotMessage'
import CopilotTeaser from './CopilotTeaser'
import { useFilingViewer } from './FilingViewerContext'
import { useSheetFocusTrap } from './useSheetFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { getUsage } from '@/features/subscriptions/api/subscriptions-api'
import UpgradeModal from '@/components/UpgradeModal'
import { analytics } from '@/lib/analytics'
import { starterQuestions } from './starterQuestions'

// Below lg the standalone overlay is a modal bottom-sheet; at lg+ it docks as a static side pane.
const MOBILE_MEDIA_QUERY = '(max-width: 1023.98px)'

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
  // Set by a "Ask about this" text selection to pre-fill the composer. `nonce` re-triggers on repeat.
  prefill?: { text: string; nonce: number } | null
  // 'overlay' (default): the panel floats fixed on the right (and as a bottom-sheet on mobile).
  // 'pane': on lg+ the panel fills its grid cell inside FilingWorkspace (reflow, not overlay); below
  // lg it still falls back to the bottom-sheet overlay.
  variant?: 'overlay' | 'pane'
  // When true, render body-only (no launcher, no dialog wrapper, no header): FilingWorkspace provides
  // the secondary-pane shell + the [Answer · Filing] tabs + close. The component stays mounted while
  // hidden so the conversation/stream survives view switches and close/reopen.
  embedded?: boolean
}

// Open-panel container classes per layout variant. Mobile (bottom-sheet) is identical; they differ
// only at lg+: overlay docks fixed on the right, pane fills the FilingWorkspace grid cell.
const PANEL_BASE =
  'fixed inset-x-0 bottom-0 z-40 flex max-h-[80vh] flex-col rounded-t-2xl border border-border-light bg-panel-light text-text-primary-light dark:border-white/10 dark:bg-slate-900 dark:text-text-primary-dark shadow-2xl'
const PANEL_VARIANT: Record<'overlay' | 'pane', string> = {
  overlay:
    'lg:inset-x-auto lg:bottom-0 lg:right-0 lg:top-16 lg:max-h-none lg:w-[420px] lg:rounded-none lg:border-y-0 lg:border-l',
  pane: 'lg:static lg:inset-auto lg:z-auto lg:h-full lg:w-full lg:max-h-none lg:rounded-none lg:border-y-0 lg:border-l lg:shadow-none',
}

// Number of prior turns sent back as `history` so the model has conversational context
// without ballooning the prompt.
const HISTORY_LIMIT = 6

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
  prefill,
  variant = 'overlay',
  embedded = false,
}: AskCopilotRailProps) {
  const [messages, setMessages] = useState<CopilotMessageData[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  // Contextual upgrade modal, opened from a paywall surface (FREE teaser CTA or a monthly-limit error).
  const [upgradeOpen, setUpgradeOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  // The standalone overlay panel container — owns the mobile focus trap (when !embedded).
  const panelRef = useRef<HTMLDivElement>(null)
  // The standalone launcher (closed state) — focus returns here when the sheet closes.
  const launcherRef = useRef<HTMLButtonElement>(null)
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

  // In the embedded layout the Copilot shares the pane with the filing view; only focus the composer
  // when the Copilot view is actually active (focusing it while the Filing tab is shown would steal
  // focus, and the hidden container can't take focus anyway). Standalone overlay is always "active".
  const viewer = useFilingViewer()
  const isCopilotActive = !embedded || (viewer?.activeView ?? 'copilot') === 'copilot'

  // Focus the composer when the Copilot opens or becomes the active view (launcher tap, ⌘K, a
  // citation flow that returns to the answer, or switching back via the [Answer · Filing] tabs).
  const composerRef = useRef<CopilotComposerHandle>(null)
  useEffect(() => {
    if (!open || !isPro || !isCopilotActive) return
    const raf = requestAnimationFrame(() => composerRef.current?.focus())
    return () => cancelAnimationFrame(raf)
  }, [open, isPro, isCopilotActive])

  // Pre-fill the composer from an "Ask about this" text selection (page sets `prefill` + opens us).
  const lastPrefillNonce = useRef(0)
  useEffect(() => {
    if (!prefill || !isPro || prefill.nonce === lastPrefillNonce.current) return
    lastPrefillNonce.current = prefill.nonce
    // Defer so the composer has mounted (the rail was opened in the same tick).
    const raf = requestAnimationFrame(() => composerRef.current?.prefill(prefill.text))
    return () => cancelAnimationFrame(raf)
  }, [prefill, isPro])

  // Below lg the standalone overlay acts as a modal (focus trap + scrim). When `embedded`,
  // FilingWorkspace owns the trap/scrim, so we disable the query entirely (isMobile stays false)
  // and never add a second one here.
  const isMobile = useMediaQuery(MOBILE_MEDIA_QUERY, !embedded)
  const modalActive = open && isMobile && !embedded

  // Mobile modal focus trap for the standalone overlay only. The hook also handles Escape (capture
  // phase + preventDefault), so the window Escape listener below won't double-fire when active.
  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange])
  useSheetFocusTrap({
    active: modalActive,
    containerRef: panelRef,
    onClose: handleClose,
    restoreFocusRef: launcherRef,
  })

  // PRO Copilot question usage → an honest "N of M left" pill. Fetched only for PRO (FREE has no
  // Copilot access) and only while open; refreshed after each answer (qa_count increments
  // server-side on completion).
  const queryClient = useQueryClient()
  const { data: usage } = useQuery({
    queryKey: ['copilot-usage'],
    queryFn: getUsage,
    // /usage is auth-gated; an anon user is never PRO, but gate on isAuthenticated too so we never
    // fire a guaranteed-401 from a public page.
    enabled: isAuthenticated && isPro && open,
    staleTime: 60_000,
  })

  // Keyboard: ⌘K / Ctrl+K (and "/" when not already typing) open + focus the rail; Escape closes it.
  useEffect(() => {
    if (!summaryAvailable) return
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing =
        !!target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      const openCombo = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'
      const slashCombo = e.key === '/' && !e.metaKey && !e.ctrlKey && !typing
      if (openCombo || slashCombo) {
        e.preventDefault()
        if (open) {
          // Already open → the focus-on-open effect won't re-fire, so focus directly.
          composerRef.current?.focus()
        } else {
          // Opening → the focus-on-open effect handles focus once the composer mounts.
          onOpenChange(true)
        }
      } else if (e.key === 'Escape' && open && !e.defaultPrevented) {
        // Don't steal Escape from a nested element that already handled it (popover, IME, …).
        onOpenChange(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange, summaryAvailable])

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
          // A question was metered server-side on completion — refresh the "N of M left" pill.
          queryClient.invalidateQueries({ queryKey: ['copilot-usage'] })
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

  // Record the CTA click (shown → clicked funnel) and open the contextual upgrade modal.
  const handleUpgrade = (entryPoint: string) => {
    analytics.paywallCtaClicked({ filingId, ticker, filingType, entryPoint })
    setUpgradeOpen(true)
  }

  // Need a summary to cite against — don't render the rail at all without one.
  if (!summaryAvailable) return null

  const subjectLabel = ticker || companyName || 'this filing'

  // The conversation surface (teaser for FREE, else messages + composer). Shared by the overlay
  // panel and the embedded (FilingWorkspace shell) layout so both exercise the same code path.
  const body = !isPro ? (
    <CopilotTeaser
      filingId={filingId}
      filingType={filingType}
      ticker={ticker}
      companyName={companyName}
      isAuthenticated={isAuthenticated}
      onUpgrade={() => handleUpgrade('copilot_rail')}
    />
  ) : (
    <>
      {/* Messages / empty state */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Ask anything about {subjectLabel}’s {filingType}. Answers are grounded in the filing and
              cite the excerpts they came from.
            </p>
            <p className="mt-4 mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
              Try asking
            </p>
            <div className="flex flex-col gap-2">
              {starterQuestions(filingType).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => handleSubmit(q)}
                  className="rounded-xl border border-border-light dark:border-white/10 bg-brand-weak dark:bg-slate-800/40 px-3 py-2 text-left text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-light/30 hover:bg-brand-weak/70 dark:hover:bg-slate-800"
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
              onUpgrade={() => handleUpgrade('copilot_limit')}
              ticker={ticker}
              filingType={filingType}
              onFollowup={handleSubmit}
              // Only the latest answer offers follow-ups (and not mid-stream).
              showFollowups={idx === messages.length - 1 && !isStreaming}
            />
          ))
        )}
      </div>

      {/* Composer */}
      <CopilotComposer ref={composerRef} onSubmit={handleSubmit} disabled={isStreaming} />

      {/* Honest PRO usage — a calm count, not a hard sell. Shows the generous monthly allowance. */}
      {usage && (
        <p className="px-4 pb-2 text-center text-[11px] text-text-secondary-light dark:text-text-secondary-dark">
          {Math.max(usage.qa_limit - usage.qa_used, 0).toLocaleString()} of{' '}
          {usage.qa_limit.toLocaleString()} questions left this month
        </p>
      )}
    </>
  )

  const upgradeModal = (
    <UpgradeModal
      open={upgradeOpen}
      onClose={() => setUpgradeOpen(false)}
      feature="The filing Copilot"
    />
  )

  // --- Embedded: body only; FilingWorkspace owns the shell, tabs, header and close. The component
  // stays mounted (workspace toggles visibility) so the stream/conversation survives view switches.
  if (embedded) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        {body}
        {upgradeModal}
      </div>
    )
  }

  // --- Launcher (closed) ---
  if (!open) {
    return (
      <button
        ref={launcherRef}
        type="button"
        onClick={() => onOpenChange(true)}
        aria-haspopup="dialog"
        aria-expanded={false}
        style={{ bottom: 'max(1.25rem, env(safe-area-inset-bottom))', right: 'max(1.25rem, env(safe-area-inset-right))' }}
        className="fixed z-40 inline-flex items-center gap-2 rounded-full bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-3 text-sm font-semibold shadow-e3 dark:shadow-none transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
        aria-label="Ask this Filing"
      >
        <SparkleIcon className="h-4 w-4" />
        Ask this Filing
        <kbd className="ml-1 hidden rounded border border-slate-950/25 bg-slate-950/10 px-1.5 py-0.5 text-[10px] font-semibold leading-none sm:inline-block">
          ⌘K
        </kbd>
      </button>
    )
  }

  // --- Panel (open, standalone overlay) ---
  return (
    <>
      {/* Mobile-only scrim behind the bottom-sheet (z-30 < panel's z-40). Tapping it closes the
          sheet. `lg:hidden` keeps it out of the desktop docked/static layout entirely. */}
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        onClick={handleClose}
        className="lg:hidden fixed inset-0 z-30 bg-black/50"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-label="Ask this Filing"
        aria-modal={modalActive ? true : undefined}
        className={`${PANEL_BASE} ${PANEL_VARIANT[variant]}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-2 border-b border-border-light dark:border-white/10 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <SparkleIcon className="h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark" />
            <h2 className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Ask this Filing</h2>
            <span className="hidden shrink-0 items-center gap-1.5 rounded-full bg-brand-weak dark:bg-white/5 px-2 py-0.5 text-[11px] font-medium text-brand-strong dark:text-brand-strong-dark ring-1 ring-brand-light/30 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-strong dark:bg-brand-strong-dark" aria-hidden="true" />
              Scoped to this filing
            </span>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        {body}
        {upgradeModal}
      </div>
    </>
  )
}

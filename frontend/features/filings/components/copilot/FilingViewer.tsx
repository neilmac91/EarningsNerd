'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink, FileText, Loader2, X } from 'lucide-react'
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
import { isHttpUrl } from './CitationChip'
import { useFilingViewer } from './FilingViewerContext'
import { clearCitationHighlight, highlightExcerptInDom } from './highlightInDom'

interface FilingViewerProps {
  filingId: number
  filingLabel: string
  secUrl: string | null
  // When true, render body-only inside FilingWorkspace's secondary-pane shell (no fixed drawer, no
  // own header/close). Visibility is driven by the shared `activeView` ('filing') from context, and
  // the component stays mounted so loaded content/highlight survive switching back to the answer.
  embedded?: boolean
}

type Status = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

/**
 * In-app filing reader (P7 / 1.1). Opens when a Copilot citation requests a highlight (via
 * FilingViewerContext) or when the user selects the "Filing" tab, lazy-loads the cached filing
 * markdown, renders it, and scrolls to + flash-highlights the cited passage in place. The SEC deep
 * link stays available as "open original". In `embedded` mode the surrounding shell owns the chrome.
 */
export default function FilingViewer({ filingId, filingLabel, secUrl, embedded = false }: FilingViewerProps) {
  const viewer = useFilingViewer()
  const [localOpen, setLocalOpen] = useState(false)
  const [status, setStatus] = useState<Status>('idle')
  const [content, setContent] = useState<string | null>(null)
  const [passageMissing, setPassageMissing] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const handledNonce = useRef(0)
  const statusRef = useRef<Status>('idle')
  statusRef.current = status

  // Embedded: visibility follows the shared view state. Standalone: local citation-driven open state.
  const active = embedded ? viewer?.activeView === 'filing' : localOpen

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const c = await fetchFilingContent(filingId)
      if (c.hasContent && c.markdownContent) {
        setContent(c.markdownContent)
        setStatus('ready')
      } else {
        setStatus('empty')
      }
    } catch {
      setStatus('error')
    }
  }, [filingId])

  const request = viewer?.request ?? null

  // A citation chip requested a highlight: (standalone) open the drawer, and load if we haven't yet.
  useEffect(() => {
    if (!request || request.nonce === handledNonce.current) return
    handledNonce.current = request.nonce
    if (!embedded) setLocalOpen(true)
    setPassageMissing(false)
    // Retry on 'error' too, so a transient fetch failure isn't permanent (a fresh click re-loads).
    if (statusRef.current === 'idle' || statusRef.current === 'error') void load()
  }, [request, load, embedded])

  // Embedded "Filing" tab opened with no citation: load the full filing on first activation.
  useEffect(() => {
    if (embedded && active && statusRef.current === 'idle') void load()
  }, [embedded, active, load])

  // Once content is rendered and a citation is pending, locate + highlight the passage.
  const activeExcerpt = request?.citation.excerpt
  const activeNonce = request?.nonce
  useEffect(() => {
    if (!active || status !== 'ready' || !activeExcerpt || !contentRef.current) return
    // Defer a frame so ReactMarkdown has painted before we walk its text nodes.
    const raf = window.requestAnimationFrame(() => {
      const found = contentRef.current
        ? highlightExcerptInDom(contentRef.current, activeExcerpt)
        : false
      setPassageMissing(!found)
    })
    return () => window.cancelAnimationFrame(raf)
  }, [active, status, activeExcerpt, activeNonce, content])

  // Tear down any lingering highlight when the viewer unmounts (pane closed / page left).
  useEffect(() => () => clearCitationHighlight(), [])

  const close = () => {
    clearCitationHighlight()
    setLocalOpen(false)
  }

  const openOriginal = isHttpUrl(secUrl) ? (
    <a
      href={secUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium text-mint-300 hover:underline"
    >
      Open original <ExternalLink className="h-3 w-3" />
    </a>
  ) : null

  // Shared inner content: the loading / empty / error / ready states.
  const inner = (
    <>
      {(status === 'idle' || status === 'loading') && (
        <p className="flex flex-1 items-center justify-center gap-2 px-6 py-12 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin text-mint-400" /> Loading the filing…
        </p>
      )}

      {(status === 'empty' || status === 'error') && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-12 text-center">
          <p className="text-sm text-slate-300">
            {status === 'error'
              ? 'Could not load the filing text.'
              : 'The full filing text is not available to view in-app yet.'}
          </p>
          {isHttpUrl(secUrl) && (
            <a
              href={secUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-mint-500 px-3 py-2 text-xs font-semibold text-slate-950 transition-colors hover:bg-mint-400"
            >
              Open the original on SEC.gov <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      )}

      {status === 'ready' && (
        <div className="flex min-h-0 flex-1 flex-col">
          {passageMissing && (
            <p className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-[11px] text-amber-200">
              Couldn’t pinpoint the exact passage — showing the full filing.{' '}
              {isHttpUrl(secUrl) && (
                <a href={secUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline">
                  Open original
                </a>
              )}
            </p>
          )}
          <div
            ref={contentRef}
            className="prose prose-invert prose-sm min-h-0 max-w-none flex-1 overflow-y-auto break-words px-4 py-4 prose-headings:text-white prose-p:text-slate-200 prose-li:text-slate-200 prose-a:text-mint-300"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ''}</ReactMarkdown>
          </div>
        </div>
      )}
    </>
  )

  // --- Embedded: body only (the shell provides chrome + tabs + close + "open original"). ---
  if (embedded) {
    return <div className="flex min-h-0 flex-1 flex-col">{inner}</div>
  }

  // --- Standalone overlay drawer (citation-driven). ---
  if (!localOpen) return null

  return (
    <div
      role="dialog"
      aria-label={`${filingLabel} — filing text`}
      className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] flex-col rounded-t-2xl border border-white/10 bg-slate-900 text-slate-100 shadow-2xl lg:inset-x-auto lg:bottom-0 lg:left-0 lg:top-16 lg:max-h-none lg:w-[480px] lg:rounded-none lg:border-y-0 lg:border-r"
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-mint-400" />
          <h2 className="truncate text-sm font-semibold text-white">{filingLabel} — filing text</h2>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {openOriginal}
          <button
            type="button"
            onClick={close}
            aria-label="Close filing viewer"
            className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {inner}
    </div>
  )
}

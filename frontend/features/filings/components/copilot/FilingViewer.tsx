'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowClockwiseIcon, ArrowSquareOutIcon, CircleNotchIcon, FileTextIcon, XIcon } from '@/lib/icons'
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
  // eslint-disable-next-line react-hooks/refs -- deliberate render-time mirror so effects read the latest status without taking it as a dep (avoids re-running load on every status change)
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs the standalone drawer open in response to an external citation request (nonce-gated, runs once per click)
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
      className="inline-flex items-center gap-1 text-xs font-medium text-brand-strong dark:text-brand-strong-dark hover:underline"
    >
      Open original <ArrowSquareOutIcon className="h-3 w-3" />
    </a>
  ) : null

  // Shared inner content: the loading / empty / error / ready states.
  const inner = (
    <>
      {(status === 'idle' || status === 'loading') && (
        <p className="flex flex-1 items-center justify-center gap-2 px-6 py-12 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <CircleNotchIcon className="h-4 w-4 animate-spin text-brand-strong dark:text-brand-strong-dark" /> Loading the filing…
        </p>
      )}

      {(status === 'empty' || status === 'error') && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-12 text-center">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {status === 'error'
              ? 'Could not load the filing text.'
              : 'The full filing text is not available to view in-app yet.'}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {status === 'error' && (
              <button
                type="button"
                onClick={() => void load()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-800 px-3 py-2 text-xs font-semibold text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-brand-weak dark:hover:bg-slate-700"
              >
                <ArrowClockwiseIcon className="h-3.5 w-3.5" /> Try again
              </button>
            )}
            {isHttpUrl(secUrl) && (
              <a
                href={secUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-3 py-2 text-xs font-semibold transition-colors"
              >
                Open the original on SEC.gov <ArrowSquareOutIcon className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        </div>
      )}

      {status === 'ready' && (
        <div className="flex min-h-0 flex-1 flex-col">
          {passageMissing && (
            <p className="border-b border-warning-light/20 dark:border-warning-dark/20 bg-warning-light/10 dark:bg-warning-dark/10 px-4 py-2 text-[11px] text-warning-light dark:text-warning-dark">
              Couldn’t pinpoint the exact passage — showing the full filing.{' '}
              {isHttpUrl(secUrl) && (
                <a href={secUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline">
                  Open original
                </a>
              )}
            </p>
          )}
          {/* .filing-reader is the serif's ONE surface — the filing's own words
              (Newsreader 19/1.7, 68ch measure, reader tables). It replaces the
              Tailwind prose stack per MIGRATION v2.1 §e.1: the two must never
              coexist (double margins), and the class carries its own measure. */}
          <div
            ref={contentRef}
            className="filing-reader min-h-0 flex-1 overflow-y-auto break-words px-4 py-4"
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
      className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] flex-col rounded-t-2xl border border-border-light bg-panel-light text-text-primary-light dark:border-white/10 dark:bg-slate-900 dark:text-text-primary-dark shadow-2xl lg:inset-x-auto lg:bottom-0 lg:left-0 lg:top-16 lg:max-h-none lg:w-[480px] lg:rounded-none lg:border-y-0 lg:border-r"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border-light dark:border-white/10 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileTextIcon className="h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark" />
          <h2 className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{filingLabel} — filing text</h2>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {openOriginal}
          <button
            type="button"
            onClick={close}
            aria-label="Close filing viewer"
            className="flex h-8 w-8 items-center justify-center rounded-full text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {inner}
    </div>
  )
}

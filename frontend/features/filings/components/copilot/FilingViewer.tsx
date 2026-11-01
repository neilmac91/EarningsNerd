'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowClockwiseIcon, ArrowSquareOutIcon } from '@/lib/icons'
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'
import { isHttpUrl } from './CitationChip'
import { useFilingViewer } from './FilingViewerContext'
import { clearCitationHighlight, highlightExcerptInDom } from './highlightInDom'
import ReaderTable from './ReaderTable'
import { buttonVariants, SkeletonText } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'

// The reader's own markdown renderers: each table scrolls sideways in a box of its own (EN-04).
// Module-level, so ReactMarkdown sees the same object on every render.
const READER_COMPONENTS: Components = { table: ReaderTable }

/**
 * Whether the server located the passage a request jumps to (D-044), so the reader may paint it with the
 * device: a verified citation of the filing's own text. A summary chip's heading fallback arrives
 * unverified (SourceTrace sends `verified` only with the excerpt the server checked), and a figure (the
 * server's fact or calculated payload, isXbrlCitation) has no passage, so the text its jump finds is a best
 * effort; a passage the model labelled "XBRL · …" is still a passage. Anything else takes the neutral
 * find highlight (highlightInDom).
 */
const isLocated = (citation: CopilotCitation) => citation.verified === true && !isXbrlCitation(citation)

interface FilingViewerProps {
  filingId: number
  filingLabel: string
  // The original document for "Open original" and the empty/error-state CTA: `document_url`, then
  // `sec_url` (the page derives it with `originalDocumentUrl`; the folder index is the fallback only).
  secUrl: string | null
}

type Status = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

/**
 * In-app filing reader (P7 / 1.1), the body of the Source pane's Filing tab: FilingWorkspace's shell owns
 * its chrome (the tabs, the close and the "Original on SEC.gov" footer). It shows while the shared view
 * (FilingViewerContext's `activeView`) is 'filing', which the Filing tab or a Copilot citation's highlight
 * request selects, lazy-loads the cached filing markdown, renders it, and scrolls to and highlights the
 * cited passage in place. It stays mounted, so loaded text and the highlight survive a switch back to the
 * answer. The standalone drawer no route mounted went with E280.
 */
export default function FilingViewer({ filingId, filingLabel, secUrl }: FilingViewerProps) {
  const viewer = useFilingViewer()
  const [passageMissing, setPassageMissing] = useState(false)
  // The mounted text or status box is the retry's destination: success focuses the loaded reader
  // (or empty result); another failure keeps the focused Retry inside its retained alert.
  const contentRef = useRef<HTMLDivElement>(null)
  const handledNonce = useRef(0)

  // Visibility follows the shared view state.
  const active = viewer?.activeView === 'filing'

  // The content query owns the single in-flight request for this filing, including a tab activation
  // and a citation in the same commit. Loaded text stays fresh across view switches; a failed read
  // stays visible and focusable throughout Retry or any other refetch until data replaces it.
  // An initial errored query has no data, so re-enabling it refetches even with staleTime: Infinity.
  const contentQuery = useQuery({
    queryKey: queryKeys.filingContent(filingId),
    queryFn: () => fetchFilingContent(filingId),
    enabled: active,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
  const failure = useRetainedFailure(contentQuery, queryKeys.filingContent(filingId))
  const { refetch } = contentQuery
  const content = contentQuery.data?.markdownContent ?? null
  const status: Status = failure.failed ? 'error' : contentQuery.data
    ? contentQuery.data.hasContent && content ? 'ready' : 'empty'
    : contentQuery.isFetching ? 'loading' : 'idle'
  const failedRef = useRef(false)
  // eslint-disable-next-line react-hooks/refs -- event-like citation effect reads the latest failure without restarting on every query transition
  failedRef.current = failure.failed

  const request = viewer?.request ?? null

  // A citation chip requested a highlight: load if we haven't yet.
  useEffect(() => {
    if (!request || request.nonce === handledNonce.current) return
    handledNonce.current = request.nonce
    setPassageMissing(false)
    // A fresh citation also retries a failed read. Join any request already started by activation.
    if (failedRef.current) void refetch({ cancelRefetch: false })
  }, [request, refetch])

  // Once content is rendered and a citation is pending, find + highlight the passage: in the device's
  // paint only where the server located it, in the neutral find paint otherwise (D-044).
  const activeExcerpt = request?.citation.excerpt
  const activeLocated = request ? isLocated(request.citation) : false
  const activeNonce = request?.nonce
  // The "Showing" line names the cited passage the reader scrolled to (2026-10 critique P-06).
  const showingLabel = request ? request.citation.section_ref?.trim() || 'Cited passage' : null
  useEffect(() => {
    if (!active || status !== 'ready' || !activeExcerpt || !contentRef.current) return
    // Defer a frame so ReactMarkdown has painted before we walk its text nodes.
    const raf = window.requestAnimationFrame(() => {
      const found = contentRef.current
        ? highlightExcerptInDom(contentRef.current, activeExcerpt, { located: activeLocated })
        : false
      setPassageMissing(!found)
    })
    return () => window.cancelAnimationFrame(raf)
  }, [active, status, activeExcerpt, activeLocated, activeNonce, content])

  // Tear down any lingering highlight when the viewer unmounts (pane closed / page left).
  useEffect(() => () => clearCitationHighlight(), [])

  // The loading / empty / error / ready states.
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {(status === 'idle' || status === 'loading') && (
        // SkeletonText carries its own role="status": the wrapper stays role-less.
        <div className="flex-1 space-y-3 px-6 py-8">
          <SkeletonText lines={6} mono />
        </div>
      )}

      {(status === 'empty' || status === 'error') && (
        <div ref={contentRef} tabIndex={-1} role={status === 'error' ? 'alert' : 'status'} className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-12 text-center outline-none">
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {status === 'error'
              ? 'Could not load the filing text.'
              : 'The full filing text is not available to view in-app yet.'}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {status === 'error' && (
              <RetryButton failures={[failure]} focusTarget={contentRef} variant="secondary" size="sm" leftIcon={<ArrowClockwiseIcon className="h-3.5 w-3.5" />} />
            )}
            {isHttpUrl(secUrl) && (
              <a href={secUrl} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: 'primary', size: 'sm' })}>
                Open the original on SEC.gov <ArrowSquareOutIcon className="h-3.5 w-3.5" aria-hidden="true" />
                {' '}<span className="sr-only">(opens in a new tab)</span>
              </a>
            )}
          </div>
        </div>
      )}

      {status === 'ready' && (
        <div className="flex min-h-0 flex-1 flex-col">
          {showingLabel && !passageMissing && (
            <p className="px-4 pt-3 font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
              Showing · {showingLabel}
            </p>
          )}
          {passageMissing && (
            <p className="border-b border-warning-light/20 dark:border-warning-dark/20 bg-warning-light/10 dark:bg-warning-dark/10 px-4 py-2 text-xs text-warning-light dark:text-warning-dark">
              Couldn’t pinpoint the exact passage, so this is the full filing.{' '}
              {isHttpUrl(secUrl) && (
                <a href={secUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
                  Open original
                  {' '}<span className="sr-only">(opens in a new tab)</span>
                </a>
              )}
            </p>
          )}
          {/* .filing-reader is the serif's long-form surface: the filing's own words
              (Newsreader 19/1.7, 68ch measure, reader tables). Inside the product
              the serif also sets a passage the server located, as a marked block in
              the summary (.en-marked, D-044). It replaces the
              Tailwind prose stack per MIGRATION v2.1 §e.1: the two must never
              coexist (double margins), and the class carries its own measure and
              width (as wide as this pane, never wider: EN-04).
              A named tab stop, so the arrow keys scroll it from the top: Chromium
              made the scroller one on its own only while nothing inside it could
              take focus, and a wide table's scroll region can. Inset ring: an
              outer one would sit over what borders the reader, the "Showing ·"
              line and the pane's tabs above it and the "Original on SEC.gov"
              footer's hairline below. */}
          <div
            ref={contentRef}
            role="region"
            aria-label={`${filingLabel} · filing text`}
            tabIndex={0}
            className="filing-reader min-h-0 flex-1 overflow-y-auto break-words px-4 py-4 focus-visible:outline-none focus-visible:shadow-ring-brand-inset dark:focus-visible:shadow-ring-brand-inset-dark"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={READER_COMPONENTS}>
              {content || ''}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

'use client'

import { useRef, useState } from 'react'
import analytics from '@/lib/analytics'
import { Button } from '@/components/ui/Button'
import { BookmarkSimpleIcon, CheckCircleIcon, CopyIcon, DownloadSimpleIcon, FileArrowDownIcon } from '@/lib/icons'

export interface SaveMutation {
  mutate: (summaryId: number) => void
  isPending: boolean
}

export interface SummaryActionsBarProps {
  filingId: number
  summaryId: number | null
  isAuthenticated: boolean
  isSaved: boolean
  saveMutation: SaveMutation
  isPro: boolean
  onExportPdf: () => void
  onExportCsv: () => void
}

/**
 * Filing actions above the summary. Clipboard feedback is local; the export handlers
 * come from useSummaryExports; the save mutation is owned by the filing view.
 */
export function SummaryActionsBar({
  filingId,
  summaryId,
  isAuthenticated,
  isSaved,
  saveMutation,
  isPro,
  onExportPdf,
  onExportCsv,
}: SummaryActionsBarProps) {
  // Match the existing filing metadata canonical; never copy private URL/query state.
  const filingUrl = `https://www.earningsnerd.io/filing/${filingId}`
  const copying = useRef(false)
  const [copyState, setCopyState] = useState<'idle' | 'pending' | 'copied' | 'failed'>('idle')

  const copyFilingLink = async () => {
    if (copying.current) return
    copying.current = true
    setCopyState('pending')
    try {
      await navigator.clipboard.writeText(filingUrl)
      setCopyState('copied')
      analytics.filingLinkCopied(filingId)
    } catch {
      setCopyState('failed')
    } finally {
      copying.current = false
    }
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
      {isAuthenticated && (
        <div>
          {summaryId != null && (
            isSaved ? (
              // Terminal confirmation — a static success chip (no success Badge variant exists;
              // DS §9 reserves success for a genuine done-state, which "Saved" is).
              <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold bg-success-light/10 text-success-light dark:bg-success-dark/10 dark:text-success-dark">
                <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                Saved
              </span>
            ) : (
              // Primary treatment (was secondary) so the save affordance is discoverable pre-scroll
              // rather than reading as a low-key optional action — it is the main thing a signed-in
              // reader does with a summary they want to keep.
              <Button
                variant="primary"
                onClick={() => saveMutation.mutate(summaryId)}
                disabled={saveMutation.isPending}
              >
                <BookmarkSimpleIcon className="h-4 w-4" />
                Save Summary
              </Button>
            )
          )}
        </div>
      )}
      <div className="min-w-0 space-y-2">
        <Button type="button" variant="secondary" loading={copyState === 'pending'} onClick={copyFilingLink}>
          <CopyIcon className="h-4 w-4" aria-hidden="true" />
          Copy filing link
        </Button>
        <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {copyState === 'copied' ? 'Filing link copied.' : ''}
        </p>
        {copyState === 'failed' && (
          <p role="alert" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Could not copy the link. Try again, or copy this link manually:{' '}
            <a href={filingUrl} className="break-all text-brand-strong underline underline-offset-4 dark:text-brand-strong-dark">
              {filingUrl}
            </a>
          </p>
        )}
      </div>
      {/* Export buttons - only show for Pro users */}
      {isPro && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={onExportPdf}>
            <DownloadSimpleIcon className="h-4 w-4" />
            Export PDF
          </Button>
          <Button variant="secondary" onClick={onExportCsv}>
            <FileArrowDownIcon className="h-4 w-4" />
            Export CSV
          </Button>
        </div>
      )}
    </div>
  )
}

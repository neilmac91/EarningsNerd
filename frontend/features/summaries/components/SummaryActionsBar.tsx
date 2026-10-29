'use client'

import { useEffect, useRef, useState } from 'react'
import analytics from '@/lib/analytics'
import { Badge } from '@/components/ui/Badge'
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
  /** Whether the summary finished. Saving and exporting act on a summary, so a stored one that did not
   *  finish offers neither; the filing link is the filing's, and stays. */
  summaryFinished: boolean
  onExportPdf: () => void
  onExportCsv: () => void
}

/**
 * Filing actions above the summary. Clipboard feedback is local; the export handlers
 * come from useSummaryExports; the save mutation is owned by the filing view. Each action's label
 * wraps inside its button (`wrap`, max-w-full), so at 200% text on a 320px phone no button runs
 * past the reading column.
 */
export function SummaryActionsBar({
  filingId,
  summaryId,
  isAuthenticated,
  isSaved,
  saveMutation,
  isPro,
  summaryFinished,
  onExportPdf,
  onExportCsv,
}: SummaryActionsBarProps) {
  // Match the existing filing metadata canonical; never copy private URL/query state.
  const filingUrl = `https://www.earningsnerd.io/filing/${filingId}`
  const copying = useRef(false)
  const [copyState, setCopyState] = useState<'idle' | 'pending' | 'copied' | 'failed'>('idle')
  const savedRef = useRef<HTMLSpanElement>(null)
  const savePressed = useRef(false)

  // A successful save swaps the focused Save summary button for the Saved chip, dropping focus to
  // <body>; hand it to the chip instead (unless focus has already moved elsewhere). Only after
  // Save's own press, so an already-saved summary never takes focus on load.
  useEffect(() => {
    if (!isSaved || !savePressed.current) return
    savePressed.current = false
    if (document.activeElement === document.body) savedRef.current?.focus({ preventScroll: true })
  }, [isSaved])

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
      {isAuthenticated && summaryFinished && (
        <div>
          {summaryId != null && (
            isSaved ? (
              // Terminal confirmation: Badge's success status chip (DS §9 reserves success for a genuine
              // done-state, which "Saved" is). The chip takes focus when the save that put it here succeeds.
              <Badge
                ref={savedRef}
                tabIndex={-1}
                variant="success"
                icon={<CheckCircleIcon className="h-4 w-4" aria-hidden="true" />}
                className="outline-none"
              >
                Saved
              </Badge>
            ) : (
              // Primary treatment (was secondary) so the save affordance is discoverable pre-scroll
              // rather than reading as a low-key optional action — it is the main thing a signed-in
              // reader does with a summary they want to keep.
              // `loading`, never native `disabled`, while the save is in flight: Chromium blurs a
              // focused button that turns disabled, dropping a keyboard user to <body>. loading =
              // aria-disabled + aria-busy + a click guard, so a second press cannot re-save. The
              // icon rides leftIcon so the spinner replaces it instead of widening the button.
              <Button
                variant="primary"
                wrap
                className="max-w-full"
                onClick={() => {
                  savePressed.current = true
                  saveMutation.mutate(summaryId)
                }}
                loading={saveMutation.isPending}
                leftIcon={<BookmarkSimpleIcon className="h-4 w-4" />}
              >
                Save summary
              </Button>
            )
          )}
        </div>
      )}
      <div className="min-w-0 space-y-2">
        <Button type="button" variant="secondary" wrap className="max-w-full" loading={copyState === 'pending'} onClick={copyFilingLink}>
          <CopyIcon className="h-4 w-4" aria-hidden="true" />
          Copy filing link
        </Button>
        <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {copyState === 'copied' ? 'Filing link copied.' : ''}
        </p>
        {copyState === 'failed' && (
          <p role="alert" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Could not copy the link. Try again, or copy this link manually:{' '}
            <a
              href={filingUrl}
              className="break-all rounded-sm text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
            >
              {filingUrl}
            </a>
          </p>
        )}
      </div>
      {/* Export buttons: Pro only, and only for a summary that finished */}
      {isPro && summaryFinished && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" wrap className="max-w-full" onClick={onExportPdf}>
            <DownloadSimpleIcon className="h-4 w-4" />
            Export PDF
          </Button>
          <Button variant="secondary" wrap className="max-w-full" onClick={onExportCsv}>
            <FileArrowDownIcon className="h-4 w-4" />
            Export CSV
          </Button>
        </div>
      )}
    </div>
  )
}

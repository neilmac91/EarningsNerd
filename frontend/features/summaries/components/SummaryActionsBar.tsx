'use client'

import { Button } from '@/components/ui/Button'
import { BookmarkSimpleIcon, CheckCircleIcon, DownloadSimpleIcon, FileArrowDownIcon } from '@/lib/icons'

export interface SaveMutation {
  mutate: (summaryId: number) => void
  isPending: boolean
}

export interface SummaryActionsBarProps {
  summaryId: number | null
  isAuthenticated: boolean
  isSaved: boolean
  saveMutation: SaveMutation
  isPro: boolean
  onExportPdf: () => void
  onExportCsv: () => void
}

/**
 * Save + export action row above the summary. Presentational: the export handlers
 * come from useSummaryExports; the save mutation is owned by the filing view.
 */
export function SummaryActionsBar({
  summaryId,
  isAuthenticated,
  isSaved,
  saveMutation,
  isPro,
  onExportPdf,
  onExportCsv,
}: SummaryActionsBarProps) {
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
              <Button
                variant="secondary"
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

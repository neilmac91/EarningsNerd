'use client'

import { useCallback } from 'react'
import { format } from 'date-fns'
import { exportSummaryPdf, exportSummaryCsv } from '../api/summaries-api'
import type { Filing } from '@/features/filings/api/filings-api'
import { getErrorStatus } from '@/lib/api/types'
import { sanitizeFilename } from '@/lib/format'
import { downloadBlob } from '@/lib/downloadBlob'

type ExportKind = 'pdf' | 'csv'

function buildFilename(filing: Filing, kind: ExportKind): string {
  const base = sanitizeFilename(filing.filing_type, 'filing')
  const date = filing.filing_date ? format(new Date(filing.filing_date), 'yyyyMMdd') : 'summary'
  return `${base}_${date}.${kind}`
}

/**
 * PDF/CSV summary export handlers for the filing page. Fetches the blob via the
 * shared axios client and hands it to downloadBlob; a 403 (non-Pro) surfaces the
 * upgrade prompt, matching the prior inline behavior — just off the shared client.
 */
export function useSummaryExports(filing: Filing) {
  const run = useCallback(
    async (kind: ExportKind) => {
      try {
        const blob = kind === 'pdf' ? await exportSummaryPdf(filing.id) : await exportSummaryCsv(filing.id)
        downloadBlob(blob, buildFilename(filing, kind))
      } catch (error) {
        if (getErrorStatus(error) === 403) {
          alert(`${kind.toUpperCase()} export is a Pro feature. Please upgrade to Pro.`)
          return
        }
        console.error('Export error:', error)
        alert(`Failed to export ${kind.toUpperCase()}. Please try again.`)
      }
    },
    [filing],
  )

  return {
    exportPdf: useCallback(() => run('pdf'), [run]),
    exportCsv: useCallback(() => run('csv'), [run]),
  }
}

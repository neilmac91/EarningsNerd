'use client'

import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { resolveDataNotes, type DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { reportIdentity, type TableWindow } from '@/features/analysis/lib/reportPresentation'

const DataNotesContext = createContext<DataNotesModel | null>(null)
const TableWindowContext = createContext<ReturnType<typeof useWindowSelection> | null>(null)

function useWindowSelection(dataset: AnalysisDataset) {
  const identity = reportIdentity(dataset)
  const [selection, setSelection] = useState({ identity, window: 'all' as TableWindow })
  if (selection.identity !== identity) setSelection({ identity, window: 'all' })
  return { identity, window: selection.identity === identity ? selection.window : 'all' as TableWindow,
    setWindow: (window: TableWindow) => setSelection({ identity, window }) }
}

/** All report surfaces share one snapshot's note letters and counts. */
export function DataNotesProvider({ dataset, children }: { dataset: AnalysisDataset; children: ReactNode }) {
  const model = useMemo(() => resolveDataNotes(dataset), [dataset])
  const selection = useWindowSelection(dataset)
  return <DataNotesContext.Provider value={model}><TableWindowContext.Provider value={selection}>{children}</TableWindowContext.Provider></DataNotesContext.Provider>
}

export function useReportDataNotes() {
  return useContext(DataNotesContext)
}

/** A report shares only table presentation state; a standalone table keeps the same local API. */
export function useAnalysisTableWindow(dataset: AnalysisDataset) {
  const report = useContext(TableWindowContext)
  const local = useWindowSelection(dataset)
  return report?.identity === reportIdentity(dataset) ? report : local
}

/** Standalone surfaces resolve the same admitted metadata as the complete report. */
export function useDataNotes(dataset: AnalysisDataset) {
  const report = useReportDataNotes()
  return useMemo(() => report ?? resolveDataNotes(dataset), [report, dataset])
}

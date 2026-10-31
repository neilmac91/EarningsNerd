'use client'

import { createContext, useContext, useMemo, type ReactNode } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { resolveDataNotes, type DataNotesModel } from '@/features/analysis/lib/dataNotes'

const DataNotesContext = createContext<DataNotesModel | null>(null)

/** All report surfaces share one snapshot's note letters and counts. */
export function DataNotesProvider({ dataset, children }: { dataset: AnalysisDataset; children: ReactNode }) {
  const model = useMemo(() => resolveDataNotes(dataset), [dataset])
  return <DataNotesContext.Provider value={model}>{children}</DataNotesContext.Provider>
}

export function useReportDataNotes() {
  return useContext(DataNotesContext)
}

/** Standalone surfaces resolve the same admitted metadata as the complete report. */
export function useDataNotes(dataset: AnalysisDataset) {
  const report = useReportDataNotes()
  return useMemo(() => report ?? resolveDataNotes(dataset), [report, dataset])
}

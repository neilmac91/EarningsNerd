'use client'

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

export interface CitationHighlightRequest {
  citation: CopilotCitation
  // Bumped on every request so clicking the same citation twice still re-triggers the effect.
  nonce: number
}

interface FilingViewerContextValue {
  request: CitationHighlightRequest | null
  requestHighlight: (citation: CopilotCitation) => void
  clearRequest: () => void
}

const FilingViewerContext = createContext<FilingViewerContextValue | null>(null)

/**
 * Coordinates the in-app filing viewer (P7). A `CitationChip` deep in the Copilot answer calls
 * `requestHighlight(citation)`; the sibling `FilingViewer` listens for the request, opens, and
 * scrolls to + highlights the cited passage. Kept tiny (just a request channel) so it doesn't
 * couple the chip and the viewer beyond the citation payload.
 */
export function FilingViewerProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<CitationHighlightRequest | null>(null)

  const requestHighlight = useCallback((citation: CopilotCitation) => {
    setRequest((prev) => ({ citation, nonce: (prev?.nonce ?? 0) + 1 }))
  }, [])
  const clearRequest = useCallback(() => setRequest(null), [])

  const value = useMemo(
    () => ({ request, requestHighlight, clearRequest }),
    [request, requestHighlight, clearRequest],
  )

  return <FilingViewerContext.Provider value={value}>{children}</FilingViewerContext.Provider>
}

// Returns null outside a provider (e.g. the FREE teaser, or component tests with no viewer), so
// consumers degrade gracefully to the SEC deep link.
export function useFilingViewer(): FilingViewerContextValue | null {
  return useContext(FilingViewerContext)
}

'use client'

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'
import analytics from '@/lib/analytics'

export interface CitationHighlightRequest {
  citation: CopilotCitation
  // Bumped on every request so clicking the same citation twice still re-triggers the effect.
  nonce: number
}

// Which body the unified secondary pane is showing: the Copilot conversation or the filing text.
export type CopilotView = 'copilot' | 'filing'

interface FilingViewerContextValue {
  request: CitationHighlightRequest | null
  requestHighlight: (citation: CopilotCitation) => void
  clearRequest: () => void
  // Which pane body is active, and how to switch. A citation switches to 'filing' automatically;
  // the [Answer · Filing] tabs and openFiling() (the Filing tab with no citation) switch explicitly.
  activeView: CopilotView
  setActiveView: (view: CopilotView) => void
  openFiling: () => void
}

const FilingViewerContext = createContext<FilingViewerContextValue | null>(null)

/**
 * Coordinates the in-app filing viewer (P7) and which body the secondary pane shows (1.1). A
 * `CitationChip` deep in the Copilot answer calls `requestHighlight(citation)`; that both records the
 * passage to highlight AND switches the pane to the filing view, so the sibling `FilingViewer` opens,
 * loads, and scrolls to the cited text. The `[Answer · Filing]` tabs flip `activeView` directly, and
 * `openFiling()` opens the filing view with no citation (the viewer just loads the full filing).
 * Kept tiny (a request channel + view state) so it doesn't couple the chip, the tabs, and the viewer
 * beyond the citation payload.
 */
export function FilingViewerProvider({
  children,
  filingId,
  ticker,
  filingType,
}: {
  children: ReactNode
  // Filing context for the source_span_click analytics attribution (item 1.8). Optional so the
  // provider can still be mounted without it (the FREE teaser, component tests) — without filing
  // context the verification event is simply not emitted.
  filingId?: number
  ticker?: string | null
  filingType?: string
}) {
  const [request, setRequest] = useState<CitationHighlightRequest | null>(null)
  const [activeView, setActiveView] = useState<CopilotView>('copilot')

  const requestHighlight = useCallback((citation: CopilotCitation) => {
    // Activation DEPTH (item 1.8): a citation click is the user verifying a claim against its
    // source. This is the single shared point for every in-app citation (text [n] + XBRL [F#]).
    // Guard on filingId so propless mounts (teaser / tests) don't emit a context-less event.
    if (filingId != null) {
      analytics.sourceSpanClicked({
        filingId,
        ticker: ticker ?? null,
        filingType: filingType ?? '',
        citationIndex: String(citation.n),
        citationKind: isXbrlCitation(citation) ? 'xbrl' : 'text',
        verified: citation.verified,
        action: 'scroll_highlight',
      })
    }
    setRequest((prev) => ({ citation, nonce: (prev?.nonce ?? 0) + 1 }))
    // A citation always means "show me that passage" — switch the pane to the filing view.
    setActiveView('filing')
  }, [filingId, ticker, filingType])
  const clearRequest = useCallback(() => setRequest(null), [])
  const openFiling = useCallback(() => setActiveView('filing'), [])

  const value = useMemo(
    () => ({ request, requestHighlight, clearRequest, activeView, setActiveView, openFiling }),
    [request, requestHighlight, clearRequest, activeView, openFiling],
  )

  return <FilingViewerContext.Provider value={value}>{children}</FilingViewerContext.Provider>
}

// Returns null outside a provider (e.g. the FREE teaser, or component tests with no viewer), so
// consumers degrade gracefully to the SEC deep link.
export function useFilingViewer(): FilingViewerContextValue | null {
  return useContext(FilingViewerContext)
}

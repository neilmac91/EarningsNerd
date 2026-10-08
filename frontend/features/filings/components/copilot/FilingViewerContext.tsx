'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'
import analytics from '@/lib/analytics'
import { renderedCopy } from '@/features/filings/lib/layoutTwin'

export interface CitationHighlightRequest {
  citation: CopilotCitation
  // Bumped on every request so clicking the same citation twice still re-triggers the effect.
  nonce: number
}

// Which body the unified secondary pane is showing: the Copilot conversation or the filing text.
export type CopilotView = 'copilot' | 'filing'

interface FilingViewerContextValue {
  request: CitationHighlightRequest | null
  /**
   * Record a passage to highlight, switch the pane to the filing view and ask the page to open the
   * pane (`onRequestOpen`). `opener` is the activating element when it sits outside the pane (a
   * summary chip): the workspace returns focus to it when the pane closes, so a keyboard user lands
   * back where they left (EN-01). An activation from inside the pane (an answer's [n] chip) passes
   * none and leaves the pane's opener as it was.
   */
  requestHighlight: (citation: CopilotCitation, opener?: HTMLElement | null) => void
  clearRequest: () => void
  // Which pane body is active, and how to switch. A citation switches to 'filing' automatically;
  // the [Answer · Filing] tabs and openFiling() (the Filing tab with no citation) switch explicitly.
  activeView: CopilotView
  setActiveView: (view: CopilotView) => void
  openFiling: () => void
  /**
   * The element whose activation last requested a highlight with an opener (an activation from inside
   * the pane passes none, so this keeps the one before it), or null. FilingWorkspace never returns
   * focus to one inside the pane (`isReturnTarget`). Owned by the provider and mutated only here:
   * `peekOpener` reads it (the mobile sheet's focus-restore target), `takeOpener` reads and forgets it
   * (FilingWorkspace, when the pane closes), both as the copy now shown (`renderedCopy`: a metric chip
   * a breakpoint hid since resolves to its rendered twin). Never a trigger for anything.
   */
  peekOpener: () => HTMLElement | null
  takeOpener: () => HTMLElement | null
}

const FilingViewerContext = createContext<FilingViewerContextValue | null>(null)

/**
 * Coordinates the in-app filing viewer (P7) and which body the secondary pane shows (1.1). A
 * `SourceTrace` chip in the summary calls `requestHighlight(citation, opener)`, and a `CitationChip`
 * deep in the Copilot answer calls it without an opener; that records the passage to highlight,
 * switches the pane to the filing view AND asks the page to open the pane (`onRequestOpen`), so the
 * sibling `FilingViewer` is visible, loads, and scrolls to the cited text, or shows its truthful empty
 * state when the filing has no in-app text yet. The open is a direct call from the activation, never
 * an effect on the request nonce: a pane the user closed can therefore never reopen on its own from a
 * stale request (EN-01). The `[Answer · Filing]` tabs flip `activeView` directly, and `openFiling()`
 * opens the filing view with no citation (the viewer just loads the full filing). Kept tiny (a request
 * channel + view state + the opener) so it doesn't couple the chip, the tabs, and the viewer beyond
 * the citation payload. Nothing here reads plan or auth state: source access is the same for every
 * visitor.
 */
export function FilingViewerProvider({
  children,
  filingId,
  ticker,
  filingType,
  onRequestOpen,
}: {
  children: ReactNode
  // Filing context for the source_span_click analytics attribution (item 1.8). Optional so the
  // provider can still be mounted without it (the FREE teaser, component tests) — without filing
  // context the verification event is simply not emitted.
  filingId?: number
  ticker?: string | null
  filingType?: string
  /** Called synchronously on every highlight request: the page opens the research pane. */
  onRequestOpen?: () => void
}) {
  const [request, setRequest] = useState<CitationHighlightRequest | null>(null)
  const [activeView, setActiveView] = useState<CopilotView>('copilot')
  const opener = useRef<HTMLElement | null>(null)
  // Read through a ref so a new callback identity never changes requestHighlight (and so never
  // re-arms any consumer effect that depends on it).
  const onRequestOpenRef = useRef(onRequestOpen)
  useEffect(() => {
    onRequestOpenRef.current = onRequestOpen
  }, [onRequestOpen])

  const requestHighlight = useCallback((citation: CopilotCitation, from?: HTMLElement | null) => {
    // Activation DEPTH (item 1.8): a citation click is the user verifying a claim against its
    // source. This is the single shared point for every in-app citation (text [n] + XBRL [F#] +
    // the summary's provenance chips), so it emits exactly once per activation; opening the pane
    // emits nothing of its own.
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
    if (from !== undefined) opener.current = from
    setRequest((prev) => ({ citation, nonce: (prev?.nonce ?? 0) + 1 }))
    // A citation always means "show me that passage" — switch the pane to the filing view...
    setActiveView('filing')
    // ...and make sure the pane is actually visible (a closed pane was the EN-01 silent no-op).
    onRequestOpenRef.current?.()
  }, [filingId, ticker, filingType])
  const clearRequest = useCallback(() => setRequest(null), [])
  const openFiling = useCallback(() => setActiveView('filing'), [])
  // Read as the copy now shown: a metric chip that a breakpoint hid after it opened the pane (EN-03
  // renders each one in two layouts) resolves to its rendered twin, so focus returns to the same chip.
  const peekOpener = useCallback(() => renderedCopy(opener.current), [])
  const takeOpener = useCallback(() => {
    const el = opener.current
    opener.current = null
    return renderedCopy(el)
  }, [])

  const value = useMemo(
    () => ({ request, requestHighlight, clearRequest, activeView, setActiveView, openFiling, peekOpener, takeOpener }),
    [request, requestHighlight, clearRequest, activeView, openFiling, peekOpener, takeOpener],
  )

  return <FilingViewerContext.Provider value={value}>{children}</FilingViewerContext.Provider>
}

// Returns null outside a provider (e.g. the FREE teaser, or component tests with no viewer), so
// consumers degrade gracefully to the SEC deep link.
export function useFilingViewer(): FilingViewerContextValue | null {
  return useContext(FilingViewerContext)
}

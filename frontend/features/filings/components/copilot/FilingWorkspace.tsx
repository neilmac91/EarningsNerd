'use client'

import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ExternalLink, Sparkles } from 'lucide-react'
import PaneResizer from './PaneResizer'
import SecondaryPaneTabs, { PANE_PANEL_IDS, PANE_TAB_IDS } from './SecondaryPaneTabs'
import { isHttpUrl } from './CitationChip'
import { useFilingViewer } from './FilingViewerContext'
import { useSheetFocusTrap } from './useSheetFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'

// Below lg the secondary pane is a modal bottom-sheet; at lg+ it's a static side pane (no modal).
const MOBILE_MEDIA_QUERY = '(max-width: 1023.98px)'

const DEFAULT_WIDTH = 420
const MIN_WIDTH = 360
const MAX_WIDTH = 640
const STORAGE_KEY = 'copilot:paneWidth'

function clampWidth(w: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, w))
}

function readStoredWidth(): number {
  if (typeof window === 'undefined') return DEFAULT_WIDTH
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const n = raw ? Number(raw) : NaN
    return Number.isFinite(n) ? clampWidth(n) : DEFAULT_WIDTH
  } catch {
    // localStorage can throw (private mode, blocked third-party storage, SecurityError in an iframe).
    return DEFAULT_WIDTH
  }
}

// The secondary pane's container: a bottom-sheet below lg, a static full-height pane on lg+ (it fills
// the grid cell; PaneResizer + the sticky cell wrapper provide width/height). One element, two CSS
// personalities — so each body mounts exactly once across breakpoints.
const SHELL_CLASSES =
  'fixed inset-x-0 bottom-0 z-40 flex max-h-[85vh] flex-col rounded-t-2xl border border-border-light bg-panel-light text-text-primary-light dark:border-white/10 dark:bg-slate-900 dark:text-text-primary-dark shadow-2xl lg:static lg:inset-auto lg:z-auto lg:h-full lg:max-h-none lg:w-full lg:rounded-none lg:border-y-0 lg:shadow-none'

interface FilingWorkspaceProps {
  /** Whether the Copilot pane is open (drives the two-column desktop layout + launcher). */
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Gates the whole Copilot surface — without a summary there's nothing to cite against. */
  summaryAvailable: boolean
  /** The embedded Copilot conversation (<AskCopilotRail embedded .../>). */
  copilotBody: ReactNode
  /** The embedded filing reader (<FilingViewer embedded .../>). */
  filingBody: ReactNode
  /** SEC URL for the "open original" link on the filing tab. */
  secUrl: string | null
  /** The filing summary content (the left pane). */
  children: ReactNode
}

/**
 * Desktop "research desk" layout for the filing page (audit 1.1): the summary and a unified Copilot
 * pane sit side by side as reflowing CSS-grid panes a draggable divider resizes. The secondary pane
 * is one shell hosting an [Answer · Filing] tab switch — the Copilot conversation and the in-app
 * filing reader share the space (a citation flips to the filing view next to the answer). Below lg the
 * grid collapses to one column and the shell becomes a bottom sheet.
 *
 * Both bodies stay mounted at all times (the shell is hidden, not unmounted, when closed; the inactive
 * tab is hidden, not unmounted) so a live SSE stream and the conversation survive view switches,
 * resizes, and close/reopen.
 */
export default function FilingWorkspace({
  open,
  onOpenChange,
  summaryAvailable,
  copilotBody,
  filingBody,
  secUrl,
  children,
}: FilingWorkspaceProps) {
  const [width, setWidth] = useState<number>(DEFAULT_WIDTH)
  const viewer = useFilingViewer()
  const activeView = viewer?.activeView ?? 'copilot'
  const shellRef = useRef<HTMLDivElement>(null)
  const launcherRef = useRef<HTMLButtonElement>(null)

  // Hydrate the persisted width after mount (keeps SSR markup deterministic, avoids hydration drift).
  useEffect(() => {
    setWidth(readStoredWidth())
  }, [])

  // Below lg the bottom-sheet acts as a modal (focus trap + scrim); at lg+ it's a static side pane.
  const isMobile = useMediaQuery(MOBILE_MEDIA_QUERY)

  const handleResize = useCallback((next: number) => {
    const w = clampWidth(next)
    setWidth(w)
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(STORAGE_KEY, String(w))
    } catch {
      // Ignore storage write failures (quota/SecurityError) — the width still applies for the session.
    }
  }, [])

  const paneOpen = open && summaryAvailable
  // When closed, collapse the second track to 0 so the summary spans the full width.
  const style = { '--copilot-w': paneOpen ? `${width}px` : '0px' } as CSSProperties

  // Trap focus inside the bottom-sheet only when it's acting as a mobile modal (open + below lg).
  // FilingWorkspace owns the trap/scrim for the embedded rail; the embedded rail never adds its own.
  const modalActive = paneOpen && isMobile
  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange])
  useSheetFocusTrap({ active: modalActive, containerRef: shellRef, onClose: handleClose, restoreFocusRef: launcherRef })

  const openOriginal = isHttpUrl(secUrl) ? (
    <a
      href={secUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium text-brand-strong dark:text-brand-strong-dark hover:underline"
    >
      Open original <ExternalLink className="h-3 w-3" />
    </a>
  ) : null

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_var(--copilot-w)]" style={style}>
      <div className="min-w-0">{children}</div>
      <div className="relative min-w-0 lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)]">
        {summaryAvailable && (
          <>
            {/* Launcher (closed) */}
            {!open && (
              <button
                ref={launcherRef}
                type="button"
                onClick={() => onOpenChange(true)}
                className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-3 text-sm font-semibold shadow-e3 dark:shadow-none transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
                aria-label="Ask this Filing"
              >
                <Sparkles className="h-4 w-4" />
                Ask this Filing
                <kbd className="ml-1 hidden rounded border border-slate-950/25 bg-slate-950/10 px-1.5 py-0.5 text-[10px] font-semibold leading-none sm:inline-block">
                  ⌘K
                </kbd>
              </button>
            )}

            {/* Resize divider (desktop, open only) — sits on the pane's left edge. */}
            {paneOpen && (
              <PaneResizer
                width={width}
                min={MIN_WIDTH}
                max={MAX_WIDTH}
                onResize={handleResize}
                className="absolute -left-1 top-0 z-10 hidden h-full w-2 lg:block"
              />
            )}

            {/* Mobile-only scrim behind the bottom-sheet (z-30 < shell's z-40). Tapping it closes
                the sheet. `lg:hidden` keeps it out of the desktop static-pane layout entirely. */}
            {paneOpen && (
              <button
                type="button"
                aria-hidden="true"
                tabIndex={-1}
                onClick={handleClose}
                className="lg:hidden fixed inset-0 z-30 bg-black/50"
              />
            )}

            {/* Unified secondary-pane shell — always mounted (bodies persist across close/reopen),
                but hidden + removed from the a11y tree when closed. */}
            <div
              ref={shellRef}
              role="dialog"
              aria-label="Ask this Filing"
              aria-modal={modalActive ? true : undefined}
              aria-hidden={!paneOpen}
              className={`${SHELL_CLASSES} ${paneOpen ? 'lg:border-l lg:border-border-light dark:lg:border-white/10' : 'hidden'}`}
            >
              <SecondaryPaneTabs
                activeView={activeView}
                onSelectAnswer={() => viewer?.setActiveView('copilot')}
                onSelectFiling={() => viewer?.openFiling()}
                onClose={() => onOpenChange(false)}
                openOriginal={activeView === 'filing' ? openOriginal : null}
              />
              <div className="flex min-h-0 flex-1 flex-col">
                <div
                  id={PANE_PANEL_IDS.copilot}
                  role="tabpanel"
                  aria-labelledby={PANE_TAB_IDS.copilot}
                  className={activeView === 'copilot' ? 'flex min-h-0 flex-1 flex-col' : 'hidden'}
                >
                  {copilotBody}
                </div>
                <div
                  id={PANE_PANEL_IDS.filing}
                  role="tabpanel"
                  aria-labelledby={PANE_TAB_IDS.filing}
                  className={activeView === 'filing' ? 'flex min-h-0 flex-1 flex-col' : 'hidden'}
                >
                  {filingBody}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

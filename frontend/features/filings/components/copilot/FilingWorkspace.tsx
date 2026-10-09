'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { ArrowSquareOutIcon, SparkleIcon } from '@/lib/icons'
import PaneResizer from './PaneResizer'
import SecondaryPaneTabs, { PANE_PANEL_IDS, PANE_TAB_IDS } from './SecondaryPaneTabs'
import CopilotCoachmark from './CopilotCoachmark'
import { isHttpUrl } from './CitationChip'
import { useFilingViewer } from './FilingViewerContext'
import { useSheetFocusTrap } from './useSheetFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { useConsentLayer } from '@/hooks/useConsentLayer'
import { BOTTOM_CHROME_OFFSET } from '@/lib/consentLayer'

// Below lg the secondary pane is a modal bottom-sheet; at lg+ it's a static side pane (no modal).
const MOBILE_MEDIA_QUERY = '(max-width: 1023.98px)'

// One-time discovery nudge (ping + coachmark) keyed in localStorage so it never nags twice.
const COACH_KEY = 'en:copilot-coachmark-v1'

// Hero launcher pinned bottom-RIGHT, clear of the iOS home indicator / Android nav bar and of the
// cookie-consent bar: BOTTOM_CHROME_OFFSET keeps a 1.25rem base gap on flat phones, adds the
// safe-area inset on notched ones (needs viewport-fit=cover) and the bar's height while it is
// mounted (`--consent-inset`, lib/consentLayer) — the bar sits beneath this z-40 chrome on z-consent
// and must never be covered by it, nor cover it.
const LAUNCHER_OFFSET: CSSProperties = {
  bottom: BOTTOM_CHROME_OFFSET,
  right: 'max(1.25rem, env(safe-area-inset-right))',
}
// The coachmark floats just above the launcher.
const COACHMARK_OFFSET: CSSProperties = {
  bottom: `calc(${BOTTOM_CHROME_OFFSET} + 4rem)`,
  right: 'max(1.25rem, env(safe-area-inset-right))',
}

const DEFAULT_WIDTH = 420
const MIN_WIDTH = 360
const MAX_WIDTH = 640
const STORAGE_KEY = 'copilot:paneWidth'

function clampWidth(w: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, w))
}

/** Where a closing pane may return focus: an element still in the document and outside the pane. */
function isReturnTarget(el: HTMLElement | null | undefined, pane: HTMLElement | null): el is HTMLElement {
  return !!el?.isConnected && !pane?.contains(el)
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
// personalities — so each body mounts exactly once across breakpoints. The sheet rests on the
// cookie-consent bar while that is mounted (bottom = --consent-inset) and gives up the same height
// from its 85vh cap, so its composer stays inside the viewport above the bar (EN-02).
const SHELL_CLASSES =
  'fixed inset-x-0 bottom-[var(--consent-inset,0px)] z-40 flex max-h-[calc(85vh_-_var(--consent-inset,0px))] flex-col rounded-t-2xl border border-border-light bg-panel-light text-text-primary-light dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark shadow-e5 dark:shadow-none lg:static lg:inset-auto lg:z-auto lg:h-full lg:max-h-none lg:w-full lg:rounded-none lg:border-y-0 lg:shadow-none'

interface FilingWorkspaceProps {
  /** Whether the Copilot pane is open (drives the two-column desktop layout + launcher). */
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Gates the whole Copilot surface — without a summary there's nothing to cite against. */
  summaryAvailable: boolean
  /** Demo mode (curated example/onboarding): keep the rail present-but-quiet by silencing the
   * first-run attention nudge (ping + coachmark) so it doesn't solicit on the first impression. */
  demoMode?: boolean
  /** The embedded Copilot conversation (<AskCopilotRail embedded .../>). */
  copilotBody: ReactNode
  /** The embedded filing reader (<FilingViewer embedded .../>). */
  filingBody: ReactNode
  /** The original document for the filing tab's "Open original" link: `document_url`, then `sec_url`
   * (the page derives it with `originalDocumentUrl`). */
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
  demoMode = false,
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- post-mount hydration of persisted width from localStorage (kept out of initial render to keep SSR markup deterministic)
    setWidth(readStoredWidth())
  }, [])

  // First-run discovery nudge: a subtle ping + a one-time coachmark on the launcher. Default to
  // "dismissed" so nothing renders on the server / first paint; resolve the persisted state after
  // mount (localStorage is client-only) to avoid a hydration mismatch.
  const [coachMounted, setCoachMounted] = useState(false)
  const [coachDismissed, setCoachDismissed] = useState(true)
  useEffect(() => {
    let dismissed = true
    try {
      dismissed = window.localStorage.getItem(COACH_KEY) === '1'
    } catch {
      dismissed = true // storage blocked (private mode) → keep the nudge hidden
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time hydration latch: the "seen" flag is client-only (localStorage), resolved after mount to keep SSR markup deterministic
    setCoachMounted(true)
    setCoachDismissed(dismissed)
  }, [])
  const dismissCoach = useCallback(() => {
    setCoachDismissed(true)
    try {
      window.localStorage.setItem(COACH_KEY, '1')
    } catch {
      // Ignore storage write failures — the nudge still hides for this session.
    }
  }, [])
  // Opening the rail by ANY means (launcher, ⌘K, an inline CTA) permanently marks the nudge seen.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot: persists "seen" the first time the rail opens; the cascading render is intended and bounded (fires at most once)
    if (open) dismissCoach()
  }, [open, dismissCoach])
  // Show the nudge only once there's a summary to ask about and the rail is closed — but never in
  // demo mode, where the curated first impression stays calm (the launcher remains, just no nudge),
  // and not while the cookie-consent bar is up: the launcher has moved up to clear the bar, and a
  // coachmark must not compete with the consent choice. It is deferred, not dismissed — once the
  // bar is gone it shows (unless the user already dismissed it) and points at a visible launcher.
  const consentVisible = useConsentLayer()
  const showAttention = coachMounted && !coachDismissed && summaryAvailable && !open && !demoMode && !consentVisible

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
  // A provenance chip that opened the pane (the provider's opener, recorded by requestHighlight) is
  // where focus returns on close; otherwise the launcher, which remounts on close. The trap reads
  // `.current` at cleanup time, so a getter resolves whichever applies at that moment (EN-01). An
  // opener inside the shell never qualifies: it is hidden with the pane it would return focus to.
  const peekOpener = viewer?.peekOpener
  const takeOpener = viewer?.takeOpener
  const restoreFocusRef = useMemo<RefObject<HTMLElement | null>>(
    () => ({
      get current() {
        const opener = peekOpener?.()
        return isReturnTarget(opener, shellRef.current) ? opener : launcherRef.current
      },
    }),
    [peekOpener],
  )
  useSheetFocusTrap({ active: modalActive, containerRef: shellRef, onClose: handleClose, restoreFocusRef })
  // On lg+ nothing traps focus: when a chip-opened pane closes, the shell goes display:none and any
  // focus inside it falls to <body>. Hand it back to the chip, only when it fell (focus the pane never
  // held is never moved), then forget the opener so a later launcher-driven open does not return to a
  // stale chip. This effect runs synchronously after the closing click or keydown, before Chromium
  // has moved focus off the now-hidden control (that happens in a later task), so focus still inside
  // the shell is focus that has fallen. lessons/frontend-busy-controls-stay-focusable.md (g),
  // "after it" form; lessons/frontend-dialog-opener-outlives-the-dialog.md (b).
  const wasPaneOpen = useRef(paneOpen)
  useEffect(() => {
    const was = wasPaneOpen.current
    wasPaneOpen.current = paneOpen
    if (!was || paneOpen || !takeOpener) return
    const opener = takeOpener()
    if (!isReturnTarget(opener, shellRef.current)) return
    const active = document.activeElement
    if (active !== null && active !== document.body && !shellRef.current?.contains(active)) return
    opener.focus({ preventScroll: true })
  }, [paneOpen, takeOpener])

  // A citation activated inside the Answer panel (an Ask answer's [n] chip) switches the pane to the
  // Filing tab, which hides the chip with its panel (and the answer re-renders it besides), so
  // keyboard focus falls to <body> and the next Tab restarts at the top of the page. When a keyboard
  // activation inside the panels switches the view and focus fell (to <body>, or still on the panel
  // just hidden: Chromium moves it off a hidden control only in a later task), hand it to the newly
  // selected tab, the visible control that says where the user now is. Only such an activation, in a
  // pane that was already open: opening the pane moves no focus (EN-01), and <body> after a summary
  // chip's click is focus that was never anywhere (Safari and Firefox on macOS do not focus a clicked
  // button), so it stays put; the tabs, the composer and a chip outside the pane keep their focus.
  // Keyboard only (Enter or Space on a button: a click with detail 0), as AskCopilotRail hands its
  // composer focus only to a keyboard user: a pointer's click leaves focus to the pointer, so the tab
  // never takes the arrow keys and Space from someone who clicked. The marker lasts for its event's
  // task; the effect of a discrete event runs inside it.
  const panelActivation = useRef(false)
  const markPanelActivation = useCallback((e: { detail: number }) => {
    if (e.detail !== 0) return
    panelActivation.current = true
    setTimeout(() => {
      panelActivation.current = false
    }, 0)
  }, [])
  const shown = useRef({ view: activeView, open: paneOpen })
  useEffect(() => {
    const was = shown.current
    shown.current = { view: activeView, open: paneOpen }
    const fromPanel = panelActivation.current
    panelActivation.current = false
    if (!fromPanel || !was.open || !paneOpen || was.view === activeView) return
    const active = document.activeElement
    const hiddenPanel = document.getElementById(PANE_PANEL_IDS[was.view])
    if (active !== null && active !== document.body && !hiddenPanel?.contains(active)) return
    document.getElementById(PANE_TAB_IDS[activeView])?.focus({ preventScroll: true })
  }, [activeView, paneOpen])

  const openOriginal = isHttpUrl(secUrl) ? (
    <a
      href={secUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium text-brand-strong dark:text-brand-strong-dark hover:underline"
    >
      Open original <ArrowSquareOutIcon className="h-3 w-3" />
    </a>
  ) : null

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_var(--copilot-w)]" style={style}>
      <div className="min-w-0">{children}</div>
      {/* The desktop pane is sticky under the 4rem header and ends where the consent bar begins. */}
      <div className="relative min-w-0 lg:sticky lg:top-16 lg:h-[calc(100vh_-_4rem_-_var(--consent-inset,0px))]">
        {summaryAvailable && (
          <>
            {/* Launcher (closed) */}
            {!open && (
              <>
                <button
                  ref={launcherRef}
                  type="button"
                  onClick={() => onOpenChange(true)}
                  aria-haspopup="dialog"
                  aria-expanded={false}
                  style={LAUNCHER_OFFSET}
                  className="fixed z-40 inline-flex items-center gap-2 rounded-full bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-3 text-sm font-semibold shadow-e3 dark:shadow-none transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                  aria-label="Ask this Filing"
                >
                  <SparkleIcon className="h-4 w-4" />
                  Ask this Filing
                  {/* The keycap darkens the pill it sits on (AskCopilotRail's launcher recipe) and keeps the
                      pill's label ink: a cream fill under that white ink measured 1.11:1. */}
                  <kbd className="ml-1 hidden rounded border border-black/25 bg-black/10 px-1.5 py-0.5 text-data-xs font-semibold leading-none sm:inline-block">
                    ⌘K
                  </kbd>
                  {/* First-run "new" dot — static (the decorative ping ring was removed for
                      reduced-motion parity; the solid dot is the attention affordance). */}
                  {showAttention && (
                    <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-white ring-2 ring-brand-strong dark:ring-brand-dark" />
                  )}
                </button>
                {showAttention && (
                  <CopilotCoachmark
                    onTry={() => onOpenChange(true)}
                    onDismiss={dismissCoach}
                    style={COACHMARK_OFFSET}
                  />
                )}
              </>
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

            {/* Mobile-only scrim behind the bottom-sheet (z-scrim: above the consent bar, which it dims
                and makes inert like any modal backdrop; below the shell's z-40). Tapping it closes the
                sheet. `lg:hidden` keeps it out of the desktop static-pane layout entirely. */}
            {paneOpen && (
              <button
                type="button"
                aria-hidden="true"
                tabIndex={-1}
                onClick={handleClose}
                className="lg:hidden fixed inset-0 z-scrim bg-overlay"
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
              <div className="flex min-h-0 flex-1 flex-col" onClickCapture={markPanelActivation}>
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

'use client'

import { useRef, type ReactNode } from 'react'
import { FileText, Sparkles, X } from 'lucide-react'
import type { CopilotView } from './FilingViewerContext'

// Shared ids so the tabs (here) and the tab panels (in FilingWorkspace) can reference each other
// via aria-controls / aria-labelledby — the WAI-ARIA tab pattern.
export const PANE_TAB_IDS: Record<CopilotView, string> = {
  copilot: 'copilot-pane-tab',
  filing: 'filing-pane-tab',
}
export const PANE_PANEL_IDS: Record<CopilotView, string> = {
  copilot: 'copilot-pane-panel',
  filing: 'filing-pane-panel',
}

interface SecondaryPaneTabsProps {
  activeView: CopilotView
  onSelectAnswer: () => void
  onSelectFiling: () => void
  onClose: () => void
  /** SEC "open original" link, shown only on the filing tab. */
  openOriginal?: ReactNode
}

/**
 * The single chrome row for FilingWorkspace's secondary pane: an [Answer · Filing] segmented
 * control (so the user can switch between the Copilot conversation and the filing text), the
 * "open original" SEC link (filing tab only), and the close button. Implements the WAI-ARIA tab
 * pattern — roving tabindex, arrow/Home/End navigation, and aria-controls wiring to the panels.
 */
export default function SecondaryPaneTabs({
  activeView,
  onSelectAnswer,
  onSelectFiling,
  onClose,
  openOriginal,
}: SecondaryPaneTabsProps) {
  const answerRef = useRef<HTMLButtonElement>(null)
  const filingRef = useRef<HTMLButtonElement>(null)

  const select = (view: CopilotView) => {
    if (view === 'copilot') onSelectAnswer()
    else onSelectFiling()
    ;(view === 'copilot' ? answerRef : filingRef).current?.focus()
  }

  // Arrows move (and auto-activate) between the two tabs; Home/End jump to the ends.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'End') {
      e.preventDefault()
      select('filing')
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'Home') {
      e.preventDefault()
      select('copilot')
    }
  }

  const tabBase =
    'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-light'
  const activeTab = 'bg-panel-light dark:bg-slate-700/70 text-text-primary-light dark:text-text-primary-dark'
  const idleTab = 'text-text-secondary-light dark:text-text-secondary-dark hover:text-text-secondary-light dark:hover:text-text-secondary-dark'

  return (
    <div className="flex items-center justify-between gap-2 border-b border-border-light dark:border-white/10 px-3 py-2">
      <div
        role="tablist"
        aria-label="Copilot panel views"
        onKeyDown={onKeyDown}
        className="flex items-center gap-1 rounded-lg bg-brand-weak dark:bg-slate-950/40 p-0.5"
      >
        <button
          ref={answerRef}
          id={PANE_TAB_IDS.copilot}
          type="button"
          role="tab"
          aria-selected={activeView === 'copilot'}
          aria-controls={PANE_PANEL_IDS.copilot}
          tabIndex={activeView === 'copilot' ? 0 : -1}
          onClick={onSelectAnswer}
          className={`${tabBase} ${activeView === 'copilot' ? activeTab : idleTab}`}
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          Answer
        </button>
        <button
          ref={filingRef}
          id={PANE_TAB_IDS.filing}
          type="button"
          role="tab"
          aria-selected={activeView === 'filing'}
          aria-controls={PANE_PANEL_IDS.filing}
          tabIndex={activeView === 'filing' ? 0 : -1}
          onClick={onSelectFiling}
          className={`${tabBase} ${activeView === 'filing' ? activeTab : idleTab}`}
        >
          <FileText className="h-3.5 w-3.5" aria-hidden="true" />
          Filing
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {openOriginal}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="flex h-8 w-8 items-center justify-center rounded-full text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

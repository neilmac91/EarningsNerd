'use client'

import { useRef } from 'react'
import { ChatCircleTextIcon, FileTextIcon, XIcon } from '@/lib/icons'
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

// Tab order: the filing first, then Ask (2026-10 critique P-06).
const ORDER: CopilotView[] = ['filing', 'copilot']

interface SecondaryPaneTabsProps {
  activeView: CopilotView
  onSelectAnswer: () => void
  onSelectFiling: () => void
  onClose: () => void
  /** The filing the pane shows, in the data face ("AAPL · 10-K · filed Oct 28, 2022"). */
  sourceLabel?: string | null
}

/**
 * The research pane's header (2026-10 critique P-06): the pane is named for the source. A "Source"
 * title with the filing it shows, the close button, then the [Filing · Ask] tabs — the filing first,
 * Ask beside it, underline tabs at least 36px tall (44px below lg, where the pane is a touch sheet).
 * Implements the WAI-ARIA tab pattern: roving tabindex, arrow keys wrap, Home/End jump to the ends,
 * and aria-controls wiring to the panels.
 */
export default function SecondaryPaneTabs({
  activeView,
  onSelectAnswer,
  onSelectFiling,
  onClose,
  sourceLabel,
}: SecondaryPaneTabsProps) {
  const refs = { filing: useRef<HTMLButtonElement>(null), copilot: useRef<HTMLButtonElement>(null) }

  const select = (view: CopilotView) => {
    if (view === 'copilot') onSelectAnswer()
    else onSelectFiling()
    refs[view].current?.focus()
  }

  // Arrows move from the tab that has focus (normally the selected one, under the roving tabindex).
  const onKeyDown = (e: React.KeyboardEvent) => {
    const at = ORDER.indexOf(ORDER.find((view) => refs[view].current === e.target) ?? activeView)
    const next =
      e.key === 'ArrowRight' || e.key === 'ArrowDown'
        ? ORDER[(at + 1) % ORDER.length]
        : e.key === 'ArrowLeft' || e.key === 'ArrowUp'
          ? ORDER[(at - 1 + ORDER.length) % ORDER.length]
          : e.key === 'Home'
            ? ORDER[0]
            : e.key === 'End'
              ? ORDER[ORDER.length - 1]
              : null
    if (!next) return
    e.preventDefault()
    select(next)
  }

  const tab = (view: CopilotView, label: string, Icon: typeof FileTextIcon, onClick: () => void) => {
    const active = activeView === view
    return (
      <button
        ref={refs[view]}
        id={PANE_TAB_IDS[view]}
        type="button"
        role="tab"
        aria-selected={active}
        aria-controls={PANE_PANEL_IDS[view]}
        tabIndex={active ? 0 : -1}
        onClick={onClick}
        className={
          '-mb-px inline-flex min-h-11 items-center gap-1.5 border-b-2 text-sm transition-colors duration-fast lg:min-h-9 ' +
          'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ' +
          (active
            ? 'border-brand font-semibold text-text-primary-light dark:border-brand-dark dark:text-text-primary-dark'
            : 'border-transparent font-medium text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark')
        }
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        {label}
      </button>
    )
  }

  return (
    <div className="border-b border-border-light dark:border-white/10">
      <div className="flex items-start justify-between gap-3 px-4 pt-3">
        <div className="min-w-0 pt-1">
          <p className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Source</p>
          {sourceLabel && (
            <p className="break-words font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">{sourceLabel}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-text-secondary-light transition-colors hover:bg-white hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand lg:-mr-1 lg:h-8 lg:w-8 dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>
      <div role="tablist" aria-label="Source pane views" onKeyDown={onKeyDown} className="mt-1 flex items-center gap-5 px-4">
        {tab('filing', 'Filing', FileTextIcon, onSelectFiling)}
        {tab('copilot', 'Ask', ChatCircleTextIcon, onSelectAnswer)}
      </div>
    </div>
  )
}

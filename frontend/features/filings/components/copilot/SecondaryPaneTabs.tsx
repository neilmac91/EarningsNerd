'use client'

import { type ReactNode } from 'react'
import { FileText, Sparkles, X } from 'lucide-react'
import type { CopilotView } from './FilingViewerContext'

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
 * "open original" SEC link (filing tab only), and the close button. Replaces the separate headers
 * the rail and viewer used to carry, so there's one header, not two.
 */
export default function SecondaryPaneTabs({
  activeView,
  onSelectAnswer,
  onSelectFiling,
  onClose,
  openOriginal,
}: SecondaryPaneTabsProps) {
  const tabBase =
    'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mint-400'
  const activeTab = 'bg-slate-700/70 text-white'
  const idleTab = 'text-slate-400 hover:text-slate-200'

  return (
    <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
      <div
        role="tablist"
        aria-label="Copilot panel views"
        className="flex items-center gap-1 rounded-lg bg-slate-950/40 p-0.5"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'copilot'}
          onClick={onSelectAnswer}
          className={`${tabBase} ${activeView === 'copilot' ? activeTab : idleTab}`}
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          Answer
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'filing'}
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
          className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

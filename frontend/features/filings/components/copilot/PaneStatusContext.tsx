'use client'

import { createContext, useContext } from 'react'

/**
 * The research pane's status line: FilingWorkspace renders one sr-only status region between the [Filing · Ask] tabs
 * and the two panels, so the accessibility tree holds it whichever tab shows, and below lg it sits inside the sheet's
 * dialog. The Ask rail hands it its words through this context, whose value is the line's state setter: it never
 * changes, so nothing re-renders for it. Null outside the workspace, where the rail keeps a line of its own.
 */
export const PaneStatusContext = createContext<((words: string) => void) | null>(null)

/** The pane's status line setter, or null outside the filing workspace. */
export function usePaneStatus(): ((words: string) => void) | null {
  return useContext(PaneStatusContext)
}

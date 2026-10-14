import type { SectionChanges, SectionChangesOk } from '@/features/summaries/api/summaries-api'

/**
 * Pure readings of the change report's Item 1A wording block (E27), shared by the server-rendered
 * report (WhatChanged, the landing page's sample included) and the client components that show and
 * count it. Kept out of WordingChanges.tsx, a client module, so a server render can call them.
 */

/** Whether the block has a comparison to show. A 10-Q whose Item 1A only refers back to the annual
 *  report's risk factors restates nothing, so it is not shown as a section that was compared. */
export function wordingHasContent(block: SectionChanges | null | undefined): block is SectionChangesOk {
  return Boolean(block && block.status === 'ok' && !block.current.reference_only)
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** "13 paragraphs changed: 8 modified, 3 added, 1 removed and 1 moved" */
export function changesPhrase(counts: SectionChangesOk['counts']): string {
  const parts: string[] = []
  if (counts.modified) parts.push(`${counts.modified} modified`)
  if (counts.added) parts.push(`${counts.added} added`)
  if (counts.removed) parts.push(`${counts.removed} removed`)
  if (counts.moved) parts.push(`${counts.moved} moved`)
  const total = counts.modified + counts.added + counts.removed + counts.moved
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}` : parts[0]
  return `${plural(total, 'paragraph')} changed: ${list}`
}

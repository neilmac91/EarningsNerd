/**
 * Remove ONLY a leading `## Executive Summary` heading from the summary markdown, leaving every
 * later section heading (`## Financials`, `## Outlook`, …) intact.
 *
 * The backend always emits `## Executive Summary` first (markdown_render.py). Rendered next to the
 * frontend "Summary" card title + "Full summary" badge, that produced three stacked headings
 * (T1.7 defect d). Stripping the leading H2 leaves ONE header — the DS CardTitle.
 *
 * Deliberately a SEPARATE function, not a change to stripInternalNotices: summaryStream.spec.ts
 * pins that stripInternalNotices PRESERVES `## Executive Summary`, so modifying it would break a
 * green contract test. Compose the two at the call site.
 */
export const stripLeadingExecutiveHeading = (markdown: string): string => {
  if (!markdown) return ''
  const lines = markdown.split('\n')
  let i = 0
  while (i < lines.length && !lines[i].trim()) i += 1
  if (i < lines.length && /^#{1,6}\s+executive summary\s*$/i.test(lines[i].trim())) {
    lines.splice(i, 1)
  }
  return lines.join('\n')
}

export default stripLeadingExecutiveHeading

import { deriveRiskHeadline } from '@/features/summaries/lib/riskHeadline'

/**
 * Headings for the source-first risk rows (2026-10 critique P-03).
 *
 * The server withholds model-written titles: every projected risk is labelled "Filing excerpt"
 * (backend provenance_service), so each row is headed by the opening words of its own verbatim
 * excerpt, cut by deriveRiskHeadline (riskHeadline.ts): a prefix of the excerpt, never recased or
 * rewritten ("iPhone" stays "iPhone"), with a trailing ellipsis when the excerpt goes on, or the
 * positional "Risk n" when the excerpt cannot give one. The filing's whitespace is kept (a no-break
 * space stays one).
 *
 * One pair of enclosing quote marks is dropped first, since the blockquote under the heading shows
 * them: only when the whole span opens with “, " or ‘ and closes with its match, and neither mark
 * occurs inside. Any other span keeps every byte.
 *
 * Unique: a heading an earlier row already took gets the first free occurrence number ("… (2)", then
 * "… (3)" if a heading itself ended in "(2)"), so the accessibility tree never lists two identical
 * headings.
 */

const ENCLOSING_PAIRS: Record<string, string> = { '“': '”', '"': '"', '‘': '’' }

/** The span inside one enclosing pair of quote marks, when it has exactly that pair; else the excerpt untouched. */
const withoutEnclosingQuotes = (excerpt: string): string => {
  const span = excerpt.trim()
  const open = span.charAt(0)
  const close = ENCLOSING_PAIRS[open]
  if (!close || span.length < 2 || !span.endsWith(close)) return excerpt
  const inner = span.slice(1, -1)
  return inner.includes(open) || inner.includes(close) ? excerpt : inner
}

export function excerptHeadings(excerpts: string[]): string[] {
  const taken = new Set<string>()
  return excerpts.map((excerpt, index) => {
    const title = deriveRiskHeadline(withoutEnclosingQuotes(excerpt), index)
    let heading = title
    for (let n = 2; taken.has(heading.toLowerCase()); n += 1) heading = `${title} (${n})`
    taken.add(heading.toLowerCase())
    return heading
  })
}

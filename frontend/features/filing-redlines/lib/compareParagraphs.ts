export const MAX_COMPARISON_CHARACTERS = 120_000
export const MAX_COMPARISON_PARAGRAPHS = 400

export interface ParagraphComparison {
  added: string[]
  removed: string[]
  unchangedCount: number
}

function paragraphs(text: string, label: string): string[] {
  if (text.length > MAX_COMPARISON_CHARACTERS) {
    throw new Error(`${label} text exceeds the ${MAX_COMPARISON_CHARACTERS.toLocaleString('en-US')}-character comparison limit.`)
  }

  const result = text
    .split(/\r?\n[^\S\r\n]*\r?\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)

  if (result.length === 0) {
    throw new Error(`${label} text is empty. Both filings need cached text to compare.`)
  }
  if (result.length > MAX_COMPARISON_PARAGRAPHS) {
    throw new Error(`${label} text exceeds the ${MAX_COMPARISON_PARAGRAPHS}-paragraph comparison limit.`)
  }
  return result
}

function normalized(paragraph: string): string {
  return paragraph.replace(/\s+/g, ' ')
}

function counts(paragraphs: string[]): Map<string, number> {
  const result = new Map<string, number>()
  for (const paragraph of paragraphs) {
    const key = normalized(paragraph)
    result.set(key, (result.get(key) ?? 0) + 1)
  }
  return result
}

function unmatched(paragraphs: string[], remaining: Map<string, number>): string[] {
  return paragraphs.filter((paragraph) => {
    const key = normalized(paragraph)
    const count = remaining.get(key) ?? 0
    if (count === 0) return true
    remaining.set(key, count - 1)
    return false
  })
}

/**
 * Compare an exact multiset of paragraphs, ignoring whitespace and paragraph moves.
 * Retain the source text and order for unmatched occurrences. No semantic pairing or
 * materiality judgment is implied; a changed paragraph appears once on each side.
 */
export function compareParagraphs(earlier: string, current: string): ParagraphComparison {
  const earlierParagraphs = paragraphs(earlier, 'Earlier filing')
  const currentParagraphs = paragraphs(current, 'Current filing')
  const removed = unmatched(earlierParagraphs, counts(currentParagraphs))
  const added = unmatched(currentParagraphs, counts(earlierParagraphs))

  return {
    added,
    removed,
    unchangedCount: earlierParagraphs.length - removed.length,
  }
}

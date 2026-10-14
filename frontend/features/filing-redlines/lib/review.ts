import { MAX_COMPARISON_CHARACTERS, MAX_COMPARISON_PARAGRAPHS, type ParagraphComparison } from './compareParagraphs'
import type { RedlinePair } from './filingPair'

export type ReviewStatus = 'unreviewed' | 'reviewed' | 'needs-follow-up'
export type ReviewLabels = Record<string, ReviewStatus>

export function reviewChanges(comparison: ParagraphComparison, labels: ReviewLabels) {
  return (['removed', 'added'] as const).flatMap((kind) => comparison[kind].map((text, index) => {
    // An occurrence retains its identity under filtering, including duplicate paragraphs.
    const id = `${kind}-${index + 1}`
    return { id, kind, occurrence: index + 1, text, reviewStatus: labels[id] ?? 'unreviewed' }
  }))
}

/** Always export the complete comparison; the display filter is deliberately not an input. */
export function createReviewReceipt(pair: RedlinePair, comparison: ParagraphComparison, labels: ReviewLabels, exportedAt: string) {
  const changes = reviewChanges(comparison, labels)
  const reviewed = changes.filter((change) => change.reviewStatus === 'reviewed').length
  return {
    schemaVersion: 1,
    exportedAt,
    fictional: pair.fictional,
    sources: { earlier: { ...pair.earlier, form: '10-K' }, later: { ...pair.current, form: '10-K' } },
    scope: {
      text: pair.fictional ? 'Invented excerpts; no real issuer or SEC source.' : 'Available cached text; full-filing coverage has not been verified.',
      fullFilingCoverageVerified: false,
      included: 'All added and removed paragraph occurrences, regardless of the display filter. Matched text is not included.',
      unsupported: 'Section extraction, tables as structured data, semantic pairing, word-level alignment and materiality assessment.',
    },
    method: {
      name: 'exact-paragraph-multiset-v1',
      matching: 'Internal whitespace is normalized; paragraph order is ignored; duplicate counts, case, punctuation and numbers are preserved.',
      display: 'Paragraph text is preserved with outer whitespace trimmed. A changed paragraph is an addition plus a removal, not a paired edit.',
      maximumCharactersPerInput: MAX_COMPARISON_CHARACTERS,
      maximumParagraphsPerInput: MAX_COMPARISON_PARAGRAPHS,
    },
    review: {
      meaning: 'User tracking only. Reviewed does not verify a source or establish materiality, completeness or investment suitability.',
      persistence: 'Labels and search exist only in current browser memory; this downloaded receipt is a snapshot, not a server audit record.',
      total: changes.length,
      reviewed,
      remaining: changes.length - reviewed,
      needsFollowUp: changes.filter((change) => change.reviewStatus === 'needs-follow-up').length,
    },
    matchedParagraphCount: comparison.unchangedCount,
    changes,
  }
}

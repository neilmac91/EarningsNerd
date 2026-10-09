import type { Summary } from '@/features/summaries/api/summaries-api'

/**
 * The summary's verification tally (2026-10 critique, the "verification ledger" pattern): counts of
 * what the server matched, read from the payload the page already has. Scoped vocabulary only —
 * figures "matched the company's XBRL", excerpts "located in the filing text", the rest "withheld";
 * never "verified" without saying against what.
 *
 * - figures: the Financial highlights rows (every `metrics` block) the server could check at all
 *   (`source_checkable`: a concept it maps, of at least $1M), and of those the rows whose value it
 *   matched against the SEC-filed XBRL value (`source_verified`, the chip's "SEC XBRL"). Per-share
 *   figures, ratios, margins and segment lines are never checked, so they are never counted as
 *   misses. A payload from before the flag yields no figures count rather than a wrong one.
 * - excerpts: the source-first risk projection's own counts (backend provenance_service).
 *
 * Null when neither applies, so a legacy summary shows no tally rather than a zero.
 */
export interface VerificationTally {
  figures: { matched: number; total: number } | null
  excerpts: { located: number; total: number; withheld: number } | null
}

interface RiskProjection {
  version?: number
  verified_count?: number
  withheld_count?: number
  candidate_count?: number
}

export function verificationTally(summary: Summary | null | undefined): VerificationTally | null {
  if (!summary) return null
  const rows = (summary.rendered_sections ?? [])
    .flatMap((section) => section.blocks)
    .filter((block) => block.kind === 'metrics')
    .flatMap((block) => block.metric_rows ?? [])
  const checkable = rows.filter((row) => row.source_checkable === true)
  const figures = checkable.length > 0
    ? { matched: checkable.filter((row) => row.source_verified === true).length, total: checkable.length }
    : null

  const raw = summary.raw_summary
  const projection = raw?.risk_source_context_version === 1
    ? (raw.sections as { _risk_source_projection?: RiskProjection } | undefined)?._risk_source_projection
    : undefined
  let excerpts: VerificationTally['excerpts'] = null
  if (projection?.version === 1 && typeof projection.verified_count === 'number') {
    const located = projection.verified_count
    const withheld = typeof projection.withheld_count === 'number' ? projection.withheld_count : 0
    const candidates = typeof projection.candidate_count === 'number' ? projection.candidate_count : located + withheld
    if (candidates > 0) excerpts = { located, total: Math.max(candidates, located), withheld }
  }

  return figures || excerpts ? { figures, excerpts } : null
}

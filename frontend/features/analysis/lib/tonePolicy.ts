import type { Direction } from '@/lib/financialTone'
import type { SeriesTone } from '@/features/analysis/api/analysis-api'

/**
 * Map a sign-based direction to the tone actually displayed for a series. The valence judgment
 * (debt up = cost/risk → inverted; capex/investing/financing = strategic choice → neutral) is
 * the DATASET's, shipped per series as `tone` by the backend (trend_analysis_service's
 * _SERIES_TONE) — the same source-of-truth pattern as `percent` — so the concept lists live in
 * exactly one place. A missing or unknown tone (old fixture, deploy skew) keeps the default
 * sign-based reading; an already-flat direction is never overridden.
 */
export function applySeriesTone(
  tone: SeriesTone | null | undefined,
  direction: Direction
): Direction {
  if (direction === 'flat') return 'flat'
  if (tone === 'neutral') return 'flat'
  if (tone === 'inverted') return direction === 'up' ? 'down' : 'up'
  return direction
}

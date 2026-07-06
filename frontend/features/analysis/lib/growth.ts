import { fmtPercent, fmtPercentPoints } from '@/lib/format'
import { directionOf, type Direction } from '@/lib/financialTone'
import type { GrowthValue } from '@/features/analysis/api/analysis-api'

/**
 * Render a YoY/QoQ delta consistently everywhere it appears (metrics table, KPI strip): "n/m"
 * for a sign-flip crossing (flat tone — it isn't a real up/down move), percentage points for a
 * `percent`-unit series (margins — the value is already pp, never ×100), relative percentage
 * for everything else.
 */
export function formatGrowth(
  value: GrowthValue | null | undefined,
  isPercent: boolean
): { text: string; direction: Direction } {
  if (value === null || value === undefined) return { text: '', direction: 'flat' }
  if (value === 'nm') return { text: 'n/m', direction: 'flat' }
  if (isPercent) return { text: fmtPercentPoints(value, { digits: 1 }), direction: directionOf(value) }
  return { text: fmtPercent(value * 100, { digits: 1, signed: true }), direction: directionOf(value) }
}

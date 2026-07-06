import { describe, expect, it } from 'vitest'
import { progressRefetchInterval } from '@/features/summaries/hooks/useSummaryGeneration'

// L1 completion: the progress poll must stop on EVERY terminal stage the backend writes. The backend
// writes three — completed, error, AND partial (record_progress(..., "partial") on the timeout /
// low-coverage path). `partial` was missing from the terminal set, so a placeholder page backed by a
// partial-ending run polled at 1s forever. Guard all three so "never outlives the generation" holds.
describe('progressRefetchInterval (L1 poll terminal set)', () => {
  it('stops (false) on every terminal backend stage', () => {
    for (const stage of ['completed', 'error', 'partial'] as const) {
      expect(progressRefetchInterval(stage)).toBe(false)
    }
  })

  it('keeps polling (1000ms) on non-terminal / unknown stages', () => {
    expect(progressRefetchInterval('summarizing')).toBe(1000)
    expect(progressRefetchInterval(undefined)).toBe(1000)
  })
})

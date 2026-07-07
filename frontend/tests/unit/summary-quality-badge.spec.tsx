import { partialBadgeLabel } from '@/features/summaries/components/SummaryDisplay'

// P0-2 badge de-escalation guardrail (data-quality plan, safeguard #5): when the heuristic
// XBRL literal-grounding check is the ONLY partial reason, the badge reads neutrally instead
// of accusing the data of being ungrounded (it false-fired on every bank pre-fix).
describe('partialBadgeLabel', () => {
  it('de-escalates the sole grounding reason to neutral wording', () => {
    expect(partialBadgeLabel(['financial figures not grounded in SEC XBRL data'])).toBe(
      'Partial coverage',
    )
  })

  it('keeps specific wording for other reasons', () => {
    expect(partialBadgeLabel(['only 3/9 sections populated'])).toBe(
      'Partial · only 3/9 sections populated',
    )
  })

  it('keeps the first reason when the grounding reason is not alone', () => {
    expect(
      partialBadgeLabel([
        'financial figures not grounded in SEC XBRL data',
        'only 3/9 sections populated',
      ]),
    ).toBe('Partial · financial figures not grounded in SEC XBRL data')
  })

  it('handles missing reasons', () => {
    expect(partialBadgeLabel(undefined)).toBe('Partial')
    expect(partialBadgeLabel([])).toBe('Partial')
  })
})

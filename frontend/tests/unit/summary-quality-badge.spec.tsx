import { partialBadgeLabel, reasonWords } from '@/features/summaries/components/SummaryDisplay'

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

  it('keeps the first reason when the grounding reason is not alone, in the product’s words', () => {
    // No acronym in a label (D-058): the server's "SEC XBRL" reason reads as plain words on the badge and its tooltip.
    expect(
      partialBadgeLabel([
        'financial figures not grounded in SEC XBRL data',
        'only 3/9 sections populated',
      ]),
    ).toBe('Partial · the filed revenue or net income is not stated in the summary')
    // Each in words for what its check covers: the grounding check looks for the filed figures in the summary's text.
    expect(reasonWords('financial figures not grounded in SEC XBRL data')).toBe('the filed revenue or net income is not stated in the summary')
    expect(reasonWords('filing grounding unavailable: no usable excerpt or numeric XBRL data')).toBe(
      'the filing’s text and figures were unavailable to check against',
    )
    expect(reasonWords('only 3/9 sections populated')).toBe('only 3/9 sections populated')
  })

  it('handles missing reasons', () => {
    expect(partialBadgeLabel(undefined)).toBe('Partial')
    expect(partialBadgeLabel([])).toBe('Partial')
  })
})

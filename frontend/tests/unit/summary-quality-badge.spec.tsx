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
    ).toBe('Partial · filed revenue or net income not stated')
    expect(partialBadgeLabel(['filing grounding unavailable: no usable excerpt or numeric XBRL data'])).toBe(
      'Partial · no filing text or figures to check',
    )
    // The tooltip reads each in full, in words for what its check covers: the grounding check looks for the filed
    // figures in the summary's text.
    expect(reasonWords('financial figures not grounded in SEC XBRL data')).toBe('the filed revenue or net income is not stated in the summary')
    expect(reasonWords('filing grounding unavailable: no usable excerpt or numeric XBRL data')).toBe(
      'the filing’s text and figures were unavailable to check against',
    )
    expect(reasonWords('only 3/9 sections populated')).toBe('only 3/9 sections populated')
  })

  it('keeps each reason the server writes within the characters measured to fit one line on a phone', () => {
    // Badge is nowrap, and the filing page's content box is 358px at 390px. Measured in Chromium at the badge's 12px/600
    // Inter: the 59 characters of "Partial · 12 summary figure(s) not traceable to filing data" are 351px, and the
    // long words this replaced (70 and 73 characters) were 422px and 429px. The count bounds these strings only, not a
    // width: 58 characters of other words reach 392px, so a new or reworded reason is measured before it ships
    // (test_quality_grounding_presence.py requires each reason the server writes to open an entry below). A count of 100 or
    // more passes the box by a pixel (only with AI_FIGURE_TRACE_GATE on), and under 200% text the badge, which never
    // wraps, is wider than a phone (E181).
    const firsts = [
      ['financial figures not grounded in SEC XBRL data', 'only 3/9 sections populated'],
      ['filing grounding unavailable: no usable excerpt or numeric XBRL data'],
      ['only 3/9 sections populated'],
      ['12 summary figure(s) not traceable to filing data'],
    ]
    for (const reasons of firsts) expect(partialBadgeLabel(reasons).length, partialBadgeLabel(reasons)).toBeLessThanOrEqual(59)
  })

  it('handles missing reasons', () => {
    expect(partialBadgeLabel(undefined)).toBe('Partial')
    expect(partialBadgeLabel([])).toBe('Partial')
  })
})

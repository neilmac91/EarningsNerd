import { render, screen } from '@testing-library/react'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'
import type { RiskFactor } from '@/types/summary'
import filing3Risks from '../e2e/fixtures/filing-3-risks.json'

// The evidence rows' wiring (founder option b): each row's h3 is excerptHeadings of the shown spans,
// in order, and its blockquote carries the whole span. The heading rule is pinned in
// riskHeadline.spec.ts and riskTitle.spec.ts; "model labels never reach a heading" in SummaryBlocks.spec.tsx.

const RISKS: RiskFactor[] = filing3Risks
const SPANS = RISKS.map((risk) => risk.supporting_evidence)

describe('SummaryRisks rows', () => {
  it('heads each production span with excerptHeadings and quotes the span whole, byte for byte', () => {
    render(<SummaryRisks risks={RISKS} projection={{ version: 1, verified_count: 4, withheld_count: 0 }} />)
    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings.map((h) => h.textContent)).toEqual(excerptHeadings(SPANS))
    headings.forEach((heading, i) => {
      // textContent, not the whitespace-normalising text matchers, so the filing's no-break space counts.
      expect(heading.closest('li')!.querySelector('blockquote')!.textContent).toContain(SPANS[i])
    })
  })
})

import React from 'react'
import { render, screen, within } from '@testing-library/react'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { deriveRiskHeadline } from '@/features/summaries/lib/riskHeadline'
import { QuotesIcon, TrendDownIcon } from '@/lib/icons'
import type { RiskFactor } from '@/types/summary'
import filing3Risks from '../e2e/fixtures/filing-3-risks.json'

// Risk cards (founder option b): each card is titled with a verbatim prefix of its own verified
// excerpt, under a neutral quotation glyph, never the bearish trend arrow. The excerpt still renders
// in full below the heading as the evidence. The exact headlines are pinned in riskHeadline.spec.ts;
// the "model labels never reach a heading" rule is pinned in SummaryBlocks.spec.tsx.

const PROJECTION = { version: 1, verified_count: 4, withheld_count: 0 }

/** The production filing-3 risk spans, as the backend projects them (summary/section ref = the fixed label). */
const SPANS = filing3Risks.map((risk) => risk.supporting_evidence)

const projected = (excerpt: string): RiskFactor => ({
  summary: 'Filing excerpt',
  supporting_evidence: excerpt,
  source_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm#:~:text=x',
  source_verified: true,
  source_section_ref: 'Filing excerpt',
})

/** The glyph's geometry: an svg's children, which do not carry the className it was given. */
const glyphOf = (element: React.ReactElement): string => {
  const { container, unmount } = render(element)
  const markup = container.querySelector('svg')!.innerHTML
  unmount()
  return markup
}

/** The decorative glyph rendered beside a card heading. */
const cardGlyph = (heading: HTMLElement): string => heading.parentElement!.querySelector('svg')!.innerHTML

describe('SummaryRisks cards', () => {
  it('titles each card with a verbatim prefix of its own excerpt and keeps the full excerpt below', () => {
    render(<SummaryRisks risks={SPANS.map((s) => projected(s))} projection={PROJECTION} />)
    const headings = screen.getAllByRole('heading', { level: 4 })
    expect(headings.map((h) => h.textContent)).toEqual(SPANS.map((span, i) => deriveRiskHeadline(span, i)))
    for (const [i, heading] of headings.entries()) {
      expect(heading.textContent).not.toMatch(/^Filing excerpt \d+$/)
      // Same card: its Evidence box carries the whole excerpt, byte for byte (textContent, not the
      // whitespace-normalised text matchers, so the filing's no-break space counts).
      const card = heading.closest('[data-summary-block]') as HTMLElement
      expect(within(card).getByText('Evidence').parentElement!.textContent).toContain(SPANS[i])
      expect(SPANS[i].startsWith(heading.textContent!.replace(/…$/, ''))).toBe(true)
    }
  })

  it('keeps the positional "Filing excerpt n" title when an excerpt is too short to title the card', () => {
    render(
      <SummaryRisks risks={[projected(SPANS[1]), projected('Tariffs.')]} projection={{ ...PROJECTION, verified_count: 2 }} />,
    )
    expect(screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual([deriveRiskHeadline(SPANS[1], 0), 'Filing excerpt 2'])
  })

  it('marks every card with the neutral quotation glyph, not the bearish trend arrow', () => {
    const quotes = glyphOf(<QuotesIcon />)
    const trendDown = glyphOf(<TrendDownIcon />)
    expect(quotes).not.toBe(trendDown)

    render(<SummaryRisks risks={SPANS.map((s) => projected(s))} projection={PROJECTION} />)
    for (const heading of screen.getAllByRole('heading', { level: 4 })) {
      expect(cardGlyph(heading)).toBe(quotes)
      expect(heading.parentElement!.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    }
  })

  it('leaves the shared block’s bearish callout on its trend arrow', () => {
    const trendDown = glyphOf(<TrendDownIcon />)
    render(
      <SummaryBlock type="bearish" title="Red flag">
        Receivables outpaced sales.
      </SummaryBlock>,
    )
    expect(cardGlyph(screen.getByRole('heading', { level: 4, name: 'Red flag' }))).toBe(trendDown)
  })
})

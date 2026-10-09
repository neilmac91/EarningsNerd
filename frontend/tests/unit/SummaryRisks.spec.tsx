import React from 'react'
import { render, screen, within } from '@testing-library/react'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { QuotesIcon, TrendDownIcon } from '@/lib/icons'
import type { RiskFactor } from '@/types/summary'

// Risk cards (founder option b): each card is titled with a verbatim prefix of its own verified
// excerpt, under a neutral quotation glyph, never the bearish trend arrow, and never a
// model-authored label. The excerpt still renders in full below the heading as the evidence.

const PROJECTION = { version: 1, verified_count: 4, withheld_count: 0 }

/** The production filing-3 risk spans, as the backend projects them (summary/section ref = the fixed label). */
const SPANS = [
  'Tariffs and other measures that are applied to the Company’s products or their components can have a material adverse impact on the Company’s business, results of operations and financial condition, including impacting the Company’s supply chain, the availability of rare earths and other raw materials and components, pricing and gross margin.',
  'Substantially all of the Company’s hardware products are manufactured by outsourcing partners that are located primarily in China mainland, India, Japan, South Korea, Taiwan and Vietnam.',
  'As of September\u00a027, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion, of which $10.6 billion, if recognized, would impact the Company’s effective tax rate.',
  'Regardless of the merit of particular claims, defending against litigation or responding to government investigations can be expensive, time-consuming and disruptive to the Company’s operations.',
]
const HEADLINES = [
  'Tariffs and other measures that are applied to the Company’s products or their components…',
  'Substantially all of the Company’s hardware products are manufactured by outsourcing partners…',
  'As of September\u00a027, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion…',
  'Regardless of the merit of particular claims, defending against litigation or responding…',
]

const projected = (excerpt: string, extra: Partial<RiskFactor> = {}): RiskFactor => ({
  summary: 'Filing excerpt',
  supporting_evidence: excerpt,
  source_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm#:~:text=x',
  source_verified: true,
  source_section_ref: 'Filing excerpt',
  ...extra,
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
    expect(headings.map((h) => h.textContent)).toEqual(HEADLINES)
    for (const [i, heading] of headings.entries()) {
      // Same card: its Evidence box carries the whole excerpt, byte for byte (textContent, not the
      // whitespace-normalised text matchers, so the filing's no-break space counts).
      const card = heading.closest('[data-summary-block]') as HTMLElement
      expect(within(card).getByText('Evidence').parentElement!.textContent).toContain(SPANS[i])
      expect(SPANS[i].startsWith(HEADLINES[i].replace(/…$/, ''))).toBe(true)
    }
  })

  it('never titles a card with a model-authored label', () => {
    const risks = [
      projected(SPANS[0], { summary: 'Customer concentration', title: 'FX headwinds', description: 'Forged label' }),
    ]
    render(<SummaryRisks risks={risks} projection={{ ...PROJECTION, verified_count: 1 }} />)
    expect(screen.getByRole('heading', { level: 4 })).toHaveTextContent(HEADLINES[0])
    expect(screen.queryByText(/Customer concentration|FX headwinds|Forged label/)).not.toBeInTheDocument()
  })

  it('keeps the positional "Filing excerpt n" title when an excerpt is too short to title the card', () => {
    render(
      <SummaryRisks risks={[projected(SPANS[1]), projected('Tariffs.')]} projection={{ ...PROJECTION, verified_count: 2 }} />,
    )
    expect(screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual([HEADLINES[1], 'Filing excerpt 2'])
  })

  it('marks every card with the neutral quotation glyph, not the bearish trend arrow, on the panel fill', () => {
    const quotes = glyphOf(<QuotesIcon />)
    const trendDown = glyphOf(<TrendDownIcon />)
    expect(quotes).not.toBe(trendDown)

    render(<SummaryRisks risks={SPANS.map((s) => projected(s))} projection={PROJECTION} />)
    for (const heading of screen.getAllByRole('heading', { level: 4 })) {
      expect(cardGlyph(heading)).toBe(quotes)
      expect(heading.parentElement!.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
      // Rule 11: cards = panel, in both themes.
      expect(heading.closest('[data-summary-block]')).toHaveClass('bg-panel-light', 'dark:bg-panel-dark')
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

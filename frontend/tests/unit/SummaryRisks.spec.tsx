import { render, screen } from '@testing-library/react'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'
import type { RiskFactor } from '@/types/summary'
import filing3Risks from '../e2e/fixtures/filing-3-risks.json'

// The evidence rows' wiring (founder option b): each row's h3 is excerptHeadings of the shown spans,
// in order, and its blockquote carries the whole span. The heading rule is pinned in
// riskHeadline.spec.ts and riskTitle.spec.ts; "model labels never reach a heading" in SummaryBlocks.spec.tsx.
// The brand device on the rows (D-044): a row the server located carries a marker on its heading, the
// marker's twin in the margin and its excerpt as a marked block in the filing's face; any other row keeps
// the plain quotation. Where the twins land on the page is real layout: tests/e2e/risk-evidence-rows.spec.ts.

const RISKS: RiskFactor[] = filing3Risks
const SPANS = RISKS.map((risk) => risk.supporting_evidence)
const PROJECTION = { version: 1, verified_count: 4, withheld_count: 0 }
const unlocated = (risk: RiskFactor): RiskFactor => ({ ...risk, source_verified: false })

/** What the device draws on each row, read from the DOM: its marker, whether its excerpt is a marked block. */
const rowsOf = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('li')).map((li) => ({
    markers: Array.from(li.querySelectorAll<HTMLElement>('[data-en-ref]')).map((el) => el.textContent),
    marked: li.querySelector('blockquote')!.classList.contains('en-marked'),
    serif: li.querySelector('blockquote')!.classList.contains('font-editorial'),
  }))
const twinsOf = (container: HTMLElement) => Array.from(container.querySelectorAll('.en-margin-mark')).map((el) => el.textContent)

describe('SummaryRisks rows', () => {
  it('heads each production span with excerptHeadings and its marker, and quotes the span whole, byte for byte', () => {
    const { container } = render(<SummaryRisks risks={RISKS} projection={PROJECTION} />)
    const headings = screen.getAllByRole('heading', { level: 3 })
    // textContent, not the whitespace-normalising text matchers, so the filing's no-break space counts.
    expect(headings.map((h) => h.textContent)).toEqual(excerptHeadings(SPANS).map((heading, i) => `${heading}[${i + 1}]`))
    headings.forEach((heading, i) => {
      expect(heading.closest('li')!.querySelector('blockquote')!.textContent).toBe(SPANS[i])
    })
    expect(twinsOf(container)).toEqual(['[1]', '[2]', '[3]', '[4]'])
  })
})

describe('the device on the risk rows (D-044)', () => {
  it('marks every located row once, numbered in reading order, and leaves a row that is not located plain', () => {
    const mixed = [RISKS[0], unlocated(RISKS[1]), RISKS[2], { ...RISKS[3], source_verified: null }]
    const { container } = render(<SummaryRisks risks={mixed} projection={PROJECTION} />)
    expect(rowsOf(container)).toEqual([
      { markers: ['[1]'], marked: true, serif: true },
      { markers: [], marked: false, serif: false },
      { markers: ['[2]'], marked: true, serif: true },
      { markers: [], marked: false, serif: false },
    ])
    // Each marker's twin, once, in the margin beside the list; the twins are decorative.
    expect(twinsOf(container)).toEqual(['[1]', '[2]'])
    expect(container.querySelector('.en-margin')!.getAttribute('aria-hidden')).toBe('true')
    // The marker sits on its row's heading, hidden from assistive tech like its twin: the heading's name is its
    // words alone, and the chip says what was located.
    const heading = screen.getByRole('heading', { level: 3, name: excerptHeadings(SPANS)[2] })
    expect(heading.querySelector('[data-en-ref]')!.getAttribute('aria-hidden')).toBe('true')
  })

  it('draws no margin and no marked block when no row is located', () => {
    const { container } = render(<SummaryRisks risks={RISKS.map(unlocated)} projection={PROJECTION} />)
    expect(rowsOf(container).every((row) => row.markers.length === 0 && !row.marked && !row.serif)).toBe(true)
    expect(container.querySelector('.en-margin')).toBeNull()
    expect(container.querySelector('[data-en-ref], .en-marked, .font-editorial')).toBeNull()
  })

  it('keeps the lead and the tally outside the margin', () => {
    const { container } = render(<SummaryRisks risks={RISKS} projection={PROJECTION} />)
    const margin = container.querySelector('.en-margin')!.parentElement!
    expect(margin.contains(screen.getByText(/each heading is the start of its excerpt/))).toBe(false)
    expect(margin.contains(screen.getByText(/4 of 4 excerpts located in the filing text/))).toBe(false)
  })
})

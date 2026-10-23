import { describe, expect, it } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import FinancialMetricsTable, { type FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'
import { TAKEAWAY_WITHHELD } from '@/features/filings/lib/evidenceLabels'

// A row whose figure the server replaced with the filed one (provenance_service._swap_in_filed_figures, D-058 Q3): its
// figure panel names the filed amount shown and the summary's figure it replaced, and a takeaway that stated a figure is
// withheld (commentary_withheld: 'figure_replaced'). The summary did write one, so the cell says why it is not shown, in
// the table and in the phone cards, rather than reading as "no takeaway" (chief design on #1530).
const replaced: FinancialMetric = {
  metric: 'Operating income',
  current_period: '$133,050,000,000',
  prior_period: '$123,216M',
  commentary: '',
  commentary_withheld: 'figure_replaced',
  source_verified: true,
  source_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
  source_filed: { current_period: '$133,050 million', prior_period: '$123,216 million' },
  source_replaced: { current_period: '$132,100M' },
}
const unwritten: FinancialMetric = { metric: 'Net income', current_period: '$112.0B', prior_period: '$93.7B', commentary: '' }
// The passage the withheld takeaway cited, as a row stored before the server cleared it would still carry: the cell
// shows no chip for a takeaway it does not show.
const citedPassage = {
  excerpt: 'Operating income was $133.1 billion.',
  section_ref: 'Item 7',
  verified: true,
  fragment_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm#:~:text=Operating%20income',
}

const takeaways = (container: HTMLElement) =>
  [...container.querySelectorAll('[data-metric-field="takeaway"]')].map((field) => field.textContent?.trim())

// Sage never colours a value at rest (DESIGN.md, the Separate Signals Rule; D-030). A figure's note states the filed
// amounts in a string the server's fields fill, which no source scan reads, so the rendered panel is read instead: no
// text with a digit sits inside an element whose own colour is sage (brandCopyRules.spec.ts rule 2's colour family).
const SAGE = /^(?:dark:)?(?:text|fill)-(?:brand(?:-[a-z]+)*|accent-strong)(?:\/\S+)?$/
function digitsInSage(root: HTMLElement): string[] {
  const out: string[] = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!/\d/.test(node.textContent ?? '')) continue
    for (let element = node.parentElement; element && root.contains(element); element = element.parentElement) {
      if ((element.getAttribute('class') ?? '').split(/\s+/).some((name) => SAGE.test(name))) {
        out.push(node.textContent!.trim())
        break
      }
    }
  }
  return out
}

describe('a replaced figure', () => {
  it('names the filed amount shown, the summary’s figure it replaced and the withheld takeaway in its panel', () => {
    render(<FinancialMetricsTable metrics={[replaced]} bare />)
    act(() => screen.getAllByRole('link', { name: 'Source: Matches filing (opens in a new tab)' })[0].focus())
    expect(screen.getByRole('group', { name: 'Source detail' })).toHaveTextContent(
      'Shown as the company filed it: $133,050 million. The summary’s figure, $132,100M, was replaced. ' +
        'Its takeaway was written before the correction, so it is withheld.',
    )
  })
})

describe('the figure panel', () => {
  it.each([
    ['a replaced figure', replaced],
    ['a matched figure', { ...replaced, current_period: '$133.1B', source_replaced: null, commentary_withheld: null }],
  ])('rests the amounts in %s’s note in the ink, its check alone in sage', (_, row) => {
    render(<FinancialMetricsTable metrics={[row]} bare />)
    act(() => screen.getAllByRole('link', { name: 'Source: Matches filing (opens in a new tab)' })[0].focus())
    const panel = screen.getByRole('group', { name: 'Source detail' })
    expect(panel.textContent).toContain('$133,050 million')
    expect(digitsInSage(panel)).toEqual([])
  })

  it('reads a sage digit as one, so the check above can fail', () => {
    const { container } = render(<p><span className="text-xs text-brand-strong dark:text-brand-strong-dark">$133,050 million</span></p>)
    expect(digitsInSage(container)).toEqual(['$133,050 million'])
  })
})

describe('a withheld takeaway', () => {
  it('says it was withheld in both layouts, and a row the summary wrote none for still reads "no takeaway"', () => {
    const { container } = render(<FinancialMetricsTable metrics={[{ ...replaced, commentary_evidence: citedPassage }, unwritten]} bare />)
    const shown = takeaways(container)
    // Each row renders twice: its phone card and its table row (CSS shows one).
    expect(shown.filter((text) => text === TAKEAWAY_WITHHELD)).toHaveLength(2)
    expect(shown.filter((text) => text?.endsWith('no takeaway'))).toHaveLength(2)
    const withheld = [...container.querySelectorAll<HTMLElement>('[data-metric-field="takeaway"]')].filter((field) =>
      field.textContent?.includes(TAKEAWAY_WITHHELD),
    )
    expect(withheld).toHaveLength(2)
    for (const field of withheld) expect(within(field).queryByRole('link')).toBeNull()
  })

  it('shows a takeaway the row still has, whatever the flag says', () => {
    const { container } = render(<FinancialMetricsTable metrics={[{ ...replaced, commentary: 'Services drove the increase.' }]} bare />)
    expect(takeaways(container)).toEqual(['Services drove the increase.', 'Services drove the increase.'])
  })
})

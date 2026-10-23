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

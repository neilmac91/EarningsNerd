import React from 'react'
import { render, screen, within } from '@testing-library/react'
import { WhatChanged } from '@/features/filings/components/WhatChanged'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'

const baseReport: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Quarter over quarter',
  prior_filing: { filing_id: 11, filing_type: '10-Q', filing_date: '2024-02-01', period_end_date: '2023-12-31' },
  metrics: {
    headline: 'Revenue up 25.0%',
    items: [
      { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 25, current: 100, prior: 80, display: '+25.0%', tone: 'gain' },
      { metric: 'net_income', label: 'Net income', direction: 'down', pct: 20, current: 20, prior: 25, display: '−20.0%', tone: 'loss' },
    ],
    data_quality: 'ok',
  },
  reporting_currency: 'USD',
  risks: { new: ['Cybersecurity breach exposure'], resolved: ['Legacy litigation overhang'], carried_count: 7 },
  key_changes: 'Revenue accelerated while margins compressed on higher R&D investment.',
  has_changes: true,
}

describe('WhatChanged (A5)', () => {
  it('renders metric deltas, basis, and a link to the prior filing', () => {
    const { container } = render(<WhatChanged report={baseReport} />)
    expect(container.textContent).toContain('What changed')
    expect(container.textContent).toContain('Quarter over quarter')
    expect(container.textContent).toContain('Revenue')
    expect(container.textContent).toContain('+25.0%')
    expect(container.textContent).toContain('−20.0%')
    const link = screen.getByRole('link', { name: /prior 10-Q/i })
    expect(link.getAttribute('href')).toBe('/filing/11')
  })

  it('renders new vs no-longer-cited risks and the carried-over count', () => {
    const { container } = render(<WhatChanged report={baseReport} />)
    expect(container.textContent).toContain('New risk factors')
    expect(container.textContent).toContain('Cybersecurity breach exposure')
    expect(container.textContent).toContain('No longer cited')
    expect(container.textContent).toContain('Legacy litigation overhang')
    expect(container.textContent).toContain('7 risk factors carried over')
  })

  it('leads with the deterministic delta headline, not the deprecated outlook narrative (T1.6)', () => {
    const { container } = render(<WhatChanged report={baseReport} />)
    const text = container.textContent || ''
    // The lead is the computed metrics.headline; the summary's own outlook prose (key_changes,
    // which duplicated the Outlook section) is no longer surfaced.
    expect(text).toContain('Revenue up 25.0%')
    expect(text).not.toContain('Revenue accelerated while margins compressed')
    // The headline leads — before the metric rows, not as a footer.
    const headlineIndex = text.indexOf('Revenue up 25.0%')
    const netIncomeIndex = text.indexOf('Net income')
    expect(netIncomeIndex).toBeGreaterThan(-1)
    expect(headlineIndex).toBeLessThan(netIncomeIndex)
  })

  it('renders nothing when there are no material changes', () => {
    const empty: ChangeReport = {
      has_prior: false, comparison_basis: 'Year over year', prior_filing: null,
      metrics: null, risks: null, key_changes: null, has_changes: false,
    }
    const { container } = render(<WhatChanged report={empty} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows a partial-data note when metrics are degraded', () => {
    const partial: ChangeReport = {
      ...baseReport,
      metrics: { ...baseReport.metrics!, data_quality: 'partial' },
      risks: null,
      key_changes: null,
    }
    const { container } = render(<WhatChanged report={partial} />)
    expect(container.textContent).toContain('Some figures were withheld')
  })

  // ---- 2026-10 rebuild (docs/design/filings-index-review.md) ----

  it('colours each change from the server tone, never re-derived from direction', () => {
    const debt: ChangeReport = {
      ...baseReport,
      metrics: {
        ...baseReport.metrics!,
        items: [
          // Inverted register: debt fell, so the server sends tone 'gain' with direction 'down'.
          { metric: 'long_term_debt', label: 'Long-term debt', direction: 'down', pct: -9.3, current: 98_959e6, prior: 109_106e6, display: '−9.3%', tone: 'gain' },
          // A rise the server calls a loss.
          { metric: 'current_liabilities', label: 'Current liabilities', direction: 'up', pct: 4, current: 104e6, prior: 100e6, display: '+4.0%', tone: 'loss' },
        ],
      },
    }
    const { container } = render(<WhatChanged report={debt} />)
    // Both presentations (the sm+ table and the phone rows) colour from the same served tone.
    for (const layout of ['table', 'rows']) {
      const scope = within(container.querySelector<HTMLElement>(`[data-change-layout="${layout}"]`)!)
      expect(scope.getByText('−9.3%').className).toContain('text-gain-text')
      expect(scope.getByText('+4.0%').className).toContain('text-loss-text')
    }
  })

  // ---- 2026-10 critique P-07: direction and meaning, never one signal ----

  it('marks the arithmetic direction with a glyph and states the tone in words', () => {
    const debt: ChangeReport = {
      ...baseReport,
      metrics: {
        ...baseReport.metrics!,
        items: [
          { metric: 'long_term_debt', label: 'Total term debt', direction: 'down', pct: -7.3, current: 110.1e9, prior: 118.7e9, display: '−7.3%', tone: 'gain' },
          { metric: 'research_and_development', label: 'R&D', direction: 'up', pct: 19.8, current: 26.3e9, prior: 21.9e9, display: '+19.8%', tone: 'flat' },
        ],
      },
    }
    const { container } = render(<WhatChanged report={debt} />)
    const table = within(container.querySelector<HTMLElement>('[data-change-layout="table"]')!)
    expect(table.getByRole('columnheader', { name: 'Read as' })).toBeInTheDocument()
    const debtRow = table.getByRole('row', { name: /Total term debt/ })
    expect(debtRow).toHaveTextContent('▼−7.3%')
    expect(debtRow).toHaveTextContent('Favorable')
    const rdRow = table.getByRole('row', { name: /R&D/ })
    expect(rdRow).toHaveTextContent('▲+19.8%')
    expect(rdRow).toHaveTextContent('Neutral')
    // The glyph is decorative: the signed string already carries the direction, so no words are added.
    expect(table.getByText('▼')).toHaveAttribute('aria-hidden', 'true')
    expect(debtRow.querySelector('.sr-only')).toBeNull()
  })

  it('speaks the direction wherever no signed string states it: the dash for a zero prior, an unsigned 0.0%', () => {
    const unsigned: ChangeReport = {
      ...baseReport,
      metrics: {
        ...baseReport.metrics!,
        items: [
          // No percentage is meaningful from zero: the server sends the direction and display null.
          { metric: 'net_income', label: 'Net income', direction: 'up', pct: null, current: 5e6, prior: 0, display: null, tone: 'gain' },
          { metric: 'operating_income', label: 'Operating income', direction: 'flat', pct: null, current: 0, prior: 0, display: null, tone: 'flat' },
          // A change that rounds away keeps its direction but loses its sign.
          { metric: 'revenue', label: 'Revenue', direction: 'down', pct: 0.03, current: 99_970, prior: 100_000, display: '0.0%', tone: 'flat' },
        ],
      },
    }
    const { container } = render(<WhatChanged report={unsigned} />)
    const table = within(container.querySelector<HTMLElement>('[data-change-layout="table"]')!)
    const changeCell = (name: RegExp) => within(table.getByRole('row', { name })).getAllByRole('cell')[2]
    const fromZero = changeCell(/Net income/)
    expect(fromZero).toHaveTextContent(/^▲Up —$/)
    expect(within(fromZero).getByText('—')).toHaveAttribute('aria-hidden', 'true')
    expect(within(fromZero).getByText('Up')).toHaveClass('sr-only')
    expect(changeCell(/Operating income/)).toHaveTextContent(/^Unchanged —$/)
    const roundedAway = changeCell(/Revenue/)
    expect(roundedAway).toHaveTextContent(/^▼Down 0\.0%$/)
    expect(within(roundedAway).getByText('Down')).toHaveClass('sr-only')
    // The stacked phone rows render the same Change.
    const rows = within(container.querySelector<HTMLElement>('[data-change-layout="rows"]')!).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent(/^Net income▲Up —/)
    expect(rows[1]).toHaveTextContent(/^Operating incomeUnchanged —/)
    expect(rows[2]).toHaveTextContent(/^Revenue▼Down 0\.0%/)
  })

  it('stacks each metric below sm with prior → current and "Read as" kept', () => {
    const { container } = render(<WhatChanged report={baseReport} />)
    const rows = container.querySelector<HTMLElement>('[data-change-layout="rows"]')!
    expect(rows).toHaveClass('sm:hidden')
    expect(container.querySelector('[data-change-layout="table"]')).toHaveClass('hidden', 'sm:block')
    const items = within(rows).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('Revenue')
    expect(items[0]).toHaveTextContent('Prior $80.0 → , current $100.0')
    expect(items[0]).toHaveTextContent('Favorable')
    expect(items[1]).toHaveTextContent('Unfavorable')
  })

  it('renders bare inside a summary section: no card and no heading of its own', () => {
    const { container } = render(<WhatChanged report={baseReport} bare />)
    expect(container.querySelector('section')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'What changed' })).toBeNull()
    expect(container.textContent).toContain('Quarter over quarter, against the 10-Q for the quarter ended Dec 31, 2023.')
    expect(screen.getByRole('link', { name: /prior 10-Q/i })).toHaveAttribute('href', '/filing/11')
    // The risk subheads sit one level under the section's h2.
    expect(screen.getByRole('heading', { level: 3, name: /New risk factors/ })).toBeInTheDocument()
  })

  it('shows prior and current figures in the data face as a table, with no trend icons', () => {
    const real: ChangeReport = {
      ...baseReport,
      metrics: {
        ...baseReport.metrics!,
        items: [
          { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 7.8, current: 394_328e6, prior: 365_817e6, display: '+7.8%', tone: 'gain' },
          { metric: 'eps_diluted', label: 'Diluted EPS', direction: 'up', pct: 8.9, current: 6.11, prior: 5.61, display: '+8.9%', tone: 'gain' },
        ],
      },
    }
    const { container } = render(<WhatChanged report={real} />)
    for (const header of ['Metric', 'Prior', 'Current', 'Change']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    expect(screen.getByRole('rowheader', { name: 'Revenue' })).toBeInTheDocument()
    expect(screen.getByText('$394.3B').className).toContain('font-data')
    expect(screen.getByText('$365.8B')).toBeInTheDocument()
    expect(screen.getByText('$6.11')).toBeInTheDocument()
    expect(screen.getByText('$5.61')).toBeInTheDocument()
    expect(container.querySelectorAll('table svg')).toHaveLength(0)
  })

  describe('amounts in the filer’s own currency', () => {
    // The items are raw XBRL amounts in the filer's reporting currency; a foreign filer's are not dollars.
    const items: ChangeReport['metrics'] = {
      ...baseReport.metrics!,
      items: [
        { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 21.2, current: 45.1e12, prior: 37.2e12, display: '+21.2%', tone: 'gain' },
        { metric: 'eps_diluted', label: 'Diluted EPS', direction: 'up', pct: 103.9, current: 365.94, prior: 179.47, display: '+103.9%', tone: 'gain' },
      ],
    }

    it('labels them with the reporting currency the report names', () => {
      render(<WhatChanged report={{ ...baseReport, metrics: items, reporting_currency: 'JPY' }} />)
      const table = within(document.querySelector<HTMLElement>('[data-change-layout="table"]')!)
      expect(table.getByRole('row', { name: /Revenue/ })).toHaveTextContent(/¥37\.2T\s*¥45\.1T/)
      expect(table.getByRole('row', { name: /Diluted EPS/ })).toHaveTextContent(/¥179\.47\s*¥365\.94/)
      expect(document.body.textContent).not.toContain('$')
    })

    it('shows them unlabelled, never as dollars, when the currency is unknown', () => {
      for (const reporting_currency of [null, undefined]) {
        const { unmount } = render(<WhatChanged report={{ ...baseReport, metrics: items, reporting_currency }} />)
        const table = within(document.querySelector<HTMLElement>('[data-change-layout="table"]')!)
        expect(table.getByRole('row', { name: /Revenue/ })).toHaveTextContent(/37\.2T\s*45\.1T/)
        expect(table.getByRole('row', { name: /Diluted EPS/ })).toHaveTextContent(/179\.47\s*365\.94/)
        expect(document.body.textContent).not.toMatch(/[$¥]/)
        unmount()
      }
    })
  })

  it('states the comparison as a sentence, never as an uppercase eyebrow', () => {
    const { container } = render(<WhatChanged report={baseReport} />)
    expect(container.textContent).toContain('Quarter over quarter, against the 10-Q for the quarter ended Dec 31, 2023.')
    expect(screen.getByText('Quarter over quarter').className).not.toContain('uppercase')
    expect(screen.getByRole('link', { name: /prior 10-Q/i }).textContent).not.toContain('↗')
  })

  it('nests its subheadings one level below its own heading', () => {
    render(<WhatChanged report={baseReport} headingLevel="h4" />)
    expect(screen.getByRole('heading', { level: 4, name: 'What changed' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 5, name: /New risk factors/ })).toBeInTheDocument()
  })
})

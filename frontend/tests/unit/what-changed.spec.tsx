import React from 'react'
import { render, screen } from '@testing-library/react'
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
    // The headline leads — before the metric chips, not as a footer.
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
})

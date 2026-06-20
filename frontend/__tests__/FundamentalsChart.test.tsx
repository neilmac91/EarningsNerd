import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import FundamentalsChart from '@/components/FundamentalsChart'
import type { FundamentalsData } from '@/features/companies/api/companies-api'

const point = (over: Partial<FundamentalsData['concepts'][0]['points'][0]>) => ({
  period_end: '2024-09-28',
  fiscal_year: 2024,
  fiscal_period: 'FY',
  value: 0,
  unit: 'USD',
  form: '10-K',
  accession: '0000320193-24-000123',
  ...over,
})

const data: FundamentalsData = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  concepts: [
    {
      concept: 'revenue',
      unit: 'USD',
      points: [
        point({ period_end: '2023-09-30', fiscal_year: 2023, value: 383285000000, accession: 'a23' }),
        point({ period_end: '2024-09-28', fiscal_year: 2024, value: 391035000000, accession: 'a24' }),
      ],
    },
    {
      concept: 'net_margin',
      unit: 'pure',
      points: [point({ value: 24.3 })],
    },
  ],
}

describe('FundamentalsChart', () => {
  it('renders the heading, a metric pill per concept, and the latest USD value (compact)', () => {
    render(<FundamentalsChart data={data} />)
    expect(screen.getByRole('heading', { name: 'Fundamentals' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Revenue' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Net Margin' })).toBeInTheDocument()
    // Defaults to revenue; latest period is FY2024 = $391.0B.
    expect(screen.getByText(/\$391\.0B/)).toBeInTheDocument()
    expect(screen.getByText(/FY2024/)).toBeInTheDocument()
  })

  it('switches metric and formats "pure" units as a percentage', async () => {
    const user = userEvent.setup()
    render(<FundamentalsChart data={data} />)
    await user.click(screen.getByRole('button', { name: 'Net Margin' }))
    expect(screen.getByText(/24\.3%/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Net Margin' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('renders nothing when no concept has points (facts not backfilled yet)', () => {
    const { container } = render(
      <FundamentalsChart data={{ ticker: 'X', company_name: 'X', concepts: [] }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})

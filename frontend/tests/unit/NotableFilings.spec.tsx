import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import NotableFilings from '@/features/filings/components/NotableFilings'
import type { NotableFilingsResponse } from '@/lib/serverApi'

vi.mock('next/link', () => ({
  default: ({ children, href, onClick, ...props }: { children: React.ReactNode; href: string; onClick?: () => void; [key: string]: unknown }) => (
    <a href={href} onClick={onClick} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/components/CompanyLogo', () => ({
  default: ({ ticker }: { ticker: string }) => <div data-testid={`logo-${ticker}`} />,
}))

const mockAnalytics = vi.hoisted(() => ({
  notableFilingClicked: vi.fn(),
  homepageSectionViewed: vi.fn(),
}))
vi.mock('@/lib/analytics', () => ({ default: mockAnalytics, analytics: mockAnalytics }))

const RESPONSE: NotableFilingsResponse = {
  filings: [
    {
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      form: '8-K',
      reason: 'earnings_results',
      reason_label: 'Earnings results',
      filed_date: '2026-07-05',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/x/',
    },
    {
      ticker: 'CRSP',
      company_name: 'CRISPR Therapeutics AG',
      form: 'SC 13D',
      reason: 'activist_stake',
      reason_label: 'Activist stake',
      filed_date: '2026-07-03',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/1/y/',
    },
  ],
  status: 'ok',
  timestamp: '2026-07-06T00:00:00+00:00',
}

describe('NotableFilings', () => {
  beforeEach(() => {
    mockAnalytics.notableFilingClicked.mockClear()
  })

  it('self-omits entirely on null data', () => {
    const { container } = render(<NotableFilings data={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('self-omits entirely on an empty list', () => {
    const { container } = render(
      <NotableFilings data={{ filings: [], status: 'empty', timestamp: 't' }} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders one card per filing, linking to the COMPANY page', () => {
    render(<NotableFilings data={RESPONSE} />)

    expect(screen.getByText('Notable filings')).toBeInTheDocument()
    expect(screen.getByTestId('notable-filing-AAPL')).toHaveAttribute('href', '/company/AAPL')
    expect(screen.getByTestId('notable-filing-CRSP')).toHaveAttribute('href', '/company/CRSP')
  })

  it('shows the honest reason chip and a relative filed date', () => {
    render(<NotableFilings data={RESPONSE} />)

    expect(screen.getByText('Earnings results')).toBeInTheDocument()
    expect(screen.getByText('Activist stake')).toBeInTheDocument()
    // "8-K • Filed X ago" — relative label is time-dependent, assert shape not value.
    expect(screen.getByTestId('notable-filing-AAPL').textContent).toMatch(/8-K • Filed .* ago/)
  })

  it('fires notable_filing_clicked with ticker/form/reason on click', () => {
    render(<NotableFilings data={RESPONSE} />)

    fireEvent.click(screen.getByTestId('notable-filing-AAPL'))
    expect(mockAnalytics.notableFilingClicked).toHaveBeenCalledWith({
      ticker: 'AAPL',
      form: '8-K',
      reason: 'earnings_results',
    })
    expect(mockAnalytics.notableFilingClicked).toHaveBeenCalledTimes(1)
  })
})

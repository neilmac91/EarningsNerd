import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import QuickAccessBar, { TOP_COMPANIES } from '@/components/QuickAccessBar'

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href, onClick, ...props }: { children: React.ReactNode; href: string; onClick?: () => void; [key: string]: unknown }) => (
    <a href={href} onClick={onClick} {...props}>
      {children}
    </a>
  ),
}))

// Mock PostHog
const mockCapture = vi.fn()
vi.mock('posthog-js', () => ({
  default: {
    capture: (event: string, properties: Record<string, unknown>) => mockCapture(event, properties),
  },
}))

describe('QuickAccessBar', () => {
  beforeEach(() => {
    mockCapture.mockClear()
  })

  it('renders all 8 companies', () => {
    render(<QuickAccessBar />)

    TOP_COMPANIES.forEach(({ ticker }) => {
      expect(screen.getByTestId(`quick-access-${ticker}`)).toBeInTheDocument()
    })
  })

  it('displays correct tickers', () => {
    render(<QuickAccessBar />)

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('NVDA')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
    expect(screen.getByText('META')).toBeInTheDocument()
    expect(screen.getByText('GOOGL')).toBeInTheDocument()
    expect(screen.getByText('AMZN')).toBeInTheDocument()
    expect(screen.getByText('BABA')).toBeInTheDocument()
  })

  it('links to correct company pages', () => {
    render(<QuickAccessBar />)

    const appleLink = screen.getByTestId('quick-access-AAPL')
    expect(appleLink).toHaveAttribute('href', '/company/AAPL')

    const babaLink = screen.getByTestId('quick-access-BABA')
    expect(babaLink).toHaveAttribute('href', '/company/BABA')
  })

  it('tracks clicks with PostHog analytics', () => {
    render(<QuickAccessBar />)

    const nvidiaLink = screen.getByTestId('quick-access-NVDA')
    fireEvent.click(nvidiaLink)

    expect(mockCapture).toHaveBeenCalledWith('quick_access_click', { ticker: 'NVDA' })
  })

  it('tracks different tickers correctly', () => {
    render(<QuickAccessBar />)

    fireEvent.click(screen.getByTestId('quick-access-AAPL'))
    expect(mockCapture).toHaveBeenCalledWith('quick_access_click', { ticker: 'AAPL' })

    fireEvent.click(screen.getByTestId('quick-access-BABA'))
    expect(mockCapture).toHaveBeenCalledWith('quick_access_click', { ticker: 'BABA' })

    expect(mockCapture).toHaveBeenCalledTimes(2)
  })

  it('renders section with accessible label', () => {
    render(<QuickAccessBar />)

    const section = screen.getByRole('region', { name: /popular companies/i })
    expect(section).toBeInTheDocument()
  })

  it('displays helper text', () => {
    render(<QuickAccessBar />)

    expect(screen.getByText('Popular companies — click to explore')).toBeInTheDocument()
  })

  it('includes BABA (Alibaba) not AMD', () => {
    render(<QuickAccessBar />)

    expect(screen.getByText('BABA')).toBeInTheDocument()
    expect(screen.getByText('Alibaba')).toBeInTheDocument()
    expect(screen.queryByText('AMD')).not.toBeInTheDocument()
  })
})

describe('TOP_COMPANIES constant', () => {
  it('contains exactly 8 companies', () => {
    expect(TOP_COMPANIES).toHaveLength(8)
  })

  it('has correct structure for each company', () => {
    TOP_COMPANIES.forEach((company) => {
      expect(company).toHaveProperty('ticker')
      expect(company).toHaveProperty('name')
      expect(typeof company.ticker).toBe('string')
      expect(typeof company.name).toBe('string')
    })
  })

  it('includes Alibaba (BABA)', () => {
    const baba = TOP_COMPANIES.find((c) => c.ticker === 'BABA')
    expect(baba).toBeDefined()
    expect(baba?.name).toBe('Alibaba')
  })
})

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

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

/**
 * The landing's Notable filings row (D-045) as the backend serves it under D-046's rule (F3, E90): 10-K and 10-Q
 * filings only, newest first, one per company. The companies are samples, not real filings. The backend's query holds
 * the rule (backend/tests/unit/test_notable_filings_service.py); this holds the row to rendering what it is served
 * and nothing else, and the mount gate (landing-sections-mounted.spec.ts) holds its place on the page.
 */
const RESPONSE: NotableFilingsResponse = {
  filings: [
    {
      ticker: 'SMPA',
      company_name: 'Sample Industries A Inc.',
      form: '10-Q',
      reason: 'quarterly_report',
      reason_label: 'Quarterly report',
      filed_date: '2026-07-05',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/1/a/',
    },
    {
      ticker: 'SMPB',
      company_name: 'Sample Holdings B Corp.',
      form: '10-K',
      reason: 'annual_report',
      reason_label: 'Annual report',
      filed_date: '2026-07-03',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/2/b/',
    },
    {
      ticker: 'SMPC',
      company_name: 'Sample Partners C Ltd.',
      form: '10-Q',
      reason: 'quarterly_report',
      reason_label: 'Quarterly report',
      filed_date: '2026-07-01',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/3/c/',
    },
  ],
  status: 'ok',
  timestamp: '2026-07-06T00:00:00+00:00',
}

describe('NotableFilings', () => {
  beforeEach(() => {
    mockAnalytics.notableFilingClicked.mockClear()
  })

  it('self-omits entirely on null data (a failed read)', () => {
    const { container } = render(<NotableFilings data={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('self-omits entirely on an empty list (the backend omits a week with fewer than three companies)', () => {
    const { container } = render(
      <NotableFilings data={{ filings: [], status: 'empty', timestamp: '2026-07-06T00:00:00+00:00' }} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('is a ruled row named Notable filings, its line saying what the feed is', () => {
    render(<NotableFilings data={RESPONSE} />)
    const row = screen.getByRole('region', { name: 'Notable filings' })
    expect(row).toHaveAttribute('data-landing-row')
    expect(row.id).toBe('notable-filings')
    const heading = within(row).getByRole('heading', { level: 2, name: 'Notable filings' })
    // The label column: the number, the title, then the one line.
    expect([...heading.parentElement!.children].map((child) => child.tagName)).toEqual(['SPAN', 'H2', 'P'])
    expect(heading.parentElement!.lastElementChild).toHaveTextContent(
      /^The past week’s 10-K and 10-Q filings from companies with a summary to read, newest first\.$/,
    )
  })

  it('renders the served cards and only those, in the served order, each opening its company page', () => {
    render(<NotableFilings data={RESPONSE} />)
    const row = screen.getByRole('region', { name: 'Notable filings' })
    const links = within(row).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/company/SMPA', '/company/SMPB', '/company/SMPC'])
    expect(links.map((link) => link.getAttribute('data-testid'))).toEqual([
      'notable-filing-SMPA',
      'notable-filing-SMPB',
      'notable-filing-SMPC',
    ])
  })

  it('lays the cards out two across from 40rem at the reader’s text size, over a one-column base', () => {
    render(<NotableFilings data={RESPONSE} />)
    const list = within(screen.getByRole('region', { name: 'Notable filings' })).getByRole('list')
    expect(list).toHaveClass('grid', 'grid-cols-1', '[@media(min-width:40rem)]:grid-cols-2')
    expect(within(list).getAllByRole('listitem')).toHaveLength(RESPONSE.filings.length)
  })

  it('shows the reason chip and a relative filed date', () => {
    render(<NotableFilings data={RESPONSE} />)

    expect(within(screen.getByTestId('notable-filing-SMPA')).getByText('Quarterly report')).toBeInTheDocument()
    expect(within(screen.getByTestId('notable-filing-SMPB')).getByText('Annual report')).toBeInTheDocument()
    // The chip's label may wrap (a phone at 200% text), so it takes the 16px step over Badge's full radius: a pill on
    // one line, a rounded box once it wraps (DESIGN.md, Shapes).
    expect(within(screen.getByTestId('notable-filing-SMPA')).getByText('Quarterly report')).toHaveClass('!whitespace-normal', '!rounded-xl')
    // "10-Q · Filed X ago": the relative label is time-dependent, so assert its shape, not its value. The middot is the
    // search rows' separator: a no-break space keeps it to the form code, so where the line wraps (a phone at 200% text)
    // the dot stays on the code's line and no line starts with it, and assistive tech hears a comma in its place.
    const card = screen.getByTestId('notable-filing-SMPA')
    expect(card.textContent).toMatch(/10-Q\u00a0·, Filed .* ago/)
    expect(within(card).getByText('·')).toHaveAttribute('aria-hidden', 'true')
    expect(within(card).getByText(',')).toHaveClass('sr-only')
  })

  it('sets the ticker in the data face, and the form code as data-face text in one unbroken run, never an eyebrow chip', () => {
    render(<NotableFilings data={RESPONSE} />)
    expect(within(screen.getByTestId('notable-filing-SMPB')).getByText('SMPB')).toHaveClass('font-data')
    const form = within(screen.getByTestId('notable-filing-SMPB')).getByText('10-K')
    expect(form).toHaveClass('font-data', 'whitespace-nowrap', 'text-text-primary-light', 'dark:text-text-primary-dark')
    expect(form.className).not.toMatch(/\b(uppercase|tracking-eyebrow)\b/)
    expect(form.parentElement?.className).not.toMatch(/\b(uppercase|tracking-eyebrow)\b/)
  })

  it('fires notable_filing_clicked with ticker/form/reason on click', () => {
    render(<NotableFilings data={RESPONSE} />)

    fireEvent.click(screen.getByTestId('notable-filing-SMPB'))
    expect(mockAnalytics.notableFilingClicked).toHaveBeenCalledWith({
      ticker: 'SMPB',
      form: '10-K',
      reason: 'annual_report',
    })
    expect(mockAnalytics.notableFilingClicked).toHaveBeenCalledTimes(1)
  })

  it('anchors the filed-ago label to the response timestamp, not the viewer clock', () => {
    // NotableFilingCard is a client component server-rendered into an ISR page. Before this was
    // anchored, the label came from the live clock, so HTML generated just before a UTC date
    // boundary and hydrated just after it rendered two different strings: a hydration mismatch
    // and a visible text swap. Same payload, two clocks either side of the boundary, one label.
    vi.useFakeTimers()
    try {
      vi.setSystemTime(new Date('2026-07-06T23:50:00Z'))
      const first = render(<NotableFilings data={RESPONSE} />)
      const generated = screen.getByTestId('notable-filing-SMPA').textContent
      expect(generated).toContain('12 hours ago')
      first.unmount()

      vi.setSystemTime(new Date('2026-07-09T00:10:00Z'))
      render(<NotableFilings data={RESPONSE} />)
      expect(screen.getByTestId('notable-filing-SMPA').textContent).toBe(generated)
    } finally {
      vi.useRealTimers()
    }
  })
})

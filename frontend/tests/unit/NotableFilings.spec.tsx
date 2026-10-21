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

  it('shows the reason chip and the filed date', () => {
    render(<NotableFilings data={RESPONSE} />)

    expect(within(screen.getByTestId('notable-filing-SMPA')).getByText('Quarterly report')).toBeInTheDocument()
    expect(within(screen.getByTestId('notable-filing-SMPB')).getByText('Annual report')).toBeInTheDocument()
    // The chip's label may wrap (a phone at 200% text), so it takes the 16px step over Badge's full radius: a pill on
    // one line, a rounded box once it wraps (DESIGN.md, Shapes).
    expect(within(screen.getByTestId('notable-filing-SMPA')).getByText('Quarterly report')).toHaveClass('!whitespace-normal', '!rounded-xl')
    // "10-Q · filed Jul 5, 2026", in the Filing identity line's words (the date cases below). The middot is the search
    // rows' separator: a no-break space keeps it to the form code, so where the line wraps (a phone at 200% text) the dot
    // stays on the code's line and no line starts with it, and assistive tech hears a comma in its place.
    const card = screen.getByTestId('notable-filing-SMPA')
    expect(card.textContent).toMatch(/10-Q\u00a0·, filed Jul 5, 2026/)
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

  /** The card's text for one filing dated `filed_date`. */
  const cardText = (filed_date: string): string => {
    const { unmount } = render(
      <NotableFilings data={{ ...RESPONSE, filings: [{ ...RESPONSE.filings[0], filed_date }] }} />,
    )
    const text = screen.getByTestId('notable-filing-SMPA').textContent ?? ''
    unmount()
    return text
  }

  it('states each filed date as the Filing identity line does, "filed Jul 5, 2026", with no time of day and no relative word', () => {
    // filed_date is an EDGAR day with no time, so the card states the day, in the words and the helper of the Filing
    // identity line (formatLocalDate, 'MMM d, yyyy'), and never an hour or a count from now.
    const row = render(<NotableFilings data={RESPONSE} />)
    const served: Array<[string, string]> = [
      ['SMPA', 'filed Jul 5, 2026'],
      ['SMPB', 'filed Jul 3, 2026'],
      ['SMPC', 'filed Jul 1, 2026'],
    ]
    for (const [ticker, filed] of served) {
      const text = screen.getByTestId(`notable-filing-${ticker}`).textContent ?? ''
      expect(text).toContain(filed)
      expect(text).not.toMatch(/\b(today|yesterday|tomorrow|ago)\b/i)
      expect(text).not.toMatch(/\bin \d/)
      expect(text).not.toMatch(/\d{1,2}:\d{2}|\b(am|pm|hours?|minutes?|seconds?)\b/i)
    }
    row.unmount()
    // A two-digit day, and a year's first day.
    expect(cardText('2026-06-29')).toContain('filed Jun 29, 2026')
    expect(cardText('2027-01-01')).toContain('filed Jan 1, 2027')
  })

  it('keeps the filed day for a reader west or east of UTC: a date-only value is a calendar day, not an instant', () => {
    // vitest's forks pool, this config's default, re-reads TZ when it is assigned (as filing-date-local-day.spec.tsx and
    // TrialBanner.spec.tsx rely on). Each zone's control proves the pin applied, so the case cannot pass in UTC by
    // accident, and shows the shift the helper avoids there.
    try {
      vi.stubEnv('TZ', 'America/Los_Angeles')
      expect(new Date(2026, 6, 5).getTimezoneOffset()).toBe(420)
      expect(new Date('2026-07-05').getDate()).toBe(4) // the day read as a UTC instant, a day early in Los Angeles
      expect(cardText('2026-07-05')).toContain('filed Jul 5, 2026')

      vi.stubEnv('TZ', 'Asia/Tokyo')
      expect(new Date(2026, 6, 5).getTimezoneOffset()).toBe(-540)
      expect(new Date(2026, 6, 5).toISOString().slice(0, 10)).toBe('2026-07-04') // Tokyo's midnight, read back in UTC
      expect(cardText('2026-07-05')).toContain('filed Jul 5, 2026')
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('states the same date whatever the viewer clock, so the server render and hydration agree', () => {
    // NotableFilingCard is a client component server-rendered into an ISR page. A label read from the live clock
    // rendered one string on the server and another in the browser either side of a date boundary: a hydration
    // mismatch and a visible text swap. The filed date reads no clock. Same payload, two clocks either side of the
    // boundary, one label.
    vi.useFakeTimers()
    try {
      vi.setSystemTime(new Date('2026-07-06T23:50:00Z'))
      const first = render(<NotableFilings data={RESPONSE} />)
      const generated = screen.getByTestId('notable-filing-SMPA').textContent
      expect(generated).toContain('filed Jul 5, 2026')
      first.unmount()

      vi.setSystemTime(new Date('2026-07-09T00:10:00Z'))
      render(<NotableFilings data={RESPONSE} />)
      expect(screen.getByTestId('notable-filing-SMPA').textContent).toBe(generated)
    } finally {
      vi.useRealTimers()
    }
  })
})

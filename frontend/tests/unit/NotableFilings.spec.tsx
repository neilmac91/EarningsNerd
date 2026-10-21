import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

import ReportingThisWeek from '@/features/calendar/components/ReportingThisWeek'
import NotableFilings from '@/features/filings/components/NotableFilings'
import type { NotableFilingsResponse, ReportingThisWeekResponse } from '@/lib/serverApi'

vi.mock('next/link', () => ({
  default: ({ children, href, onClick, ...props }: { children: React.ReactNode; href: string; onClick?: () => void; [key: string]: unknown }) => (
    <a href={href} onClick={onClick} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/components/CompanyLogo', () => ({
  default: ({ ticker, name, size }: { ticker: string; name?: string; size?: number }) => (
    <div data-testid={`logo-${ticker}`} data-name={name} data-size={size} />
  ),
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

  it('renders the served lines and only those, in the served order, each opening its company page', () => {
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

  it('lays the lines out two across from 40rem at the reader’s text size, over a one-column base', () => {
    render(<NotableFilings data={RESPONSE} />)
    const list = within(screen.getByRole('region', { name: 'Notable filings' })).getByRole('list')
    expect(list).toHaveClass('grid', 'grid-cols-1', '[@media(min-width:40rem)]:grid-cols-2')
    expect(within(list).getAllByRole('listitem')).toHaveLength(RESPONSE.filings.length)
  })

  it('states the filed date after the form code, the middot held to the code', () => {
    render(<NotableFilings data={RESPONSE} />)
    // "10-Q · filed Jul 5, 2026", in the Filing identity line's words (the date cases below). The middot is the search
    // rows' separator: a no-break space keeps it to the form code, so where the line wraps (a phone at 200% text) the dot
    // stays on the code's line and no line starts with it, and assistive tech hears a comma in its place.
    const line = screen.getByTestId('notable-filing-SMPA')
    expect(line.textContent).toMatch(/10-Q\u00a0·, filed Jul 5, 2026/)
    expect(within(line).getByText('·')).toHaveAttribute('aria-hidden', 'true')
    expect(within(line).getByText(',')).toHaveClass('sr-only')
  })

  it('prints no reason chip: the form code stands alone, as on the Filing identity line and the search option', () => {
    // Under D-046 the chip could only say "Annual report" beside a 10-K or "Quarterly report" beside a 10-Q, the codes
    // the row's line already names (chief design's review of #1461). The payload and the analytics event keep the reason.
    render(<NotableFilings data={RESPONSE} />)
    for (const filing of RESPONSE.filings) {
      expect(screen.getByTestId(`notable-filing-${filing.ticker}`)).not.toHaveTextContent(filing.reason_label)
    }
  })

  it('prints a served name in capitals as the other rows do, through formatCompanyName, on the line and for the mark', () => {
    // EDGAR's display name often arrives in capitals; Reporting this week, the Filing identity line and the company page
    // print names through formatCompanyName, so this line does too (a sample company, never a real one).
    render(<NotableFilings data={{ ...RESPONSE, filings: [{ ...RESPONSE.filings[0], company_name: 'SAMPLE INDUSTRIES A INC' }] }} />)
    const line = screen.getByTestId('notable-filing-SMPA')
    expect(line).toHaveTextContent('Sample Industries A Inc')
    expect(line.textContent).not.toContain('SAMPLE INDUSTRIES')
    expect(within(line).getByTestId('logo-SMPA')).toHaveAttribute('data-name', 'Sample Industries A Inc')
  })

  it('holds "Jul 5," as one run and moves the date under the code whole before it breaks', () => {
    // As the hero's identity line holds its date (HeroExample.tsx): "filed" stays on the code's line, the date is one
    // inline block that moves beneath it whole, and inside it only the year may drop, so no line reads "filed Jul" over
    // "5, 2026".
    render(<NotableFilings data={RESPONSE} />)
    const run = within(screen.getByTestId('notable-filing-SMPA')).getByText('Jul 5,')
    expect(run).toHaveClass('whitespace-nowrap')
    const date = run.parentElement!
    expect(date).toHaveClass('inline-block')
    expect(date).toHaveTextContent(/^Jul 5, 2026$/)
    expect(date.parentElement!.textContent).toMatch(/filed Jul 5, 2026$/)
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

  /** The line's text for one filing dated `filed_date`. */
  const lineText = (filed_date: string): string => {
    const { unmount } = render(
      <NotableFilings data={{ ...RESPONSE, filings: [{ ...RESPONSE.filings[0], filed_date }] }} />,
    )
    const text = screen.getByTestId('notable-filing-SMPA').textContent ?? ''
    unmount()
    return text
  }

  it('states each filed date as the Filing identity line does, "filed Jul 5, 2026", with no time of day and no relative word', () => {
    // filed_date is an EDGAR day with no time, so the line states the day, in the words and the helper of the Filing
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
    expect(lineText('2026-06-29')).toContain('filed Jun 29, 2026')
    expect(lineText('2027-01-01')).toContain('filed Jan 1, 2027')
  })

  it('keeps the filed day for a reader west or east of UTC: a date-only value is a calendar day, not an instant', () => {
    // vitest's forks pool, this config's default, re-reads TZ when it is assigned (as filing-date-local-day.spec.tsx and
    // TrialBanner.spec.tsx rely on). Each zone's control proves the pin applied, so the case cannot pass in UTC by
    // accident, and shows the shift the helper avoids there.
    try {
      vi.stubEnv('TZ', 'America/Los_Angeles')
      expect(new Date(2026, 6, 5).getTimezoneOffset()).toBe(420)
      expect(new Date('2026-07-05').getDate()).toBe(4) // the day read as a UTC instant, a day early in Los Angeles
      expect(lineText('2026-07-05')).toContain('filed Jul 5, 2026')

      vi.stubEnv('TZ', 'Asia/Tokyo')
      expect(new Date(2026, 6, 5).getTimezoneOffset()).toBe(-540)
      expect(new Date(2026, 6, 5).toISOString().slice(0, 10)).toBe('2026-07-04') // Tokyo's midnight, read back in UTC
      expect(lineText('2026-07-05')).toContain('filed Jul 5, 2026')
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('states the same date whatever the viewer clock, so the server render and hydration agree', () => {
    // NotableFilingLine is a client component server-rendered into an ISR page. A label read from the live clock
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

describe('the Notable filings line keeps Reporting this week’s line anatomy', () => {
  // The two rows sit one above the other, both list companies and both open the company page, so they share one line
  // (chief design's review of #1461). Their classes are written in each file; this fails when the two drift.
  const REPORTING: ReportingThisWeekResponse = {
    companies: [{ ticker: 'SMPR', name: 'SAMPLE RETAIL R INC', earnings_date: '2026-07-07', time: 'amc' }],
    week_start: '2026-07-06',
    week_end: '2026-07-10',
    status: 'ok',
    timestamp: '2026-07-06T00:00:00+00:00',
  }

  /** One line of a row, read from the rendered DOM: its list and item (the hairlines), the link (its padding, hover and
   *  ring), the mark's size, the text column, the top line, the ticker, the slot beside it and the name. */
  const anatomy = (link: HTMLElement) => {
    const item = link.closest('li')!
    const column = link.children[1] as HTMLElement
    const top = column.children[0] as HTMLElement
    return {
      list: item.parentElement!.className,
      item: item.className,
      link: link.className,
      markSize: link.children[0].getAttribute('data-size'),
      column: column.className,
      top: top.className,
      ticker: top.children[0].className,
      slot: top.children[1].className,
      name: column.children[1].className,
    }
  }

  it('matches it line for line: the hairlines, the link’s padding, hover and ring, the mark at 32, the ticker’s face and size, the slot and the name’s truncation', () => {
    render(
      <>
        <ReportingThisWeek data={REPORTING} />
        <NotableFilings data={RESPONSE} />
      </>,
    )
    const reporting = anatomy(screen.getByTestId('reporting-this-week-SMPR'))
    const notable = anatomy(screen.getByTestId('notable-filing-SMPA'))
    expect(notable).toEqual(reporting)
    // And the shared anatomy is the hairline line's, so a lifted card cannot pass by turning up in both rows.
    expect(notable.markSize).toBe('32')
    expect(notable.item).toContain('border-b')
    expect(notable.list).toContain('border-t')
    expect(notable.link).not.toMatch(/shadow-e[0-9]|bg-panel|border-border|translate-y/)
    expect(notable.name).toContain('truncate')
  })
})

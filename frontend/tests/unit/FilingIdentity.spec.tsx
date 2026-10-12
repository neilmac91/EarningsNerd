// A zone behind UTC, where a UTC-midnight instant rendered through new Date() shows the day before
// (the filing-date-local-day.spec.tsx precedent; vitest isolates each file, so the pin is local).
process.env.TZ = 'America/New_York'

import { render, screen, within } from '@testing-library/react'
import { FilingIdentity, filingCrumb } from '@/features/filings/components/FilingIdentity'
import { VerificationTallyLine } from '@/features/summaries/components/VerificationTallyLine'
import { verificationTally } from '@/features/summaries/lib/verificationTally'
import type { Filing } from '@/features/filings/api/filings-api'
import type { Summary } from '@/features/summaries/api/summaries-api'

// The filing identity strip (2026-10 critique P-04) and the verification tally under it.
const filing: Filing = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2022-10-28T00:00:00+00:00',
  report_date: '2022-09-24T00:00:00+00:00',
  accession_number: '0000320193-22-000108',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/aapl-20220924.htm',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.', exchange: 'Nasdaq' },
}

describe('FilingIdentity', () => {
  it('states company, form, period, filed date, exchange and the original in one strip', () => {
    const { container } = render(<FilingIdentity filing={filing} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toHaveClass('font-data')
    // UTC-midnight instants render their own calendar day (formatLocalDate), in any viewer TZ.
    expect(new Date(filing.report_date!).getDate()).toBe(23) // control: the bug is observable here
    const facts = screen.getByText('fiscal year ended Sep 24, 2022').parentElement!
    expect(facts).toHaveClass('font-data')
    expect(facts).toHaveTextContent('10-K·,fiscal year ended Sep 24, 2022·,filed Oct 28, 2022·,Nasdaq·,Original on SEC EDGAR')
    expect(screen.getByRole('link', { name: /Original on SEC EDGAR/ })).toHaveAttribute('href', filing.document_url)
    // The form is weight in the data face, never a Badge, and there is no decorative AI chip.
    expect(screen.getByText('10-K')).toHaveClass('font-semibold')
    expect(container.textContent).not.toMatch(/AI analysis/i)
  })

  it('names the period by the form: a quarter for a 10-Q', () => {
    render(<FilingIdentity filing={{ ...filing, filing_type: '10-Q', report_date: '2022-06-25T00:00:00+00:00' }} />)
    expect(screen.getByText('quarter ended Jun 25, 2022')).toBeInTheDocument()
  })

  it('names an 8-K’s report date as its event date, never a period end, and crumbs it by its filed date', () => {
    const eightK = { ...filing, filing_type: '8-K', report_date: '2022-10-27T00:00:00+00:00' }
    render(<FilingIdentity filing={eightK} />)
    expect(screen.getByText('event date Oct 27, 2022')).toBeInTheDocument()
    expect(screen.queryByText(/ended/)).toBeNull()
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(crumbs).getByText('8-K · filed Oct 28, 2022')).toHaveAttribute('aria-current', 'page')
  })

  it('leaves the period out when the filing has no period of report', () => {
    render(<FilingIdentity filing={{ ...filing, report_date: undefined }} />)
    expect(screen.queryByText(/ended/)).toBeNull()
    expect(screen.getByText('filed Oct 28, 2022')).toBeInTheDocument()
  })

  it('leads with a breadcrumb back to the company, the filing as the current crumb', () => {
    render(<FilingIdentity filing={filing} />)
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(crumbs).getByRole('link', { name: 'Apple Inc.' })).toHaveAttribute('href', '/company/AAPL')
    expect(within(crumbs).getByText('10-K · Sep 24, 2022')).toHaveAttribute('aria-current', 'page')
    expect(filingCrumb({ filing_type: '8-K', report_date: undefined, filing_date: '2022-10-27' })).toBe('8-K · filed Oct 27, 2022')
  })

  it('shows the Superseded marker only when it is true', () => {
    const { rerender } = render(<FilingIdentity filing={filing} />)
    expect(screen.queryByText('Superseded')).toBeNull()
    rerender(<FilingIdentity filing={{ ...filing, superseded_by_accession: '0000320193-23-000001' }} />)
    expect(screen.getByText('Superseded')).toBeInTheDocument()
  })
})

const summaryWith = (rows: { source_verified?: boolean; source_checkable?: boolean }[], projection?: Record<string, number>) =>
  ({
    id: 1,
    filing_id: 3,
    rendered_sections: [
      {
        id: 'financial-highlights',
        title: 'Financial highlights',
        blocks: [
          {
            kind: 'metrics',
            metric_rows: rows.map((r, i) => ({ metric: `m${i}`, current_period: '$1B', prior_period: '', ...r })),
          },
        ],
      },
    ],
    raw_summary: projection
      ? { risk_source_context_version: 1, sections: { _risk_source_projection: { version: 1, ...projection } } }
      : null,
  }) as unknown as Summary

describe('verificationTally', () => {
  it('counts XBRL-matched figures and the located excerpts the server projected', () => {
    const checked = { source_checkable: true }
    expect(
      verificationTally(
        summaryWith(
          [{ ...checked, source_verified: true }, { ...checked, source_verified: true }, { ...checked, source_verified: false }],
          { verified_count: 3, withheld_count: 1, candidate_count: 4 },
        ),
      ),
    ).toEqual({ figures: { matched: 2, total: 3 }, excerpts: { located: 3, total: 4, withheld: 1 } })
  })

  it('counts only the figures the server could check: EPS, margins and segment lines are never misses', () => {
    const rows = [
      { source_checkable: true, source_verified: true }, // revenue
      { source_checkable: false, source_verified: false }, // diluted EPS
      { source_checkable: false, source_verified: false }, // a segment line
    ]
    expect(verificationTally(summaryWith(rows))?.figures).toEqual({ matched: 1, total: 1 })
    // A payload from before the flag gives no figures count rather than a wrong denominator.
    expect(verificationTally(summaryWith([{ source_verified: true }, {}]))).toBeNull()
  })

  it('is null for a summary with nothing to count, so no zero tally renders', () => {
    expect(verificationTally(summaryWith([]))).toBeNull()
    expect(verificationTally(null)).toBeNull()
  })

  it('renders scoped words, with the check glyph only when nothing was left unmatched', () => {
    const { container, rerender } = render(
      <VerificationTallyLine tally={{ figures: { matched: 6, total: 6 }, excerpts: { located: 3, total: 4, withheld: 1 } }} />,
    )
    expect(container).toHaveTextContent(
      '6 of 6 checkable figures matched the company’s XBRL · , 3 of 4 risk excerpts located in the filing text · , 1 withheld',
    )
    expect(container.querySelector('svg')!.getAttribute('class')).not.toContain('text-brand-strong')
    rerender(<VerificationTallyLine tally={{ figures: { matched: 6, total: 6 }, excerpts: null }} />)
    expect(container).toHaveTextContent('6 of 6 checkable figures matched the company’s XBRL')
    expect(container.querySelector('svg')!.getAttribute('class')).toContain('text-brand-strong')
    expect(container.textContent).not.toMatch(/verified/i)
  })
})

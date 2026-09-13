// TZ must be set BEFORE anything imports date-fns or the components under test, because the
// runtime resolves the local zone once. This is why the pin lives here and not in
// vitest.config.mts: a global pin would silently move unrelated date assertions across the suite.
process.env.TZ = 'America/New_York'

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FilingsHistoryNote from '@/features/filings/components/FilingsHistoryNote'
import { formatLocalDate } from '@/lib/format'

/**
 * An API calendar date is a UTC-midnight INSTANT. `Filing.filing_date` is a
 * `DateTime(timezone=True)` column (backend/app/models/__init__.py:212) serialised with
 * `.isoformat()` (backend/app/routers/filings.py:160), so it reaches the browser as
 * '2025-08-05T00:00:00+00:00'. Rendering that through `new Date(...)`, `parseISO(...)` or
 * `toLocaleDateString` shows 4 August to every viewer behind UTC — which is every US user, the
 * whole audience for a US SEC-filings product. For a product whose claim is that every figure
 * traces to the filing, a filed-date that is systematically wrong by a day is a credibility
 * defect, not a cosmetic one.
 *
 * CI cannot catch this by accident: GitHub runners are UTC, where the bug is invisible. That is
 * exactly why this spec pins a US zone and why the control assertion below is not optional.
 */
const WIRE = '2025-08-05T00:00:00+00:00' // a filing filed on 5 August 2025

describe('filing dates render as the filed calendar day, not a UTC instant', () => {
  it('is actually running in a timezone where the bug is observable', () => {
    // Control. If the TZ pin ever stops applying, every assertion below would pass for the wrong
    // reason — the suite would go green in UTC while the bug shipped. This fails loudly instead.
    expect(new Date(WIRE).getDate()).toBe(4)
    expect(new Date().getTimezoneOffset()).not.toBe(0)
  })

  it('formatLocalDate keeps the filed day in a zone behind UTC', () => {
    expect(formatLocalDate(WIRE, 'MMM dd, yyyy')).toBe('Aug 05, 2025')
    expect(formatLocalDate(WIRE, 'MMM d, yyyy')).toBe('Aug 5, 2025')
  })

  it('names the export file after the filed day, not the day before', () => {
    // The export filename is the one place the wrong day leaves the app and lands on a user's
    // disk, where it cannot be corrected by a later render fix.
    expect(formatLocalDate(WIRE, 'yyyyMMdd', 'summary')).toBe('20250805')
  })

  it('renders the server-seeded filings-history note on the filed day', () => {
    // This note is server-rendered (app/company/[ticker]/page.tsx seeds initialFilings), so the
    // old parseISO path was a hydration mismatch as well as a wrong date: UTC on the server,
    // local in the browser.
    render(<FilingsHistoryNote oldestFilingDate={'2001-03-31T00:00:00+00:00'} cik="19617" />)
    expect(screen.getByText(/Showing filings since Mar 31, 2001/)).toBeInTheDocument()
  })

  it('falls back rather than rendering an invalid date', () => {
    expect(formatLocalDate(null, 'MMM d, yyyy', 'Date TBD')).toBe('Date TBD')
    expect(formatLocalDate('not-a-date', 'MMM d, yyyy', '—')).toBe('—')
    const { container } = render(<FilingsHistoryNote oldestFilingDate={'not-a-date'} cik="19617" />)
    expect(container).toBeEmptyDOMElement()
  })
})

import React, { createRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { FilingIndex, type FilingIndexProps } from '@/features/filings/components/FilingIndex'
import type { Filing } from '@/features/filings/api/filings-api'
import type { RetainedFailure } from '@/hooks/useRetainedFailure'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const filing = (id: number, filing_type: string, filed: string, report_date: string, extra: Partial<Filing> = {}): Filing => ({
  id,
  filing_type,
  filing_date: `${filed}T00:00:00+00:00`,
  report_date,
  accession_number: `0001045810-${id}`,
  document_url: `https://www.sec.gov/doc/${id}`,
  sec_url: `https://www.sec.gov/edgar/${id}`,
  ...extra,
})

// NVIDIA-shaped: the fiscal year ends in late January; groups are the calendar year of the period of report.
const FILINGS: Filing[] = [
  filing(1, '10-Q', '2026-08-26', '2026-07-26'),
  filing(2, '10-Q', '2026-05-20', '2026-04-26'),
  filing(3, '10-K', '2026-02-25', '2026-01-25'),
  filing(4, '10-Q', '2025-11-19', '2025-10-26'),
  filing(5, '10-K', '2025-02-26', '2025-01-26'),
  filing(6, '10-Q', '2024-11-20', '2024-10-27'),
]
const IDLE: RetainedFailure = { failed: false, error: null, busy: false, retry: () => {} }

function Harness({ initiallyOpen = ['2026', '2025'], ...props }: Partial<FilingIndexProps> & { initiallyOpen?: string[] }) {
  const [open, setOpen] = useState(() => new Set(initiallyOpen))
  const toggle = (year: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(year)) next.delete(year)
      else next.add(year)
      return next
    })
  return (
    <FilingIndex
      companyName="NVIDIA Corp"
      filings={FILINGS}
      status="ready"
      failure={IDLE}
      headingRef={createRef<HTMLHeadingElement>()}
      latest={FILINGS[0]}
      expandedYears={open}
      onToggleYear={toggle}
      cik="1045810"
      {...props}
    />
  )
}

describe('FilingIndex', () => {
  it('is one labelled section with a sentence-case heading and a live count', () => {
    render(<Harness />)
    expect(screen.getByRole('heading', { level: 2, name: 'SEC filings' })).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('region', { name: 'SEC filings' })).toBeInTheDocument()
    expect(screen.getByText('6 filings')).toBeInTheDocument()
  })

  it('names each row by its own content: form, period of report, markers, filed date', () => {
    render(<Harness />)
    const row = screen.getByRole('link', { name: /^10-Q\s+Quarter ended Jul 26, 2026\s+Latest\s+Filed Aug 26, 2026$/ })
    expect(row).toHaveAttribute('href', '/filing/1')
    expect(row).not.toHaveAttribute('aria-label')
    expect(screen.getByRole('link', { name: /^10-K\s+Fiscal year ended Jan 25, 2026\s+Filed Feb 25, 2026$/ })).toHaveAttribute('href', '/filing/3')
  })

  it('keeps EDGAR a sibling of the row link, never nested inside it', () => {
    const { container } = render(<Harness />)
    const row = screen.getByRole('link', { name: /^10-Q\s+Quarter ended Jul 26, 2026/ })
    const edgar = screen.getByRole('link', { name: 'View the 10-Q filed Aug 26, 2026 on SEC EDGAR (opens in a new tab)' })
    expect(edgar).toHaveAttribute('href', 'https://www.sec.gov/edgar/1')
    expect(edgar).toHaveAttribute('target', '_blank')
    expect(edgar).toHaveAttribute('rel', 'noopener noreferrer')
    expect(row.contains(edgar)).toBe(false)
    expect(container.querySelectorAll('a a')).toHaveLength(0)
  })

  it('marks the latest filing once, and leads with it as the one primary action', () => {
    render(<Harness />)
    expect(screen.getAllByText('Latest')).toHaveLength(1)
    expect(screen.getByText('Latest filing')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^Summarize this filing/ })).toHaveAttribute('href', '/filing/1')
    expect(screen.getByText(/NVIDIA Corp’s most recent filing\. Start with its AI summary\./)).toBeInTheDocument()
  })

  it('drops the lead when there is no latest filing (the flag is off)', () => {
    render(<Harness latest={null} />)
    expect(screen.queryByText('Latest filing')).toBeNull()
    expect(screen.queryByText('Latest')).toBeNull()
  })

  it('exposes each year’s state and keeps collapsed lists in the DOM, hidden', () => {
    render(<Harness />)
    const year = screen.getByRole('button', { name: /Report year 2024/ })
    expect(year).toHaveAttribute('aria-expanded', 'false')
    const list = document.getElementById(year.getAttribute('aria-controls') as string)
    expect(list).not.toBeNull()
    expect(list).toHaveAttribute('hidden')
    fireEvent.click(year)
    expect(year).toHaveAttribute('aria-expanded', 'true')
    expect(list).not.toHaveAttribute('hidden')
  })

  it('filters by form through pressed segments and says how many match', () => {
    render(<Harness />)
    expect(screen.getByRole('group', { name: 'Filter by form' })).toBeInTheDocument()
    const tenK = screen.getByRole('button', { name: '10-K' })
    expect(tenK).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(tenK)
    expect(tenK).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('2 of 6 filings')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^10-Q\s/ })).toBeNull()
  })

  it('opens the group of a chosen year (a filter always shows its result)', () => {
    render(<Harness initiallyOpen={['2026']} />)
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by report year' }), { target: { value: '2024' } })
    expect(screen.getByRole('button', { name: /Report year 2024/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('1 of 6 filings')).toBeInTheDocument()
  })

  it('names the filters when nothing matches, and clears them', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: '10-K' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by report year' }), { target: { value: '2024' } })
    expect(screen.getByText('No 10-K filings in 2024.')).toBeInTheDocument()
    expect(screen.getByText('0 of 6 filings match these filters.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByText('6 filings')).toBeInTheDocument()
  })

  it('keeps a superseded original as a row and says what replaced it', () => {
    const original = filing(7, '10-K', '2024-02-21', '2024-01-28', { superseded_by_accession: 'ACC-AMEND' })
    const amendment = filing(8, '10-K/A', '2024-03-08', '2024-01-28', { accession_number: 'ACC-AMEND' })
    render(<Harness filings={[amendment, original]} latest={amendment} initiallyOpen={['2024']} />)
    expect(screen.getByText('Superseded')).toBeInTheDocument()
    expect(screen.getByText('Superseded by the 10-K/A filed Mar 8, 2024')).toBeInTheDocument()
    expect(screen.getByText('Amends the 10-K filed Feb 21, 2024')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^10-K\s+Fiscal year ended Jan 28, 2024\s+Superseded/ })).toHaveAttribute('href', '/filing/7')
  })

  it('names a filing without a period of report by its filed date, once, and says so in its row', () => {
    // Routine for a 6-K: EDGAR's submissions feed often has no reportDate for it.
    const sixK = filing(9, '6-K', '2024-11-20', '', { report_date: undefined })
    render(<Harness filings={[sixK]} latest={sixK} initiallyOpen={['2024']} />)
    const lead = screen.getByText('Latest filing').parentElement!
    expect(lead.textContent).toContain('Filed Nov 20, 2024')
    expect(lead.textContent?.match(/Filed Nov 20, 2024/g)).toHaveLength(1)
    expect(screen.getByRole('link', { name: /^6-K\s+Period of report not stated\s+Latest\s+Filed Nov 20, 2024$/ })).toHaveAttribute('href', '/filing/9')
    // It still groups under the calendar year of its filing date.
    expect(screen.getByRole('button', { name: /Report year 2024/ })).toBeInTheDocument()
  })

  it('shows the failure in place, as a Notice whose Retry is RetryButton', () => {
    const retry = vi.fn()
    render(<Harness status="error" failure={{ failed: true, error: new Error('down'), busy: false, retry }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Couldn’t load filings')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(retry).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('link', { name: /Quarter ended/ })).toBeNull()
  })

  it('loads as one status region shaped like the list, with no toolbar or lead', () => {
    render(<Harness status="loading" filings={undefined} />)
    expect(screen.getByRole('status', { name: 'Loading filings' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Filter by form' })).toBeNull()
    expect(screen.queryByText('Latest filing')).toBeNull()
  })

  it('says so plainly when a company has no filings', () => {
    render(<Harness filings={[]} latest={null} />)
    expect(screen.getByText('No filings to show')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Filter by form' })).toBeNull()
  })

  it('renders the page’s footer action beside the history note', () => {
    render(<Harness footerAction={<button type="button">Show full history</button>} />)
    expect(screen.getByRole('button', { name: 'Show full history' })).toBeInTheDocument()
    expect(screen.getByText(/Showing filings since Nov 20, 2024/)).toBeInTheDocument()
  })
})

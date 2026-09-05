import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Filing } from '@/features/filings/api/filings-api'
import SupersededFilingNotice from '@/features/filings/components/SupersededFilingNotice'
import { TickerFilingsView } from '@/features/filings/components/TickerFilingsView'
import { queryKeys } from '@/lib/queryKeys'

const original: Filing = {
  id: 41, filing_type: '10-K', filing_date: '2026-02-01', accession_number: 'original',
  document_url: 'https://www.sec.gov/original.htm', sec_url: 'https://www.sec.gov/original',
  superseded_by_accession: 'amendment',
}
const amendment: Filing = {
  ...original, id: 72, filing_type: '10-K/A', filing_date: '2026-02-02',
  accession_number: 'amendment', superseded_by_accession: null,
}

describe('filing supersession', () => {
  it('links only a known replacement and keeps an unavailable replacement as a badge', () => {
    const { rerender } = render(<SupersededFilingNotice filing={original} filings={[original, amendment]} />)
    expect(screen.getByText('Superseded')).toBeVisible()
    expect(screen.getByRole('link', { name: 'View amendment' })).toHaveAttribute('href', '/filing/72')

    rerender(<SupersededFilingNotice filing={original} filings={[original]} />)
    expect(screen.getByText('Superseded')).toBeVisible()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    rerender(<SupersededFilingNotice filing={{ ...original, superseded_by_accession: 'original' }} filings={[original]} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    rerender(<SupersededFilingNotice filing={amendment} filings={[original, amendment]} />)
    expect(screen.queryByText('Superseded')).not.toBeInTheDocument()
  })

  it('keeps the original picker route readable beside a distinct amendment link without nested anchors', () => {
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
    client.setQueryData(queryKeys.tickerCompany('AAPL'), { id: 1, ticker: 'AAPL', name: 'Apple Inc.' })
    client.setQueryData(queryKeys.tickerFilings('AAPL'), [original, amendment])
    const { container } = render(
      <QueryClientProvider client={client}><TickerFilingsView ticker="aapl" /></QueryClientProvider>,
    )
    const originalLink = screen.getByRole('link', { name: 'Generate AI summary for 10-K original' })
    expect(originalLink).toHaveAttribute('href', '/filing/41')
    const row = originalLink.parentElement!.parentElement!
    expect(within(row).getByText('Superseded')).toBeVisible()
    expect(within(row).getByRole('link', { name: 'View amendment' })).toHaveAttribute('href', '/filing/72')
    expect(screen.getByRole('link', { name: 'Generate AI summary for 10-K/A amendment' })).toHaveAttribute('href', '/filing/72')
    expect(container.querySelector('a a')).toBeNull()
    expect(screen.getAllByText('Superseded')).toHaveLength(1)
    client.clear()
  })
})

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SummaryDisplay } from '@/features/summaries/components/SummaryDisplay'
import type { Filing } from '@/features/filings/api/filings-api'

// The "Suggested follow-ups" card opens the Ask rail, so it names the feature the way the rest of
// the product does: "ask this filing", never "the Copilot" (D-034).
vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@/lib/featureFlags', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/featureFlags')>(),
  ENABLE_FINANCIAL_CHARTS: false,
}))
vi.mock('@/features/summaries/api/summaries-api', async importOriginal => ({
  ...await importOriginal<typeof import('@/features/summaries/api/summaries-api')>(),
  getWhatChanged: async () => null,
}))
vi.mock('@/features/summaries/hooks/useSummaryExports', () => ({
  useSummaryExports: () => ({ exportPdf: vi.fn(), exportCsv: vi.fn() }),
}))

const filing: Filing = {
  id: 42, filing_type: '10-K', filing_date: '2025-10-31', accession_number: 'test-accession',
  document_url: 'https://www.sec.gov/Archives/test/doc.htm', sec_url: 'https://www.sec.gov/Archives/test/',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
}
const QUESTION = 'How much of revenue came from Services?'

afterEach(cleanup)

describe('suggested follow-ups', () => {
  it('asks this filing, never "the Copilot", and hands the question to the rail', () => {
    const onAsk = vi.fn()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <SummaryDisplay filing={filing}
          summary={{ id: 91, filing_id: 42, business_overview: '## Overview\n\nThe filing narrative.', rendered_sections: [], raw_summary: { sections: { action_items: [QUESTION] } } }}
          isAuthenticated isPro={false} isSaved={false}
          saveMutation={{ mutate: vi.fn(), isPending: false }} onAsk={onAsk} />
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { name: 'Suggested follow-ups' })).toBeInTheDocument()
    expect(screen.getByText('Tap a question to ask this filing.')).toBeInTheDocument()
    expect(screen.queryByText(/copilot/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: QUESTION }))
    expect(onAsk).toHaveBeenCalledExactlyOnceWith(QUESTION, 'followup')
    client.clear()
  })
})

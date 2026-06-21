import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/features/filings/api/filing-content-api', () => ({
  fetchFilingContent: vi.fn(async () => ({
    hasContent: true,
    markdownContent: '# Filing\n\nRevenue grew strongly this year.',
  })),
}))

vi.mock('@/features/filings/components/copilot/highlightInDom', () => ({
  highlightExcerptInDom: vi.fn(() => true),
  clearCitationHighlight: vi.fn(),
}))

import FilingViewer from '@/features/filings/components/copilot/FilingViewer'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
import { highlightExcerptInDom } from '@/features/filings/components/copilot/highlightInDom'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

function Harness() {
  const v = useFilingViewer()!
  const citation: CopilotCitation = {
    n: 1,
    excerpt: 'Revenue grew strongly',
    section_ref: null,
    verified: true,
    fragment_url: null,
  }
  return (
    <>
      <button type="button" onClick={() => v.openFiling()}>
        open-filing
      </button>
      <button type="button" onClick={() => v.requestHighlight(citation)}>
        cite
      </button>
      <FilingViewer embedded filingId={1} filingLabel="AAPL 10-K" secUrl="https://sec.gov/x" />
    </>
  )
}

describe('FilingViewer (embedded)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the full filing when the Filing tab is opened (no citation)', async () => {
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'open-filing' }))

    expect(await screen.findByText(/Revenue grew strongly this year/)).toBeInTheDocument()
    expect(fetchFilingContent).toHaveBeenCalledWith(1)
    // No citation → no highlight.
    expect(highlightExcerptInDom).not.toHaveBeenCalled()
  })

  it('loads and highlights the cited passage on a citation request', async () => {
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))

    expect(await screen.findByText(/Revenue grew strongly this year/)).toBeInTheDocument()
    await waitFor(() =>
      expect(highlightExcerptInDom).toHaveBeenCalledWith(expect.anything(), 'Revenue grew strongly'),
    )
  })
})

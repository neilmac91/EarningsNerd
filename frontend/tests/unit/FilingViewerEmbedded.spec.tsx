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

  it('offers a Retry that reloads after a transient failure', async () => {
    vi.mocked(fetchFilingContent).mockRejectedValueOnce(new Error('network'))
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'open-filing' }))

    const retry = await screen.findByRole('button', { name: /try again/i })
    fireEvent.click(retry)

    expect(await screen.findByText(/Revenue grew strongly this year/)).toBeInTheDocument()
  })

  // EN-01: the pane's states after a chip activation are truthful, and every one of them keeps the
  // original-document action, whose target is the page-derived url (document_url, then sec_url).
  it('the empty state (no in-app text) offers the original document from the page-derived url', async () => {
    vi.mocked(fetchFilingContent).mockResolvedValueOnce({ filingId: 1, hasContent: false, markdownContent: null })
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    expect(await screen.findByText('The full filing text is not available to view in-app yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the original on sec\.gov/i })).toHaveAttribute('href', 'https://sec.gov/x')
    expect(highlightExcerptInDom).not.toHaveBeenCalled()
  })

  it('a content-fetch failure keeps the original-document action beside Try again', async () => {
    vi.mocked(fetchFilingContent).mockRejectedValueOnce(new Error('network'))
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    expect(await screen.findByText('Could not load the filing text.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the original on sec\.gov/i })).toHaveAttribute('href', 'https://sec.gov/x')
  })

  it('an unmatched excerpt shows the truthful banner with Open original and claims no match', async () => {
    vi.mocked(highlightExcerptInDom).mockReturnValueOnce(false)
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    expect(await screen.findByText(/Couldn’t pinpoint the exact passage/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open original' })).toHaveAttribute('href', 'https://sec.gov/x')
    expect(screen.queryByText(/source match found/i)).toBeNull()
  })

  it('repeated activation of the same citation highlights again each time', async () => {
    render(
      <FilingViewerProvider>
        <Harness />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    expect(await screen.findByText(/Revenue grew strongly this year/)).toBeInTheDocument()
    await waitFor(() => expect(highlightExcerptInDom).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    await waitFor(() => expect(highlightExcerptInDom).toHaveBeenCalledTimes(2))
    // One load serves both activations; the request is re-run, the content is not re-fetched.
    expect(fetchFilingContent).toHaveBeenCalledTimes(1)
  })
})

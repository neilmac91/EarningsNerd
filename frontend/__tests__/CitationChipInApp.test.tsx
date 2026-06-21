import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'

const citation: CopilotCitation = {
  n: 1,
  excerpt: 'Revenue increased to $391.0B this year.',
  section_ref: 'Item 7 — MD&A',
  verified: true,
  fragment_url: 'https://www.sec.gov/x#:~:text=Revenue',
}

// Surfaces the current highlight request so we can assert the chip drove it.
function RequestProbe() {
  const viewer = useFilingViewer()
  return <div data-testid="probe">{viewer?.request ? `req:${viewer.request.citation.n}` : 'none'}</div>
}

describe('CitationChip with an in-app filing viewer', () => {
  it('requests an in-app highlight on click (button, not a SEC link) + keeps "Open original"', () => {
    render(
      <FilingViewerProvider>
        <CitationChip citation={citation} />
        <RequestProbe />
      </FilingViewerProvider>,
    )

    // Primary action is a button (in-app), not a navigating anchor.
    const chip = screen.getByRole('button', { name: /citation 1: item 7 — md&a/i })
    expect(screen.queryByRole('link', { name: /citation 1/i })).toBeNull()

    expect(screen.getByTestId('probe')).toHaveTextContent('none')
    fireEvent.click(chip)
    expect(screen.getByTestId('probe')).toHaveTextContent('req:1')

    // The popover (portaled) opens on hover and offers the SEC original as a secondary link.
    fireEvent.mouseEnter(chip)
    expect(screen.getByRole('link', { name: /open original/i })).toHaveAttribute(
      'href',
      citation.fragment_url,
    )

    // It's a labelled group (it contains that interactive link), never a tooltip — a tooltip must
    // not hold focusable content.
    expect(screen.getByRole('group', { name: /citation 1: item 7 — md&a/i })).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('falls back to a SEC-jump link when no viewer is mounted', () => {
    render(<CitationChip citation={citation} />)
    const link = screen.getByRole('link', { name: /citation 1/i })
    expect(link).toHaveAttribute('href', citation.fragment_url)
    expect(link).toHaveAttribute('target', '_blank')
  })
})

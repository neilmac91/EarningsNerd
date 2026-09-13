import { describe, it, expect, vi } from 'vitest'
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

  it.each([
    { height: 863, width: 1024, chipTop: 253, naturalHeight: 312 },
    { height: 260, width: 320, chipTop: 128, naturalHeight: 500 },
  ])('keeps the measured card inside $width × $height and scrollable without losing actions', ({ height, width, chipTop, naturalHeight }) => {
    vi.stubGlobal('innerHeight', height)
    vi.stubGlobal('innerWidth', width)
    const rectSpy = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.getAttribute('role') === 'group') {
        // JSDOM has no layout. Supply the observed natural source height and browser-style
        // max-height/max-width sizing, then read the component's actual positioned coordinates.
        const maxHeight = Number.parseFloat(this.style.maxHeight) || Infinity
        const maxWidth = Number.parseFloat(this.style.maxWidth) || Infinity
        const cardHeight = Math.min(naturalHeight, maxHeight)
        const cardWidth = Math.min(256, maxWidth)
        const top = Number.parseFloat(this.style.top) || 0
        const left = (Number.parseFloat(this.style.left) || 0) - cardWidth / 2
        return { top, left, bottom: top + cardHeight, right: left + cardWidth,
          width: cardWidth, height: cardHeight, x: left, y: top, toJSON: () => ({}) } as DOMRect
      }
      return { top: chipTop, bottom: chipTop + 18, left: width - 40, right: width - 22,
        width: 18, height: 18, x: width - 40, y: chipTop, toJSON: () => ({}) } as DOMRect
    })
    try {
      render(<FilingViewerProvider><CitationChip citation={citation} /><RequestProbe /></FilingViewerProvider>)
      const chip = screen.getByRole('button', { name: /citation 1:/i })
      fireEvent.focus(chip)
      const card = screen.getByRole('group', { name: /citation 1:/i })
      const bounds = card.getBoundingClientRect()
      expect(bounds.top).toBeGreaterThanOrEqual(8)
      expect(bounds.bottom).toBeLessThanOrEqual(height - 8)
      expect(bounds.left).toBeGreaterThanOrEqual(8)
      expect(bounds.right).toBeLessThanOrEqual(width - 8)
      expect(card).toHaveStyle({ overflowY: 'auto' })
      fireEvent.scroll(card)
      expect(card).toBeInTheDocument()
      fireEvent.scroll(screen.getByText(citation.excerpt))
      expect(card).toBeInTheDocument()
      const original = screen.getByRole('link', { name: /open original/i })
      fireEvent.focus(original)
      expect(original).toHaveAttribute('href', citation.fragment_url)
      fireEvent.click(chip)
      expect(screen.getByTestId('probe')).toHaveTextContent('req:1')
      fireEvent.scroll(window)
      expect(screen.queryByRole('group', { name: /citation 1:/i })).toBeNull()
    } finally {
      rectSpy.mockRestore()
      vi.unstubAllGlobals()
    }
  })

  it('falls back to a SEC-jump link when no viewer is mounted', () => {
    render(<CitationChip citation={citation} />)
    const link = screen.getByRole('link', { name: /citation 1/i })
    expect(link).toHaveAttribute('href', citation.fragment_url)
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('visually distinguishes XBRL figure chips from text-excerpt chips', () => {
    const textCitation: CopilotCitation = { ...citation }
    const factCitation: CopilotCitation = {
      n: 'F1',
      excerpt: 'Revenue = $391.04B USD (FY2024)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: 'https://www.sec.gov/filing',
    }
    const { rerender } = render(<CitationChip citation={textCitation} />)
    expect(screen.getByRole('link', { name: /citation 1/i })).toHaveAttribute(
      'data-citation-kind',
      'text',
    )

    rerender(<CitationChip citation={factCitation} />)
    expect(screen.getByRole('link', { name: /citation f1/i })).toHaveAttribute(
      'data-citation-kind',
      'xbrl',
    )
  })
})

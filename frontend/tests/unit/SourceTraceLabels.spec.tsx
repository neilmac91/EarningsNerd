import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SourceTrace, SourceTracePanelBody } from '@/features/filings/components/SourceTrace'

// A passage chip says what its link opens (lib/evidenceLabels passageLabel): the quote it found, the section of one it
// could not find, or the filing when the passage names no section. A takeaway's passage names one only when its excerpt
// does (provenance_service._excerpt_section_ref), so "Section linked" there would promise a section the link never opens.
const DOCUMENT = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'

describe('SourceTrace passage labels', () => {
  it.each([
    [true, 'Item 7', 'Quote found in filing'],
    [true, null, 'Quote found in filing'],
    [false, 'Item 7', 'Section linked'],
    [false, null, 'Quote not found'],
  ])('verified %s, section %s: "%s"', (verified, sectionRef, label) => {
    render(<SourceTrace url={DOCUMENT} verified={verified} sectionRef={sectionRef} />)
    expect(screen.getByRole('link', { name: `Source: ${label} (opens in a new tab)` })).toBeInTheDocument()
  })

  it('says a section-less passage it could not find links to the filing', () => {
    render(<SourceTracePanelBody header={null} isVerified={false} note={null} url={DOCUMENT} />)
    expect(screen.getByText('We link to the filing. We couldn’t find these words in it.')).toBeInTheDocument()
    expect(screen.queryByText(/We link to the section/)).not.toBeInTheDocument()
  })
})

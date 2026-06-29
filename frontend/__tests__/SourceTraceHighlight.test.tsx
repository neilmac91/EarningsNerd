import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SourceTrace } from '@/components/SourceTrace'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'

// Surfaces the current highlight request so we can assert the chip drove it (mirrors the
// CitationChip in-app test's probe).
function RequestProbe() {
  const viewer = useFilingViewer()
  return <div data-testid="probe">{viewer?.request ? viewer.request.citation.excerpt : 'none'}</div>
}

const EVIDENCE = 'Our revenue is concentrated among a small number of large customers.'

describe('SourceTrace in-app highlight (item 1.4)', () => {
  it('requests an in-app highlight of the verbatim excerpt (risk factor) when a viewer is mounted', () => {
    render(
      <FilingViewerProvider>
        <SourceTrace
          url="https://sec.gov/x"
          verified
          sectionRef="Item 1A · Risk Factors"
          excerpt={EVIDENCE}
        />
        <RequestProbe />
      </FilingViewerProvider>,
    )
    expect(screen.getByTestId('probe')).toHaveTextContent('none')
    // With a viewer mounted the chip is an in-app button (not an external EDGAR link).
    fireEvent.click(screen.getByRole('button', { name: /source:/i }))
    expect(screen.getByTestId('probe')).toHaveTextContent(EVIDENCE)
  })

  it('falls back to the section heading for a metric (no verbatim excerpt) when a viewer is mounted', () => {
    render(
      <FilingViewerProvider>
        <SourceTrace url="https://sec.gov/x" verified sectionRef="Consolidated Statements of Operations" />
        <RequestProbe />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: /source:/i }))
    expect(screen.getByTestId('probe')).toHaveTextContent('Consolidated Statements of Operations')
  })

  it('degrades to the external SEC link when no viewer is mounted', () => {
    render(
      <SourceTrace url="https://sec.gov/x" verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />,
    )
    // No provider → no in-app highlight → the chip is the EDGAR anchor (unchanged behavior).
    const link = screen.getByRole('link', { name: /source:/i })
    expect(link).toHaveAttribute('href', 'https://sec.gov/x')
  })
})

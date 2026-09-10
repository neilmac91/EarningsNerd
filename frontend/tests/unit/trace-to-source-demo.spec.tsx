import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TraceToSourceDemo from '@/features/marketing/components/TraceToSourceDemo'
import { SAMPLE_TRACE } from '@/features/marketing/lib/landing-samples'

describe('TraceToSourceDemo (landing evidence section)', () => {
  it('renders the claim with its provenance panel open and a real EDGAR link', () => {
    render(<TraceToSourceDemo trace={SAMPLE_TRACE} />)
    expect(screen.getByText(SAMPLE_TRACE.claim, { exact: false })).toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: 'Source: Verified in filing' })
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    const panel = screen.getByRole('group', { name: 'Source detail' })
    expect(panel.id).not.toBe('')
    expect(trigger).toHaveAttribute('aria-controls', panel.id)
    expect(panel).toHaveTextContent(SAMPLE_TRACE.sectionRef)
    expect(panel).toHaveTextContent(SAMPLE_TRACE.excerpt)
    expect(panel).toHaveTextContent('Verified against the original SEC filing')

    expect(screen.getByRole('link', { name: /open in sec edgar/i })).toHaveAttribute('href', SAMPLE_TRACE.url)
  })

  it('toggles the panel closed and open again from the chip', () => {
    render(<TraceToSourceDemo trace={SAMPLE_TRACE} />)
    const trigger = screen.getByRole('button', { name: 'Source: Verified in filing' })

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('group', { name: 'Source detail' })).toBeNull()

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()
  })
})

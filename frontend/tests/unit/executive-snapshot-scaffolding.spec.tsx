import React from 'react'
import { render, screen } from '@testing-library/react'
import { SummaryExecutiveSnapshot } from '@/features/summaries/components/SummaryExecutiveSnapshot'

/**
 * T1.2 machine gate (CLAUDE.md rule 12): the executive snapshot renders its known schema fields as
 * real UI — never the stringified "Headline:/Key Points:/Tone:/Source Section Ref:" key labels the
 * old renderMarkdownValue flattener leaked. Branch-agnostic (component-level), so it holds for both
 * the tabbed and simplified summary layouts.
 */
describe('SummaryExecutiveSnapshot kills dict-flattener scaffolding leaks', () => {
  it('renders known keys without field-name labels and suppresses neutral tone + raw section ref', () => {
    render(
      <SummaryExecutiveSnapshot
        snapshot={{
          headline: 'Revenue rose on data-center demand',
          key_points: ['Data-center revenue up sharply', 'Gross margin expanded'],
          tone: 'neutral',
          source_section_ref: 'Item 2. MD&A',
        }}
      />,
    )
    expect(screen.getByText('Revenue rose on data-center demand')).toBeInTheDocument()
    expect(screen.getByText('Data-center revenue up sharply')).toBeInTheDocument()
    expect(screen.getByText('Gross margin expanded')).toBeInTheDocument()
    // No stringified schema field names
    expect(screen.queryByText(/Headline:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Key Points:/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Tone:/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Source Section Ref:/i)).not.toBeInTheDocument()
    // Neutral tone renders nothing; raw section ref is not surfaced in T1.2
    expect(screen.queryByText(/neutral/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Item 2\. MD&A/)).not.toBeInTheDocument()
  })

  it('shows a non-neutral tone as a badge without a Tone: label', () => {
    render(
      <SummaryExecutiveSnapshot
        snapshot={{ headline: 'Guidance raised', key_points: ['Q3 outlook lifted'], tone: 'positive' }}
      />,
    )
    expect(screen.getByText('positive')).toBeInTheDocument()
    expect(screen.queryByText(/Tone:/i)).not.toBeInTheDocument()
  })

  it('falls back to markdown for a legacy string snapshot', () => {
    render(<SummaryExecutiveSnapshot snapshot={'Plain overview text.'} />)
    expect(screen.getByText('Plain overview text.')).toBeInTheDocument()
  })
})

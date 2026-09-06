import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ExampleSummaryCard from '@/features/marketing/components/ExampleSummaryCard'
import type { ExampleData } from '@/lib/serverApi'

const example: ExampleData = {
  filingId: 42,
  ticker: 'ASML',
  companyName: 'ASML Holding N.V.',
  filingType: '20-F',
  filingDate: '2026-02-11',
  secUrl: 'https://www.sec.gov/Archives/edgar/data/937966/000093796626000001/',
  excerpt: 'Fixture excerpt from this issuer.',
  qualityTier: 'full',
  metrics: [
    { label: 'Revenue', value: '€32.7B' },
    { label: 'Net Income', value: '€9.6B' },
  ],
}

describe('ExampleSummaryCard source consistency', () => {
  it('does not attach fallback Apple figures to a live issuer with no matched metrics', () => {
    render(<ExampleSummaryCard example={{ ...example, metrics: [] }} />)

    expect(screen.getByText('ASML Holding N.V.')).toBeInTheDocument()
    expect(screen.getByText('20-F')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'ASML Holding N.V. logo' })).toBeInTheDocument()
    expect(screen.queryByText('$394.3B')).not.toBeInTheDocument()
    expect(screen.queryByText('$99.8B')).not.toBeInTheDocument()
    expect(screen.queryByText('$6.11')).not.toBeInTheDocument()
    expect(screen.queryByText('Revenue')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Read the full summary/ })).toBeInTheDocument()
  })

  it('renders the live issuer and its supplied financial figures together', () => {
    render(<ExampleSummaryCard example={example} />)

    expect(screen.getByText('ASML Holding N.V.')).toBeInTheDocument()
    expect(screen.getByText('€32.7B')).toBeInTheDocument()
    expect(screen.getByText('€9.6B')).toBeInTheDocument()
    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument()
  })

  it('uses the complete dated Apple snapshot only when no live example is available', () => {
    render(<ExampleSummaryCard example={null} />)

    expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    expect(screen.getByText('10-K · FY 2022')).toBeInTheDocument()
    expect(screen.getByText('$394.3B')).toBeInTheDocument()
    expect(screen.getByText('$99.8B')).toBeInTheDocument()
    expect(screen.getByText('$6.11')).toBeInTheDocument()
  })
})

import React from 'react'
import { render, screen } from '@testing-library/react'
import { FilingPulse, type Pulse } from '@/components/FilingPulse'

const pulse: Pulse = {
  score: 10,
  tier: 'Active',
  has_signal: true,
  components: [
    { key: 'recency', label: 'Recently filed', description: 'fresh', source: 'EDGAR', value: 5, share: 50 },
    { key: 'news_buzz', label: 'News volume', description: 'news', source: 'Finnhub', value: 3.5, share: 35 },
    { key: 'filing_velocity', label: 'Filing cadence', description: 'cadence', source: 'EDGAR', value: 1.5, share: 15 },
    { key: 'search_activity', label: 'Reader interest', description: 'reads', source: 'EarningsNerd', value: 0.5, share: 5 },
  ],
}

describe('FilingPulse (calm, sourced gauge)', () => {
  it('shows the qualitative tier, not a hype number', () => {
    const { container } = render(<FilingPulse pulse={pulse} />)
    expect(container.textContent).toContain('Pulse')
    expect(container.textContent).toContain('Active')
    // The calm gauge is intentionally not the casino "On Fire" / orange aesthetic.
    expect(container.textContent).not.toContain('On Fire')
    expect(container.querySelector('.text-orange-300')).toBeNull()
  })

  it('lists the top three driving signals with their share', () => {
    const { container } = render(<FilingPulse pulse={pulse} />)
    expect(container.textContent).toContain('Recently filed')
    expect(container.textContent).toContain('News volume')
    expect(container.textContent).toContain('Filing cadence')
    // Capped at three — the 4th signal is not shown.
    expect(container.textContent).not.toContain('Reader interest')
    expect(container.textContent).toContain('50%')
  })

  it('exposes an accessible label for the gauge', () => {
    render(<FilingPulse pulse={pulse} />)
    expect(screen.getByRole('img', { name: /filing pulse: active/i })).toBeInTheDocument()
  })

  it('degrades to a Quiet gauge with no signals', () => {
    const quiet: Pulse = { score: 0, tier: 'Quiet', has_signal: false, components: [] }
    const { container } = render(<FilingPulse pulse={quiet} />)
    expect(container.textContent).toContain('Quiet')
    expect(screen.getByRole('img', { name: /filing pulse: quiet/i })).toBeInTheDocument()
  })

  it('falls back to a raw score when no pulse is provided', () => {
    render(<FilingPulse score={4} />)
    // No pulse object -> defaults to the Quiet tier but still renders the gauge.
    expect(screen.getByRole('img', { name: /filing pulse/i })).toBeInTheDocument()
  })
})

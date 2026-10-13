import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))

vi.mock('@/lib/analytics', () => ({
  analytics: { paywallPromptShown: vi.fn() },
}))

import { analytics } from '@/lib/analytics'
import CopilotTeaser from '@/features/filings/components/copilot/CopilotTeaser'

const baseProps = {
  filingId: 7,
  filingType: '10-K',
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  isAuthenticated: true,
  onUpgrade: vi.fn(),
}

describe('CopilotTeaser', () => {
  beforeEach(() => {
    vi.mocked(analytics.paywallPromptShown).mockClear()
  })

  it('renders value props + upgrade CTA and fires the paywall event once', () => {
    const onUpgrade = vi.fn()
    render(<CopilotTeaser {...baseProps} onUpgrade={onUpgrade} />)

    // Claims scoped to what the answer card shows (ASK-01, ASK-02; brandCopyRules rule 1).
    expect(screen.getByText('Cited passages you can check against the filing')).toBeInTheDocument()
    expect(screen.getByText('Figures from XBRL show the tag they came from')).toBeInTheDocument()
    expect(screen.queryByText(/never guessed|every answer|exact filing text/i)).not.toBeInTheDocument()
    // The CTA is a button that opens the contextual upgrade modal (not a raw /pricing link).
    const cta = screen.getByRole('button', { name: /upgrade to pro/i })
    fireEvent.click(cta)
    expect(onUpgrade).toHaveBeenCalledTimes(1)
    expect(analytics.paywallPromptShown).toHaveBeenCalledTimes(1)
    expect(analytics.paywallPromptShown).toHaveBeenCalledWith(
      expect.objectContaining({
        filingId: 7,
        ticker: 'AAPL',
        filingType: '10-K',
        entryPoint: 'copilot_rail',
      }),
    )
  })

  it("blurs a sample from Apple's verified FY2025 10-K, with the sequential markers a live answer shows", () => {
    const { container } = render(<CopilotTeaser {...baseProps} />)
    const sample = container.querySelector('[aria-hidden="true"]')!
    expect(sample).toHaveTextContent('AAPL · 10-K · FY2025')
    expect(sample).toHaveTextContent(
      'Services net sales were $109.2B, up 13.5% from $96.2B [1]. Management attributes the increase to advertising, the App Store and cloud services [2].',
    )
    expect(sample).toHaveTextContent('2 matched sources')
    // The server renumbers every marker, so a live answer never shows [F1].
    expect(sample.textContent).not.toMatch(/\[F\d+\]/)
  })

  it('uses the issuer in the heading, falling back cleanly when unknown', () => {
    const { rerender } = render(<CopilotTeaser {...baseProps} ticker="AAPL" />)
    expect(screen.getByText("Ask AAPL’s 10-K anything")).toBeInTheDocument()

    // No ticker and no company → "Ask this 10-K anything" (not "Ask this filing’s 10-K anything").
    rerender(<CopilotTeaser {...baseProps} ticker={null} companyName={null} />)
    expect(screen.getByText('Ask this 10-K anything')).toBeInTheDocument()
  })

  it('shows a sign-in link only for unauthenticated visitors', () => {
    const { rerender } = render(<CopilotTeaser {...baseProps} isAuthenticated={false} />)
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()

    rerender(<CopilotTeaser {...baseProps} isAuthenticated />)
    expect(screen.queryByRole('link', { name: /sign in/i })).not.toBeInTheDocument()
  })
})

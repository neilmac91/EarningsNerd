import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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
}

describe('CopilotTeaser', () => {
  beforeEach(() => {
    vi.mocked(analytics.paywallPromptShown).mockClear()
  })

  it('renders value props + upgrade CTA and fires the paywall event once', () => {
    render(<CopilotTeaser {...baseProps} />)

    expect(screen.getByText(/never guessed/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upgrade to pro/i })).toHaveAttribute('href', '/pricing')
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

  it('shows a sign-in link only for unauthenticated visitors', () => {
    const { rerender } = render(<CopilotTeaser {...baseProps} isAuthenticated={false} />)
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()

    rerender(<CopilotTeaser {...baseProps} isAuthenticated />)
    expect(screen.queryByRole('link', { name: /sign in/i })).not.toBeInTheDocument()
  })
})

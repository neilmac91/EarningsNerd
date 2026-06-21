import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/features/filings/api/copilot-api', () => ({
  askFilingStream: vi.fn(),
  // Keep the real paywall heuristic so the error-state branch is exercised honestly.
  isCopilotPaywallError: (msg: string) => /pro feature|upgrade to pro|monthly limit/i.test(msg),
}))

vi.mock('@/lib/analytics', () => ({
  analytics: {
    paywallPromptShown: vi.fn(),
    copilotQuestionAsked: vi.fn(),
    copilotAnswerCompleted: vi.fn(),
    copilotAnswerErrored: vi.fn(),
  },
}))

import { askFilingStream, type CopilotHandlers } from '@/features/filings/api/copilot-api'
import { analytics } from '@/lib/analytics'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'

const baseProps = {
  filingId: 42,
  filingType: '10-Q',
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  summaryAvailable: true,
  isPro: true,
  isAuthenticated: true,
}

function renderRail(overrides: Partial<React.ComponentProps<typeof AskCopilotRail>> = {}) {
  const onOpenChange = vi.fn()
  const utils = render(
    <AskCopilotRail {...baseProps} open={false} onOpenChange={onOpenChange} {...overrides} />,
  )
  return { onOpenChange, ...utils }
}

describe('AskCopilotRail', () => {
  beforeEach(() => {
    vi.mocked(askFilingStream).mockReset()
  })

  it('renders the launcher when a summary is available', () => {
    renderRail()
    expect(screen.getByRole('button', { name: /ask this filing/i })).toBeInTheDocument()
  })

  it('renders nothing when no summary is available', () => {
    const { container } = renderRail({ summaryAvailable: false })
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the locked teaser for non-Pro users, fires paywall analytics, never calls the API', () => {
    renderRail({ open: true, isPro: false })
    // Richer teaser: value prop + upsell CTA (no streaming).
    expect(screen.getByText(/cited to the exact filing text/i)).toBeInTheDocument()
    const upgrade = screen.getByRole('link', { name: /upgrade to pro/i })
    expect(upgrade).toHaveAttribute('href', '/pricing')
    expect(askFilingStream).not.toHaveBeenCalled()
    expect(analytics.paywallPromptShown).toHaveBeenCalledWith(
      expect.objectContaining({ filingId: 42, entryPoint: 'copilot_rail' }),
    )
  })

  it('shows starter chips in the empty state for Pro users', () => {
    renderRail({ open: true })
    // 10-Q-specific starter question
    expect(
      screen.getByRole('button', { name: /how did revenue and margins change this quarter/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /what are the top risks/i })).toBeInTheDocument()
  })

  it('streams tokens and renders the grounded footer + a source row on complete', async () => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })

    const user = userEvent.setup()
    renderRail({ open: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(askFilingStream).toHaveBeenCalledTimes(1)
    const [filingIdArg, questionArg] = vi.mocked(askFilingStream).mock.calls[0]
    expect(filingIdArg).toBe(42)
    expect(questionArg).toBe('What changed?')

    // User message is shown.
    expect(screen.getByText('What changed?')).toBeInTheDocument()

    // Drive the streamed answer synchronously via the captured handlers.
    const handlers = captured!
    handlers.onProgress?.('reading')
    handlers.onToken('Revenue ')
    handlers.onToken('grew 8%.')
    handlers.onComplete({
      answer: 'Revenue grew 8%.',
      citations: [
        {
          n: 1,
          excerpt: 'Net sales increased 8%...',
          section_ref: 'MD&A — Results of Operations',
          verified: true,
          fragment_url: 'https://sec.gov/frag#1',
        },
      ],
      grounded: 1,
      kind: 'answer',
      followups: [],
    })

    expect(await screen.findByText(/revenue grew 8%/i)).toBeInTheDocument()
    expect(screen.getByText(/grounded in 1 excerpt/i)).toBeInTheDocument()

    const sourceLink = screen.getByRole('link', { name: /MD&A — Results of Operations/i })
    expect(sourceLink).toHaveAttribute('href', 'https://sec.gov/frag#1')
    expect(sourceLink).toHaveAttribute('target', '_blank')

    // Analytics: the question opened the funnel and the completion logged the quality signals.
    expect(analytics.copilotQuestionAsked).toHaveBeenCalledWith(
      expect.objectContaining({ filingId: 42, ticker: 'AAPL', filingType: '10-Q' }),
    )
    expect(analytics.copilotAnswerCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'answer', grounded: 1, citations: 1, usedXbrl: false }),
    )
  })

  it('opens the rail on ⌘K and on "/" (when not typing)', () => {
    const cmd = renderRail({ open: false })
    fireEvent.keyDown(document.body, { key: 'k', metaKey: true })
    expect(cmd.onOpenChange).toHaveBeenCalledWith(true)

    cmd.unmount()
    const slash = renderRail({ open: false })
    fireEvent.keyDown(document.body, { key: '/' })
    expect(slash.onOpenChange).toHaveBeenCalledWith(true)
  })

  it('closes the rail on Escape when open', () => {
    const { onOpenChange } = renderRail({ open: true })
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('renders the distinct "Not disclosed" card on a not_disclosed completion', async () => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })

    const user = userEvent.setup()
    renderRail({ open: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'What is the CEO salary?')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    captured!.onNotDisclosed('The filing does not disclose the CEO salary.')

    expect(await screen.findByText(/not disclosed in this filing/i)).toBeInTheDocument()
    expect(
      screen.getByText(/the filing does not disclose the ceo salary/i),
    ).toBeInTheDocument()
    // The not-disclosed card must not carry the grounded footer.
    expect(screen.queryByText(/grounded in/i)).not.toBeInTheDocument()
  })

  it('shows an upgrade link inside the bubble on a paywall error', async () => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })

    const user = userEvent.setup()
    renderRail({ open: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'anything')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    captured!.onError('This is a Pro feature.')

    const errorBubble = await screen.findByText('This is a Pro feature.')
    const upgradeLink = within(errorBubble.closest('div')!).getByRole('link', { name: /upgrade to pro/i })
    expect(upgradeLink).toHaveAttribute('href', '/pricing')
  })
})

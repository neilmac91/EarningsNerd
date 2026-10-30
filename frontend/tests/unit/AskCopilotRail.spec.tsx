import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => ({ id: 1 }) }))

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

// UpgradeModal (rendered by the rail) uses useRouter; provide a stub app router.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/features/filings/api/copilot-api', async () => {
  const actual = await vi.importActual<typeof import('@/features/filings/api/copilot-api')>(
    '@/features/filings/api/copilot-api',
  )
  // Partial mock: stub the network call but keep the real pure helpers (paywall heuristic,
  // isXbrlCitation/xbrlTag) so the rendered message exercises the genuine code paths.
  return {
    ...actual,
    askFilingStream: vi.fn(),
  }
})

vi.mock('@/lib/analytics', () => ({
  analytics: {
    paywallPromptShown: vi.fn(),
    paywallCtaClicked: vi.fn(),
    copilotQuestionAsked: vi.fn(),
    copilotAnswerCompleted: vi.fn(),
    copilotAnswerErrored: vi.fn(),
  },
}))

// The rail fetches Copilot usage (PRO monthly count, or FREE lifetime "taste" balance); stub it so
// tests don't hit network. Controllable per-test via mockGetUsage.
const mockGetUsage = vi.fn()
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getUsage: () => mockGetUsage(),
}))

const PRO_USAGE = {
  summaries_used: 0,
  summaries_limit: null,
  is_pro: true,
  month: '2026-06',
  qa_used: 3,
  qa_limit: 1000,
  copilot_free_taste_used: 0,
  copilot_free_taste_total: 0,
}

import { queryKeys } from '@/lib/queryKeys'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { askFilingStream, type CopilotHandlers } from '@/features/filings/api/copilot-api'
import { analytics } from '@/lib/analytics'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import { PANE_PANEL_IDS } from '@/features/filings/components/copilot/SecondaryPaneTabs'

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
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(queryKeys.currentUser(), overrides.isAuthenticated === false ? null : { id: 1 })
  let props = overrides
  const view = () => (
    <QueryClientProvider client={queryClient}>
      <AskCopilotRail {...baseProps} open={false} onOpenChange={onOpenChange} {...props} />
    </QueryClientProvider>
  )
  const utils = render(view())
  return { onOpenChange, ...utils, rerenderRail: (patch: typeof overrides) => {
    props = { ...props, ...patch }
    utils.rerender(view())
  } }

}

describe('AskCopilotRail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(askFilingStream).mockReset()
    mockGetUsage.mockReset()
    mockGetUsage.mockResolvedValue(PRO_USAGE)
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
    // Richer teaser: value prop + upsell CTA (no streaming). The CTA opens the contextual upgrade
    // modal and records the click, rather than navigating to a raw /pricing link.
    expect(screen.getByText(/cited passages you can check against the filing/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))
    expect(analytics.paywallCtaClicked).toHaveBeenCalledWith(
      expect.objectContaining({ filingId: 42, entryPoint: 'copilot_rail' }),
    )
    // Modal appears (its primary action).
    expect(screen.getByRole('button', { name: /see plans/i })).toBeInTheDocument()
    expect(askFilingStream).not.toHaveBeenCalled()
    expect(analytics.paywallPromptShown).toHaveBeenCalledWith(
      expect.objectContaining({ filingId: 42, entryPoint: 'copilot_rail' }),
    )
  })

  it('lets a FREE user with remaining taste ask, and shows the free-questions count (roadmap 2.2)', async () => {
    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 1, copilot_free_taste_total: 3,
    })
    renderRail({ open: true, isPro: false })

    // Composer (not the teaser) once usage confirms taste remains, plus an honest count.
    expect(await screen.findByLabelText(/ask about this filing/i)).toBeInTheDocument()
    expect(screen.getByText(/2 of 3 free questions left/i)).toBeInTheDocument()
    // Pro's questions are capped too, so the upsell names the plan and promises no "unlimited" (ASK-03).
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    expect(screen.queryByText(/unlimited/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/cited passages you can check against the filing/i)).not.toBeInTheDocument()
  })

  it('a FREE user who spends the last question keeps the conversation, with the cap from usage and no "unlimited"', async () => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })
    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 2, copilot_free_taste_total: 3,
    })
    const user = userEvent.setup()
    renderRail({ open: true, isPro: false })
    await user.type(await screen.findByLabelText(/ask about this filing/i), 'anything')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 3, copilot_free_taste_total: 3,
    })
    await act(async () => {
      captured!.onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] })
    })

    // One product name in the sentence (D-034), and Pro's monthly cap read from the usage response.
    expect(await screen.findByText('You’ve used your 3 free questions.')).toBeInTheDocument()
    expect(screen.getByText('Pro includes 1,000 questions a month.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    expect(screen.queryByText(/unlimited|copilot/i)).not.toBeInTheDocument()
  })

  it('refetches usage after a plan gate, so the usage line agrees with the plan card', async () => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })
    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 2, copilot_free_taste_total: 3,
    })
    const user = userEvent.setup()
    renderRail({ open: true, isPro: false })
    expect(await screen.findByText(/1 of 3 free questions left/i)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/ask about this filing/i), 'anything')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    // The allowance was spent elsewhere first (another tab): the server's 403 says so, and its count moved.
    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 3, copilot_free_taste_total: 3,
    })
    const fetched = mockGetUsage.mock.calls.length
    await act(async () => {
      captured!.onError("You've used your 3 free Copilot questions. Upgrade to Pro to access this feature.")
    })

    expect(await screen.findByText('You’ve used your 3 free questions.')).toBeInTheDocument()
    expect(mockGetUsage.mock.calls.length).toBeGreaterThan(fetched)
    expect(screen.queryByText(/1 of 3 free questions left/i)).not.toBeInTheDocument()
  })

  it('names the filing without a possessive on "this filing" when the issuer is unknown', () => {
    renderRail({ open: true, ticker: null, companyName: null })
    expect(screen.getByText(/ask anything about this 10-Q\./i)).toBeInTheDocument()
    expect(screen.queryByText(/this filing’s/i)).not.toBeInTheDocument()
  })

  it('drops the old claim from the empty state: not every answer carries a citation', () => {
    renderRail({ open: true })
    // An answer can ship an uncited figure or a not-disclosed verdict with no citation
    // (copilot_service.py), so the rail never says every answer cites its excerpts (D-034). The
    // sentence it says instead is copilotClaim.spec.tsx's case; this one holds the old one out.
    expect(screen.getByRole('button', { name: /what are the top risks/i })).toBeInTheDocument()
    expect(screen.queryByText(/cite the excerpts they came from|grounded in the filing/i)).not.toBeInTheDocument()
  })

  it('shows the teaser for a FREE user who has spent all their free questions', async () => {
    mockGetUsage.mockResolvedValue({
      ...PRO_USAGE, is_pro: false, qa_used: 0,
      copilot_free_taste_used: 3, copilot_free_taste_total: 3,
    })
    renderRail({ open: true, isPro: false })

    // Exhausted + no conversation yet → the locked teaser (its CTA upsells).
    expect(await screen.findByText(/cited passages you can check against the filing/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/ask about this filing/i)).not.toBeInTheDocument()
  })

  it('shows starter chips in the empty state for Pro users', () => {
    renderRail({ open: true })
    // 10-Q-specific starter question
    expect(
      screen.getByRole('button', { name: /how did revenue and margins change this quarter/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /what are the top risks/i })).toBeInTheDocument()
  })

  it('brings the composer back into view when a question leaves focus in it, after Send or Enter', async () => {
    vi.mocked(askFilingStream).mockImplementation(async () => {})
    // jsdom has no scrollIntoView; record each call's element and options.
    const calls: { el: Element; arg: unknown }[] = []
    const jsdomScrollIntoView = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = vi.fn(function (this: Element, arg?: boolean | ScrollIntoViewOptions) {
      calls.push({ el: this, arg })
    })
    try {
      const user = userEvent.setup()
      // The column returns to the top, then the composer's shell (the box that draws its focus ring around the field
      // and Send, never the whole form: CopilotComposer.spec.tsx) comes to its nearest edge, once per question.
      for (const via of ['Send', 'Enter'] as const) {
        calls.length = 0
        const view = renderRail({ open: true })
        const field = screen.getByLabelText(/ask about this filing/i)
        await user.type(field, via === 'Enter' ? 'What changed?{Enter}' : 'What changed?')
        if (via === 'Send') await user.click(screen.getByRole('button', { name: /^send$/i }))
        expect(document.activeElement).toBe(via === 'Enter' ? field : screen.getByRole('button', { name: /^send$/i }))
        expect(calls).toHaveLength(1)
        expect(calls[0].arg).toEqual({ block: 'nearest' })
        expect(calls[0].el.contains(field) && calls[0].el.contains(document.activeElement)).toBe(true)
        expect(calls[0].el.tagName).not.toBe('FORM')
        view.unmount()
      }
      expect(askFilingStream).toHaveBeenCalledTimes(2)
    } finally {
      Element.prototype.scrollIntoView = jsdomScrollIntoView
    }
  })

  it('anchors once per question: a progress heartbeat leaves the column and the composer where the reader put them', async () => {
    let captured!: CopilotHandlers
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { captured = handlers })
    // jsdom has no scrollIntoView; count the reveals.
    const reveals: Element[] = []
    const jsdomScrollIntoView = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
      reveals.push(this)
    })
    try {
      const user = userEvent.setup()
      renderRail({ open: true })
      const field = screen.getByLabelText(/ask about this filing/i)
      // The column that scrolls as one (the composer form's parent): record every write to its scrollTop.
      const column = field.closest('form')!.parentElement!
      const writes: number[] = []
      let top = 0
      Object.defineProperty(column, 'scrollTop', {
        configurable: true,
        get: () => top,
        set: (value: number) => {
          top = value
          writes.push(value)
        },
      })

      await user.type(field, 'What changed?{Enter}')
      expect(writes).toEqual([0])
      expect(reveals).toHaveLength(1)

      // The reader scrolls back up the column while the answer is read; the server's heartbeats keep coming.
      top = 120
      act(() => {
        captured.onProgress?.('reading')
        captured.onProgress?.('reading')
      })
      expect(writes).toEqual([0])
      expect(top).toBe(120)
      expect(reveals).toHaveLength(1)

      // The next question is a new turn, and anchors again.
      act(() => captured.onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
      await user.type(field, 'And margins?{Enter}')
      expect(askFilingStream).toHaveBeenCalledTimes(2)
      expect(writes).toEqual([0, 0])
      expect(reveals).toHaveLength(2)
    } finally {
      Element.prototype.scrollIntoView = jsdomScrollIntoView
    }
  })

  it('holds intermediate prose and renders the source-check footer + a source row on complete', async () => {
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
    act(() => {
      handlers.onProgress?.('reading')
      handlers.onToken('UNADMITTED REVENUE')
      handlers.onNotDisclosed('UNADMITTED ABSENCE')
    })
    expect(screen.queryByText(/UNADMITTED/)).not.toBeInTheDocument()
    expect(analytics.copilotAnswerCompleted).not.toHaveBeenCalled()
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
    expect(screen.getByText(/1 matched source/i)).toBeInTheDocument()

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

  it.each([
    { payload: {}, usedXbrl: false },
    { payload: { fact: true as const }, usedXbrl: true },
    { payload: { calculated: true as const }, usedXbrl: true },
  ])('logs usedXbrl $usedXbrl from the fact payload $payload, never the "XBRL · …" label (E179)', async ({ payload, usedXbrl }) => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })
    const user = userEvent.setup()
    renderRail({ open: true })
    await user.type(screen.getByLabelText(/ask about this filing/i), 'What was revenue?{Enter}')
    act(() => captured!.onComplete({
      answer: 'Revenue was $391.0B [1].',
      citations: [{ n: 1, excerpt: 'Revenue = $391.04B USD (FY2024)', section_ref: 'XBRL · us-gaap:Revenues', verified: true,
        fragment_url: null, ...payload }],
      grounded: 1,
      kind: 'answer',
      followups: [],
    }))
    expect(analytics.copilotAnswerCompleted).toHaveBeenCalledWith(expect.objectContaining({ usedXbrl }))
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

    act(() => captured!.onNotDisclosed('UNADMITTED ABSENCE'))
    expect(screen.queryByText('UNADMITTED ABSENCE')).not.toBeInTheDocument()
    captured!.onComplete({ answer: 'The filing does not disclose the CEO salary.', citations: [],
      grounded: 0, kind: 'not_disclosed', followups: [] })

    expect(await screen.findByText(/not disclosed in this filing/i)).toBeInTheDocument()
    expect(
      screen.getByText(/the filing does not disclose the ceo salary/i),
    ).toBeInTheDocument()
    // The not-disclosed card must not carry the source-check footer.
    expect(screen.queryByText(/matched sources?/i)).not.toBeInTheDocument()
  })

  it('shows an upgrade CTA inside the bubble on a paywall error (opens the modal + tracks it)', async () => {
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
    const upgrade = within(errorBubble.closest('div')!).getByRole('button', { name: /upgrade to pro/i })
    fireEvent.click(upgrade)

    expect(analytics.paywallCtaClicked).toHaveBeenCalledWith(
      expect.objectContaining({ filingId: 42, entryPoint: 'copilot_limit' }),
    )
    expect(screen.getByRole('button', { name: /see plans/i })).toBeInTheDocument()
  })

  // E31: the card follows a known code whatever the words say, so their next edit cannot move a button.
  it.each([
    ['a plan gate in other words', 'Words that name neither.', 'plan_required' as const, { upgrade: true, retry: false }],
    ['the cap in words that name Pro', 'Upgrade to Pro will not lift this.', 'pro_fair_use_limit' as const, { upgrade: false, retry: false }],
    ['a pause in words that read like a limit', 'Monthly limit reached for now.', 'generation_paused' as const, { upgrade: false, retry: true }],
  ])('answers %s by its code', async (_, words, code, shows) => {
    let captured: CopilotHandlers | null = null
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => {
      captured = handlers
    })
    const user = userEvent.setup()
    renderRail({ open: true })
    await user.type(screen.getByLabelText(/ask about this filing/i), 'anything')
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    await act(async () => {
      captured!.onError(words, code)
    })

    const bubble = (await screen.findByText(words)).closest('div')!
    expect(within(bubble).queryAllByRole('button', { name: /upgrade to pro/i })).toHaveLength(shows.upgrade ? 1 : 0)
    expect(within(bubble).queryAllByRole('button', { name: /try again/i })).toHaveLength(shows.retry ? 1 : 0)
  })

  it('clears a cancelled pending turn, preserves completed history, and ignores obsolete callbacks after reopening', async () => {
    const requests: { handlers: CopilotHandlers; signal?: AbortSignal }[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers, signal) => {
      requests.push({ handlers, signal })
    })
    const user = userEvent.setup()
    const rail = renderRail({ open: true })
    const ask = async (question: string) => {
      await user.type(screen.getByLabelText(/ask about this filing/i), question)
      await user.click(screen.getByRole('button', { name: /^send$/i }))
    }
    await ask('Completed question')
    act(() => requests[0].handlers.onComplete({ answer: 'Retained completed answer.', citations: [],
      grounded: 0, kind: 'answer', followups: [] }))
    await ask('Cancelled question')
    act(() => requests[1].handlers.onToken('REJECTED DRAFT'))
    rail.rerenderRail({ open: false })
    expect(requests[1].signal?.aborted).toBe(true)
    rail.rerenderRail({ open: true })
    expect(screen.getByText('Retained completed answer.')).toBeInTheDocument()
    expect(screen.getByText('The question was cancelled. Please try again.')).toBeInTheDocument()
    expect(screen.getByLabelText(/ask about this filing/i)).not.toBeDisabled()
    expect(screen.queryByText('REJECTED DRAFT')).not.toBeInTheDocument()
    await ask('New question')
    act(() => {
      requests[1].handlers.onComplete({ answer: 'OBSOLETE ANSWER', citations: [], grounded: 0, kind: 'answer', followups: ['OBSOLETE FOLLOWUP'] })
      requests[1].handlers.onError('OBSOLETE ERROR')
    })
    expect(screen.queryByText(/OBSOLETE/)).not.toBeInTheDocument()
    await user.type(screen.getByLabelText(/ask about this filing/i), 'Queued next question')
    // Unavailable mid-stream via aria-disabled, never native `disabled` (Chromium blurs a focused
    // button that turns disabled) — busyControls.filings.spec.tsx pins focus + the re-entry guard.
    expect(screen.getByRole('button', { name: /^send$/i })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled()
    expect(vi.mocked(askFilingStream).mock.calls[2][2]).toEqual([
      { role: 'user', content: 'Completed question' }, { role: 'assistant', content: 'Retained completed answer.' },
    ])
    act(() => requests[2].handlers.onComplete({ answer: 'New admitted answer.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    expect(screen.getByText('New admitted answer.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^send$/i })).not.toHaveAttribute('aria-disabled')
    expect(analytics.copilotAnswerCompleted).toHaveBeenCalledTimes(2)
    rail.unmount()
  })

  it('uses the real wire consumer to reject draft-bearing false citations without a completed event', async () => {
    const actual = await vi.importActual<typeof import('@/features/filings/api/copilot-api')>('@/features/filings/api/copilot-api')
    vi.mocked(askFilingStream).mockImplementation(actual.askFilingStream)
    let control!: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({ start(c) { control = c } })
    const originalFetch = global.fetch
    global.fetch = async () => new Response(body)
    const encoder = new TextEncoder()
    const emit = async (event: unknown) => {
      await act(async () => {
        control.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
        for (let i = 0; i < 12; i++) await Promise.resolve()
      })
    }
    const user = userEvent.setup()
    const rail = renderRail({ open: true })
    try {
      await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?')
      await user.click(screen.getByRole('button', { name: /^send$/i }))
      await emit({ type: 'token', text: 'UNVERIFIED FINANCIAL DRAFT' })
      expect(screen.queryByText('UNVERIFIED FINANCIAL DRAFT')).not.toBeInTheDocument()
      await emit({ type: 'complete', answer: 'UNVERIFIED FINANCIAL DRAFT [1]', citations: [
        { n: 1, excerpt: 'absent excerpt', section_ref: null, verified: false, fragment_url: null },
      ], grounded: 0, kind: 'answer', followups: ['UNVERIFIED FOLLOWUP'] })
      expect(screen.getByText("I couldn't verify the cited evidence, so I couldn't provide this answer.")).toBeInTheDocument()
      expect(screen.queryByText(/UNVERIFIED|absent excerpt/)).not.toBeInTheDocument()
      expect(analytics.copilotAnswerCompleted).not.toHaveBeenCalled()
      expect(analytics.copilotAnswerErrored).toHaveBeenCalledOnce()
      expect(screen.getByLabelText(/ask about this filing/i)).not.toBeDisabled()
    } finally { rail.unmount(); global.fetch = originalFetch }
  })

  it('invalidates callbacks on unmount without accepting a late completion', async () => {
    let captured!: CopilotHandlers
    let signal!: AbortSignal
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers, s) => { captured = handlers; signal = s! })
    const user = userEvent.setup()
    const rail = renderRail({ open: true })
    await user.type(screen.getByLabelText(/ask about this filing/i), 'Pending question')
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    rail.unmount()
    expect(signal.aborted).toBe(true)
    act(() => captured.onComplete({ answer: 'LATE ANSWER', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    expect(analytics.copilotAnswerCompleted).not.toHaveBeenCalled()
  })

  it('says what the Copilot is doing in a status line of its own, there before any question', async () => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    renderRail({ open: true })
    // Before any question the rail's line is the only status region, and it is empty.
    const line = screen.getByRole('status')
    expect(line).toBeEmptyDOMElement()
    // Every change to the line, in order: what a screen reader is given.
    const said: string[] = []
    const observer = new MutationObserver(() => said.push(line.textContent ?? ''))
    observer.observe(line, { childList: true, characterData: true, subtree: true })
    const ask = async (question: string) => {
      await user.type(screen.getByLabelText(/ask about this filing/i), `${question}{Enter}`)
      // The reading card is created with its words, so the card never says them: the line does, a frame later.
      await waitFor(() => expect(line).toHaveTextContent('Reading the filing…'))
    }

    await ask('What changed?')
    act(() => requests[0].onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    await ask('And margins?')
    act(() => requests[1].onError('The answer could not be checked.'))
    await waitFor(() => expect(said).toEqual([
      'Reading the filing…', 'Answer ready.',
      // The next question empties the line first, so the same words are heard again.
      '', 'Reading the filing…',
      // An error empties it: the card's alert says what went wrong.
      '',
    ]))
    observer.disconnect()
    expect(screen.getByRole('alert')).toHaveTextContent('The answer could not be checked.')
    expect(line).toBeInTheDocument()
  })

  it("empties its status line on a cancel and on a plan gate, whose sentence stays the reading card's", async () => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    const rail = renderRail({ open: true })
    const line = () => screen.getAllByRole('status').find((region) => region.classList.contains('sr-only'))!
    const ask = async (question: string) => {
      await user.type(screen.getByLabelText(/ask about this filing/i), `${question}{Enter}`)
      await waitFor(() => expect(line()).toHaveTextContent('Reading the filing…'))
    }

    // Closing the sheet mid-question cancels it: the reopened rail's line is empty, and the card shows the cancel.
    await ask('What changed?')
    rail.rerenderRail({ open: false })
    rail.rerenderRail({ open: true })
    expect(line()).toBeEmptyDOMElement()
    expect(screen.getByRole('alert')).toHaveTextContent('The question was cancelled. Please try again.')

    // A plan gate: the reading card's own region takes the plan card's sentence, so the line says nothing over it.
    await ask('And margins?')
    act(() => requests[1].onError('This is a Pro feature.'))
    expect(line()).toBeEmptyDOMElement()
    expect(screen.getAllByRole('status').find((region) => region !== line())).toHaveTextContent('This is a Pro feature.')
  })

  it.each([
    ['an answer', 'Answer ready.'],
    ['an error', ''],
    ['a cancel', ''],
  ])('drops the reading words still a frame away when %s comes first', async (ending, expected) => {
    let captured!: CopilotHandlers
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { captured = handlers })
    const rail = renderRail({ open: true })
    // Asked and ended in one task, so the frame that would say "Reading the filing…" has not run yet.
    fireEvent.change(screen.getByLabelText(/ask about this filing/i), { target: { value: 'What changed?' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    if (ending === 'an answer') {
      act(() => captured.onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    } else if (ending === 'an error') {
      act(() => captured.onError('The answer could not be checked.'))
    } else {
      rail.rerenderRail({ open: false })
      rail.rerenderRail({ open: true })
    }
    await act(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    // The line is the one status region: a done answer has no role, an error or a cancel is the card's alert.
    expect(screen.getByRole('status').textContent).toBe(expected)
  })

})

describe("AskCopilotRail in the filing workspace's pane", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(askFilingStream).mockReset()
    mockGetUsage.mockReset()
    mockGetUsage.mockResolvedValue(PRO_USAGE)
    window.localStorage.clear()
  })

  /** The filing page's research pane, open on the Ask tab, with the rail embedded in it as the page mounts it: keyed
   *  by its filing, so `showFiling` mounts another filing's rail in the same pane. */
  function renderInPane() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(queryKeys.currentUser(), { id: 1 })
    const page = (filingId: number) => (
      <QueryClientProvider client={queryClient}>
        <FilingViewerProvider>
          <FilingWorkspace
            open
            onOpenChange={vi.fn()}
            summaryAvailable
            secUrl="https://www.sec.gov/Archives/edgar/data/320193/"
            copilotBody={<AskCopilotRail key={filingId} {...baseProps} filingId={filingId} open onOpenChange={vi.fn()} embedded />}
            filingBody={<div>The filing</div>}
          >
            <div>The summary</div>
          </FilingWorkspace>
        </FilingViewerProvider>
      </QueryClientProvider>
    )
    const utils = render(page(baseProps.filingId))
    return { ...utils, showFiling: (filingId: number) => utils.rerender(page(filingId)) }
  }

  it("says what it is doing in the pane's line, between the tabs and the panels, heard while the Filing tab shows", async () => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    renderInPane()
    // One status line, the pane's, and the rail keeps none of its own: in the shell, after the tabs and before both
    // panels, so hiding a panel never hides it.
    const line = screen.getByRole('status')
    expect(line).toHaveClass('sr-only')
    expect(line).toBeEmptyDOMElement()
    expect(line.parentElement).toBe(screen.getByRole('complementary', { name: 'Source' }))
    expect(line.compareDocumentPosition(screen.getByRole('tablist')) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    for (const panel of screen.getAllByRole('tabpanel')) {
      expect(line.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
    // Every change to the line, in order: what a screen reader is given.
    const said: string[] = []
    const observer = new MutationObserver(() => said.push(line.textContent ?? ''))
    observer.observe(line, { childList: true, characterData: true, subtree: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?{Enter}')
    await waitFor(() => expect(line).toHaveTextContent('Reading the filing…'))
    // The reader opens the filing while the answer is read. The Ask panel hides, and everything in it leaves the
    // accessibility tree; the line is in neither panel, so the answer is still heard.
    await user.click(screen.getByRole('tab', { name: /filing/i }))
    const askPanel = document.getElementById(PANE_PANEL_IDS.copilot)!
    expect(askPanel).toHaveClass('hidden')
    act(() => requests[0].onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    expect(line).toHaveTextContent('Answer ready.')
    expect(line.closest('.hidden, [hidden], [aria-hidden="true"]')).toBeNull()

    // Back on the Ask tab, the next question empties the line first, so the same words are heard again, and an error
    // empties it: the card's alert says what went wrong.
    await user.click(screen.getByRole('tab', { name: 'Ask' }))
    await user.type(screen.getByLabelText(/ask about this filing/i), 'And margins?{Enter}')
    await waitFor(() => expect(line).toHaveTextContent('Reading the filing…'))
    act(() => requests[1].onError('The answer could not be checked.'))
    await waitFor(() => expect(said).toEqual(['Reading the filing…', 'Answer ready.', '', 'Reading the filing…', '']))
    observer.disconnect()
    expect(screen.getByRole('alert')).toHaveTextContent('The answer could not be checked.')
    expect(screen.getAllByRole('status')).toEqual([line])
  })

  it.each([
    ['a failed answer', 'The answer could not be completed. Please try again.', 'Try again'],
    ['a plan gate', 'This is a Pro feature.', 'Upgrade to Pro'],
    [
      'the fair-use cap',
      "You've reached this month's fair-use limit of 1,000 Copilot questions. It resets at the start of next month.",
      null,
    ],
  ])("says %s in the pane's line when it lands while the Filing tab shows: the card's sentence, whole and alone", async (
    _ending, sentence, button,
  ) => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    renderInPane()
    const line = screen.getByRole('status')
    const said: string[] = []
    const observer = new MutationObserver(() => said.push(line.textContent ?? ''))
    observer.observe(line, { childList: true, characterData: true, subtree: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?{Enter}')
    await waitFor(() => expect(line).toHaveTextContent('Reading the filing…'))
    // The reader opens the filing, and the question ends while it shows. The card is in the hidden Ask panel, its
    // button with it, so the line says the card's sentence: no button's label and no prefix.
    await user.click(screen.getByRole('tab', { name: /filing/i }))
    act(() => requests[0].onError(sentence))
    expect(line.textContent).toBe(sentence)
    const askPanel = document.getElementById(PANE_PANEL_IDS.copilot)!
    expect(askPanel).toHaveClass('hidden')
    expect(askPanel).toHaveTextContent(sentence)
    if (button) expect(within(askPanel).getByRole('button', { name: button })).toBeInTheDocument()

    // Later tab switches say nothing more, then or a frame later: back on the Ask tab the card is in view.
    await user.click(screen.getByRole('tab', { name: 'Ask' }))
    await user.click(screen.getByRole('tab', { name: /filing/i }))
    await act(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    observer.disconnect()
    expect(said).toEqual(['Reading the filing…', sentence])
  })

  it("leaves the pane's line empty for an error that lands on the Ask tab: the tab showing when it lands decides", async () => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    renderInPane()
    const line = screen.getByRole('status')
    const said: string[] = []
    const observer = new MutationObserver(() => said.push(line.textContent ?? ''))
    observer.observe(line, { childList: true, characterData: true, subtree: true })

    await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?{Enter}')
    await waitFor(() => expect(line).toHaveTextContent('Reading the filing…'))
    // The reader looks at the filing mid-question and is back on the Ask tab when the question fails: the card's alert
    // is in view and says it, so the line says nothing over it.
    await user.click(screen.getByRole('tab', { name: /filing/i }))
    await user.click(screen.getByRole('tab', { name: 'Ask' }))
    act(() => requests[0].onError('The answer could not be completed. Please try again.'))
    await waitFor(() => expect(said).toEqual(['Reading the filing…', '']))
    observer.disconnect()
    expect(screen.getByRole('alert')).toHaveTextContent('The answer could not be completed. Please try again.')
  })

  it("empties the pane's line when the rail leaves, so another filing's conversation never sits under its words", async () => {
    const requests: CopilotHandlers[] = []
    vi.mocked(askFilingStream).mockImplementation(async (_id, _q, _h, handlers) => { requests.push(handlers) })
    const user = userEvent.setup()
    const pane = renderInPane()
    await user.type(screen.getByLabelText(/ask about this filing/i), 'What changed?{Enter}')
    act(() => requests[0].onComplete({ answer: 'Revenue grew.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    const line = screen.getByRole('status')
    expect(line).toHaveTextContent('Answer ready.')
    // The pane stays; the rail is the filing's, so another filing mounts a new one, with an empty conversation.
    pane.showFiling(43)
    expect(screen.queryByText('Revenue grew.')).toBeNull()
    expect(screen.getByRole('status')).toBe(line)
    expect(line).toBeEmptyDOMElement()
  })

  it('drops a question\'s words still a frame away when the rail leaves, so they never land under the next rail', async () => {
    vi.mocked(askFilingStream).mockImplementation(async () => {})
    const pane = renderInPane()
    const line = screen.getByRole('status')
    // Asked and left in one task, so the frame that would say "Reading the filing…" has not run yet.
    fireEvent.change(screen.getByLabelText(/ask about this filing/i), { target: { value: 'What changed?' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    pane.showFiling(43)
    await act(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    expect(screen.getByRole('status')).toBe(line)
    expect(line.textContent).toBe('')
  })

  it("puts the pane's line inside the sheet's dialog below lg, where everything outside the dialog is unheard", () => {
    const matchMedia = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(max-width: 1023.98px)',
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          onchange: null,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    )
    try {
      renderInPane()
      const sheet = screen.getByRole('dialog', { name: 'Source' })
      expect(sheet).toHaveAttribute('aria-modal', 'true')
      expect(sheet).toContainElement(screen.getByRole('status'))
    } finally {
      matchMedia.mockRestore()
    }
  })
})

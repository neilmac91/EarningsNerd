import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'
import type { CopilotHandlers } from '@/features/filings/api/copilot-api'
import { SummaryActionsBar, type SaveMutation } from '@/features/summaries/components/SummaryActionsBar'
import CopilotComposer from '@/features/filings/components/copilot/CopilotComposer'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'
import NarrativePane, { type NarrativeState } from '@/features/analysis/components/NarrativePane'

/**
 * Filing controls keep keyboard focus while their own request is in flight and through
 * the state that request leaves behind (a cleared composer, a saved summary). They are aria-disabled
 * (+ aria-busy via the DS Button's `loading`) with an early return, never natively `disabled`:
 * Chromium blurs a focused control that turns `disabled` to <body>. jsdom does not blur disabled
 * elements, so these specs pin the attributes, that focus is never moved off the control, and that
 * a second activation (click, Enter) sends no second request.
 *
 * A control its own activation removes (Save → the Saved chip, a starter / follow-up / Retry → the
 * turn it starts, Refresh → the restarted stream) hands focus to what stays in its place first.
 * jsdom does drop focus to <body> when the focused node is removed, so those cases pin the landing.
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  getUsage: vi.fn(),
  askFilingStream: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: api.getSubscriptionStatus,
  getUsage: api.getUsage,
}))
vi.mock('@/features/filings/api/copilot-api', async () => ({
  ...(await vi.importActual<typeof import('@/features/filings/api/copilot-api')>('@/features/filings/api/copilot-api')),
  askFilingStream: api.askFilingStream,
}))
vi.mock('@/lib/analytics', () => {
  const analytics = {
    filingLinkCopied: vi.fn(),
    analysisRun: vi.fn(),
    exportGenerated: vi.fn(),
    paywallPromptShown: vi.fn(),
    paywallCtaClicked: vi.fn(),
    copilotQuestionAsked: vi.fn(),
    copilotAnswerCompleted: vi.fn(),
    copilotAnswerErrored: vi.fn(),
  }
  return { default: analytics, analytics }
})
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}

const proUser: CurrentUser = {
  id: 1, email: 'a@example.test', full_name: 'A', is_pro: true, is_beta: false, is_admin: false, email_verified: true,
}

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

/** Flush the microtasks a request would be issued on, so a second request would be counted. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

/** In flight: announced busy + unavailable, still focusable, and still the focused element. */
/** Busy is announced (aria-busy + aria-disabled) and the control keeps focus. That a busy flag
    never turns it natively disabled is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(document.activeElement).toBe(control)
}

/** Unavailable (no aria-busy: nothing of its own in flight), still focusable, still focused. */
function expectUnavailableAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(control).not.toBeDisabled()
  expect(document.activeElement).toBe(control)
}

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('SummaryActionsBar Save Summary', () => {
  it('stays focused and busy while the save is in flight, and refuses a second click or Enter', async () => {
    const ui = (saveMutation: SaveMutation) => (
      <SummaryActionsBar
        filingId={7}
        summaryId={11}
        isAuthenticated
        isSaved={false}
        saveMutation={saveMutation}
        isPro={false}
        onExportPdf={() => {}}
        onExportCsv={() => {}}
      />
    )
    const mutate = vi.fn()
    const view = render(ui({ mutate, isPending: false }))
    const save = screen.getByRole('button', { name: /save summary/i })
    save.focus()
    fireEvent.click(save)
    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate).toHaveBeenCalledWith(11)

    // The filing view's mutation is now pending.
    view.rerender(ui({ mutate, isPending: true }))
    expectBusyAndFocused(save)
    fireEvent.click(save)
    await userEvent.setup().keyboard('{Enter}')
    expect(mutate).toHaveBeenCalledTimes(1)

    // Settles without saving (an error): Save is live again and never lost focus.
    view.rerender(ui({ mutate, isPending: false }))
    expect(save).not.toHaveAttribute('aria-disabled')
    expect(save).not.toHaveAttribute('aria-busy')
    expect(document.activeElement).toBe(save)
  })

  it('lands focus on the Saved chip that replaces it after its own save succeeds', async () => {
    const ui = (saveMutation: SaveMutation, isSaved: boolean) => (
      <SummaryActionsBar
        filingId={7}
        summaryId={11}
        isAuthenticated
        isSaved={isSaved}
        saveMutation={saveMutation}
        isPro={false}
        onExportPdf={() => {}}
        onExportCsv={() => {}}
      />
    )
    const mutate = vi.fn()
    const view = render(ui({ mutate, isPending: false }, false))
    screen.getByRole('button', { name: /save summary/i }).focus()
    await userEvent.setup().keyboard('{Enter}')
    expect(mutate).toHaveBeenCalledTimes(1)
    view.rerender(ui({ mutate, isPending: true }, false))
    // The save settles and the saved status refetches: Save unmounts for the Saved chip.
    view.rerender(ui({ mutate, isPending: false }, true))
    expect(screen.queryByRole('button', { name: /save summary/i })).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByText('Saved'))
    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it('an already-saved summary never takes focus', () => {
    render(
      <SummaryActionsBar
        filingId={7}
        summaryId={11}
        isAuthenticated
        isSaved
        saveMutation={{ mutate: vi.fn(), isPending: false }}
        isPro={false}
        onExportPdf={() => {}}
        onExportCsv={() => {}}
      />,
    )
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(document.activeElement).toBe(document.body)
  })
})

describe('CopilotComposer Send', () => {
  it('keeps focus through the cleared input and the stream it started, and refuses a second send', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const view = render(<CopilotComposer onSubmit={onSubmit} locked={false} />)
    const textarea = screen.getByLabelText(/ask about this filing/i)
    const send = screen.getByRole('button', { name: /^send$/i })

    // Empty input: unavailable but focusable — the state a send lands back in.
    expect(send).toHaveAttribute('aria-disabled', 'true')
    expect(send).not.toBeDisabled()

    await user.type(textarea, 'What changed?')
    expect(send).not.toHaveAttribute('aria-disabled')
    await user.click(send)
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('What changed?')
    // Its own press cleared the input — the flip native `disabled` would blur.
    expect(textarea).toHaveValue('')
    expectUnavailableAndFocused(send)

    // The rail is streaming the answer.
    view.rerender(<CopilotComposer onSubmit={onSubmit} locked />)
    expectUnavailableAndFocused(send)
    await user.click(send)
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)

    // A queued question can neither be sent with the button nor Enter-submitted mid-stream.
    await user.type(textarea, 'Next question')
    await user.keyboard('{Enter}')
    await user.click(send)
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(textarea).toHaveValue('Next question')
    expectUnavailableAndFocused(send)

    // Stream settles: Send is live again (the queued text is still there) and still focused.
    view.rerender(<CopilotComposer onSubmit={onSubmit} locked={false} />)
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(send)
  })
})

const PRO_USAGE: Usage = {
  summaries_used: 0, summaries_limit: null, is_pro: true, month: '2026-10', qa_used: 3, qa_limit: 1000,
  copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50,
}

/** An open PRO rail whose stream stays in flight until the test settles it through `handlers()`. */
async function renderProRail() {
  api.getCurrentUserSafe.mockResolvedValue(proUser)
  api.getUsage.mockResolvedValue(PRO_USAGE)
  let handlers: CopilotHandlers | undefined
  api.askFilingStream.mockImplementation(async (_id: number, _q: string, _h: unknown, h: CopilotHandlers) => {
    handlers = h
  })
  renderWithClient(
    <AskCopilotRail
      filingId={42}
      filingType="10-Q"
      ticker="AAPL"
      companyName="Apple Inc."
      summaryAvailable
      isPro
      isAuthenticated
      open
      onOpenChange={() => {}}
    />,
  )
  const textarea = screen.getByLabelText(/ask about this filing/i)
  // The rail focuses its composer on open (next frame); let that land before the test moves focus.
  await waitFor(() => expect(textarea).toHaveFocus())
  return {
    textarea,
    send: screen.getByRole('button', { name: /^send$/i }),
    handlers: () => {
      if (!handlers) throw new Error('no question was asked')
      return handlers
    },
  }
}

describe('AskCopilotRail Send (rail wiring)', () => {
  it('keeps focus on Send while the answer streams and sends exactly one request', async () => {
    const user = userEvent.setup()
    const { textarea, send, handlers } = await renderProRail()

    await user.type(textarea, 'What changed?')
    await user.click(send)
    expect(api.askFilingStream).toHaveBeenCalledTimes(1)
    expectUnavailableAndFocused(send)

    await user.click(send)
    await user.keyboard('{Enter}')
    await user.type(textarea, 'Next question')
    await user.keyboard('{Enter}')
    await user.click(send)
    await settle()
    expect(api.askFilingStream).toHaveBeenCalledTimes(1)
    expectUnavailableAndFocused(send)

    act(() => handlers().onComplete({ answer: 'Revenue rose.', citations: [], grounded: 0, kind: 'answer', followups: [] }))
    expect(screen.getByText('Revenue rose.')).toBeInTheDocument()
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(send)
  })
})

describe('AskCopilotRail conversation controls replaced by the turn they start', () => {
  it('a starter pressed from the keyboard hands focus to the composer and asks once', async () => {
    const user = userEvent.setup()
    const { textarea } = await renderProRail()
    await user.tab({ shift: true })
    const starter = screen.getByRole('button', { name: 'Any changes to guidance?' })
    expect(document.activeElement).toBe(starter)

    await user.keyboard('{Enter}')
    expect(api.askFilingStream).toHaveBeenCalledTimes(1)
    expect(api.askFilingStream.mock.calls[0][1]).toBe('Any changes to guidance?')
    expect(starter).not.toBeInTheDocument()
    expect(document.activeElement).toBe(textarea)

    // Mid-stream, Enter in the composer it landed on sends nothing.
    await user.keyboard('{Enter}')
    await settle()
    expect(api.askFilingStream).toHaveBeenCalledTimes(1)
  })

  it('a pointer-pressed starter does not pull focus into the composer (no touch keyboard)', async () => {
    const user = userEvent.setup()
    const { textarea } = await renderProRail()
    textarea.blur()
    await user.click(screen.getByRole('button', { name: 'Any changes to guidance?' }))
    expect(api.askFilingStream).toHaveBeenCalledTimes(1)
    expect(document.activeElement).not.toBe(textarea)
  })

  it('an Ask next chip pressed from the keyboard hands focus to the composer and asks once', async () => {
    const user = userEvent.setup()
    const { textarea, handlers } = await renderProRail()
    await user.type(textarea, 'What changed?{Enter}')
    act(() => handlers().onComplete({
      answer: 'Revenue rose.', citations: [], grounded: 0, kind: 'answer', followups: ['What drove margins?'],
    }))
    textarea.focus()
    await user.tab({ shift: true })
    const chip = screen.getByRole('button', { name: /what drove margins\?/i })
    expect(document.activeElement).toBe(chip)

    await user.keyboard('{Enter}')
    expect(api.askFilingStream).toHaveBeenCalledTimes(2)
    expect(api.askFilingStream.mock.calls[1][1]).toBe('What drove margins?')
    expect(chip).not.toBeInTheDocument()
    expect(document.activeElement).toBe(textarea)
  })

  it('Retry pressed from the keyboard hands focus to the composer and re-asks once', async () => {
    const user = userEvent.setup()
    const { textarea, handlers } = await renderProRail()
    await user.type(textarea, 'What changed?{Enter}')
    act(() => handlers().onError('The connection dropped.'))
    textarea.focus()
    await user.tab({ shift: true })
    const retry = screen.getByRole('button', { name: /retry/i })
    expect(document.activeElement).toBe(retry)

    await user.keyboard('{Enter}')
    expect(api.askFilingStream).toHaveBeenCalledTimes(2)
    expect(api.askFilingStream.mock.calls[1][1]).toBe('What changed?')
    expect(retry).not.toBeInTheDocument()
    expect(document.activeElement).toBe(textarea)
  })
})

const doneNarrative: NarrativeState = {
  status: 'done',
  text: 'Revenue grew.',
  completion: {
    kind: 'analysis', analysis_id: 7, narrative: 'Revenue grew.', citations: [], grounded: 0,
    unverified: 0, cached: false, n_periods: 6,
  },
}

describe('NarrativePane Refresh analysis', () => {
  it('hands focus to the pane heading when its own restart unmounts it', async () => {
    const onRefresh = vi.fn()
    const view = render(<NarrativePane state={doneNarrative} onRefresh={onRefresh} refreshDisabled={false} />)
    screen.getByRole('button', { name: /refresh analysis/i }).focus()
    await userEvent.setup().keyboard('{Enter}')
    expect(onRefresh).toHaveBeenCalledTimes(1)

    // The page restarts the stream: the action row (and Refresh with it) unmounts.
    view.rerender(
      <NarrativePane state={{ status: 'streaming', text: '', stage: 'assembling' }} onRefresh={onRefresh} refreshDisabled />,
    )
    expect(screen.queryByRole('button', { name: /refresh analysis/i })).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'AI trend analysis' }))
  })

  it('refreshDisabled leaves it focusable and busy, and refuses a click or Enter', async () => {
    const onRefresh = vi.fn()
    render(<NarrativePane state={doneNarrative} onRefresh={onRefresh} refreshDisabled />)
    const refresh = screen.getByRole('button', { name: /refresh analysis/i })
    refresh.focus()
    expectBusyAndFocused(refresh)
    fireEvent.click(refresh)
    await userEvent.setup().keyboard('{Enter}')
    expect(onRefresh).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(refresh)
  })
})

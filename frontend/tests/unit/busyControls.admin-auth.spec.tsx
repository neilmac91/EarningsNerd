import React from 'react'
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// A control busy with its own request (or flipped by its own success) stays focusable:
// aria-disabled plus an early return, never native `disabled`. Chromium blurs a focused element
// that turns disabled and jsdom does not, so these cases pin the attributes, the kept focus, and
// that a second activation fires no second request (lessons/frontend-busy-controls-stay-focusable.md).

const { usePathname, useSearchParams } = vi.hoisted(() => ({
  usePathname: vi.fn<() => string>(),
  useSearchParams: vi.fn<() => URLSearchParams>(),
}))
vi.mock('next/navigation', () => ({ usePathname, useSearchParams, useRouter: () => ({ refresh: vi.fn() }) }))

vi.mock('@/features/admin/api/admin-api', () => ({
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  resendInvite: vi.fn(),
  revokeInvite: vi.fn(),
  updateFeedbackStatus: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: vi.fn(),
  resendVerification: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
// Chrome around the units under test: AuthShell's theme toggle, SiteChrome's header/footer.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/Header', () => ({ default: () => null }))
vi.mock('@/components/Footer', () => ({ default: () => null }))

import AdminInvitesPage from '@/app/admin/invites/page'
import CheckEmailPage from '@/app/check-email/page'
import FeedbackRow from '@/features/admin/components/FeedbackRow'
import VerificationBanner from '@/features/auth/components/VerificationBanner'
import EmailVerificationModal from '@/features/auth/components/EmailVerificationModal'
import {
  createInvite,
  listInvites,
  updateFeedbackStatus,
  type FeedbackRecord,
  type InviteRecord,
  type MintResult,
} from '@/features/admin/api/admin-api'
import { getCurrentUserSafe, resendVerification } from '@/features/auth/api/auth-api'
import { toast } from 'sonner'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError, EMAIL_VERIFICATION_REQUIRED_EVENT } from '@/lib/api/client'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function withQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

/** Unavailable after its own success (cooldown, nothing to send): aria-disabled, never natively
    disabled, and still focused. The rule-12 gate cannot see these states, so they are pinned here. */
function expectInertButFocused(el: HTMLElement) {
  expect(el).toHaveAttribute('aria-disabled', 'true')
  expect(el).not.toBeDisabled()
  expect(el).toHaveFocus()
}

/** Busy with its own request: announced and still focused. That a busy flag never turns it natively
    disabled is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(el: HTMLElement) {
  expect(el).toHaveAttribute('aria-busy', 'true')
  expect(el).toHaveAttribute('aria-disabled', 'true')
  expect(el).toHaveFocus()
}

describe('Admin invites: Send invites stays focusable', () => {
  const minted: MintResult = {
    id: 9,
    email: 'good@example.com',
    invite_link: 'https://earningsnerd.io/invite/token',
    expires_at: '2026-07-08T00:00:00Z',
    emailed: true,
    cohort: null,
  }
  const pendingGood: InviteRecord = {
    id: 9,
    email: 'good@example.com',
    status: 'pending',
    cohort: null,
    expires_at: '2026-07-08T00:00:00Z',
    used_at: null,
    user_id: null,
    created_at: '2026-07-01T00:00:00Z',
  }

  beforeEach(() => {
    vi.mocked(listInvites).mockReset()
    vi.mocked(createInvite).mockReset()
    vi.mocked(toast.success).mockReset()
    vi.mocked(toast.error).mockReset()
  })

  async function stageOneAddress() {
    withQueryClient(<AdminInvitesPage />)
    const field = screen.getByLabelText('Email addresses')
    fireEvent.change(field, { target: { value: 'good@example.com' } })
    fireEvent.blur(field)
    await waitFor(() => expect(screen.getByText(/to invite/).textContent).toMatch(/^1 to invite/))
    return screen.getByRole('button', { name: 'Send invites' })
  }

  it('keeps Send focused but inert while the batch is in flight', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    const mint = deferred<MintResult>()
    vi.mocked(createInvite).mockReturnValue(mint.promise)
    const user = userEvent.setup()
    const send = await stageOneAddress()

    await user.click(send)

    expect(send).toHaveAttribute('aria-busy', 'true')
    expect(send).toHaveTextContent('Sending…')
    expectBusyAndFocused(send)
    await user.click(send)
    await user.keyboard('{Enter}')
    expect(createInvite).toHaveBeenCalledTimes(1)

    mint.resolve(minted)
    await waitFor(() => expect(send).not.toHaveAttribute('aria-busy'))
    expect(send).toHaveFocus()
    expect(send).not.toBeDisabled()
  })

  it('stays busy until the post-send refetch lands, so a second Enter mints nothing twice', async () => {
    const refetch = deferred<InviteRecord[]>()
    vi.mocked(listInvites).mockResolvedValueOnce([]).mockReturnValueOnce(refetch.promise)
    vi.mocked(createInvite).mockResolvedValue(minted)
    const user = userEvent.setup()
    const send = await stageOneAddress()

    await user.click(send)
    await waitFor(() => expect(listInvites).toHaveBeenCalledTimes(2))
    // The mint has resolved; the list that marks the address invited has not.
    expectBusyAndFocused(send)
    await user.keyboard('{Enter}')
    await user.click(send)
    expect(createInvite).toHaveBeenCalledTimes(1)

    await act(async () => refetch.resolve([pendingGood]))
    await waitFor(() => expect(send).not.toHaveAttribute('aria-busy'))
    expectInertButFocused(send)
    expect(createInvite).toHaveBeenCalledTimes(1)
  })

  it('keeps Send focused when an all-success send leaves nothing to send', async () => {
    // The post-send refetch lists the new invite as pending, so its chip turns "already invited".
    vi.mocked(listInvites).mockResolvedValueOnce([]).mockResolvedValue([pendingGood])
    vi.mocked(createInvite).mockResolvedValue(minted)
    const user = userEvent.setup()
    const send = await stageOneAddress()

    await user.click(send)

    await waitFor(() => expect(screen.getByText(/to invite/).textContent).toMatch(/^0 to invite/))
    expect(send).not.toHaveAttribute('aria-busy')
    expectInertButFocused(send)
    await user.click(send)
    await user.keyboard('{Enter}')
    expect(createInvite).toHaveBeenCalledTimes(1)
    // Only the early return stops a no-op send now: without it this run would clear the batch's
    // results (and their invite links) and relist the just-sent address as skipped.
    expect(screen.getByText('1 invite sent')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy link' })).toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledTimes(1)
  })

  it('makes an activation with nothing entered a no-op', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    const user = userEvent.setup()
    withQueryClient(<AdminInvitesPage />)
    await screen.findByText(/No invites yet/)
    const send = screen.getByRole('button', { name: 'Send invites' })

    await user.click(send)
    await user.keyboard('{Enter}')

    expectInertButFocused(send)
    expect(send).not.toHaveAttribute('aria-busy')
    // No "0 invites sent" toast and no post-send refetch of the list.
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.error).not.toHaveBeenCalled()
    expect(listInvites).toHaveBeenCalledTimes(1)
  })
})

describe('Admin feedback: the row status select stays focusable', () => {
  const bugReport: FeedbackRecord = {
    id: 1,
    user_id: 42,
    user_email: 'alice@example.com',
    type: 'bug',
    message: 'The summary export button does nothing on Safari.',
    page_url: '/filing/123',
    status: 'new',
    created_at: '2026-06-20T00:00:00Z',
  }

  beforeEach(() => {
    vi.mocked(updateFeedbackStatus).mockReset()
  })

  it('keeps the select focused but inert through its update and the list refetch after it', async () => {
    const update = deferred<FeedbackRecord>()
    vi.mocked(updateFeedbackStatus).mockReturnValue(update.promise)
    const refetched = deferred<FeedbackRecord[]>()
    const listFeedback = vi
      .fn<() => Promise<FeedbackRecord[]>>()
      .mockResolvedValueOnce([bugReport])
      .mockReturnValueOnce(refetched.promise)
    // The admin page's list query: the select's value is the row's status from this list.
    function FeedbackTable() {
      const { data } = useQuery({ queryKey: queryKeys.adminFeedback.list({}), queryFn: listFeedback })
      return (
        <table>
          <tbody>
            {data?.map((record) => <FeedbackRow key={record.id} feedback={record} />)}
          </tbody>
        </table>
      )
    }
    const user = userEvent.setup()
    withQueryClient(<FeedbackTable />)
    const select = (await screen.findByLabelText('Set status for feedback 1')) as HTMLSelectElement
    select.focus()

    await user.selectOptions(select, 'triaged')

    await waitFor(() => expect(select).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(select)
    await user.selectOptions(select, 'resolved')
    expect(updateFeedbackStatus).toHaveBeenCalledTimes(1)
    expect(updateFeedbackStatus).toHaveBeenCalledWith(1, 'triaged')
    // The guarded change is a no-op: the controlled value stays on the row's status.
    expect(select.value).toBe('new')

    // Updated, but the list has not refetched, so the select still shows the old status: it stays
    // busy, and another change sends nothing until the refetched row catches up.
    await act(async () => update.resolve({ ...bugReport, status: 'triaged' }))
    await waitFor(() => expect(listFeedback).toHaveBeenCalledTimes(2))
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
    expectBusyAndFocused(select)
    await user.selectOptions(select, 'resolved')
    expect(updateFeedbackStatus).toHaveBeenCalledTimes(1)

    await act(async () => refetched.resolve([{ ...bugReport, status: 'triaged' }]))
    await waitFor(() => expect(select).not.toHaveAttribute('aria-busy'))
    expect(select.value).toBe('triaged')
    expect(select).not.toHaveAttribute('aria-disabled')
    expect(select).toHaveFocus()
  })
})

describe('Check email: Resend stays focusable', () => {
  beforeEach(() => {
    vi.mocked(resendVerification).mockReset()
  })

  it('keeps Resend focused but inert in flight and through the cooldown', async () => {
    useSearchParams.mockReturnValue(new URLSearchParams('email=new@example.com'))
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    render(<CheckEmailPage />)
    const resend = screen.getByRole('button', { name: 'Resend email' })

    await user.click(resend)

    expect(resend).toHaveAttribute('aria-busy', 'true')
    expectBusyAndFocused(resend)
    await user.click(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)

    sent.resolve({})
    // The cooldown follows this button's own success; it must not turn natively disabled.
    await waitFor(() => expect(resend).toHaveTextContent(/^Resend in \d+s$/))
    expect(resend).not.toHaveAttribute('aria-busy')
    expectInertButFocused(resend)
    await user.click(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)
  })

  it('keeps Resend natively disabled when the URL carries no email', () => {
    useSearchParams.mockReturnValue(new URLSearchParams(''))
    render(<CheckEmailPage />)
    expect(screen.getByRole('button', { name: 'Resend email' })).toBeDisabled()
  })
})

describe('Verification banner: Resend link stays focusable', () => {
  beforeEach(() => {
    sessionStorage.clear()
    usePathname.mockReturnValue('/dashboard')
    vi.mocked(resendVerification).mockReset()
    vi.mocked(getCurrentUserSafe).mockResolvedValue({
      id: 7,
      email: 'unverified@example.com',
      full_name: null,
      is_pro: false,
      is_beta: false,
      is_admin: false,
      email_verified: false,
    })
  })

  it('keeps Resend link focused but inert while its request is in flight', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    withQueryClient(<VerificationBanner />)
    const resend = await screen.findByRole('button', { name: 'Resend link' })

    await user.click(resend)

    expect(resend).toHaveAttribute('aria-busy', 'true')
    expectBusyAndFocused(resend)
    await user.click(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)

    // A failed resend keeps the button (success swaps it for the "sent" line by design).
    sent.reject(new Error('network'))
    await waitFor(() => expect(resend).not.toHaveAttribute('aria-busy'))
    expect(resend).not.toHaveAttribute('aria-disabled')
    expect(resend).toHaveFocus()
  })

  it('hands focus to the sent line when a successful resend removes the button', async () => {
    vi.mocked(resendVerification).mockResolvedValue({})
    const user = userEvent.setup()
    withQueryClient(<VerificationBanner />)
    const resend = await screen.findByRole('button', { name: 'Resend link' })

    await user.click(resend)

    const sentLine = await screen.findByText('Verification email sent. Check your inbox.')
    expect(resend).not.toBeInTheDocument()
    expect(sentLine).toHaveFocus()
  })

  it('leaves focus alone when it moved off Resend link before the resend succeeded', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    withQueryClient(<VerificationBanner />)
    const resend = await screen.findByRole('button', { name: 'Resend link' })

    await user.click(resend)
    await user.tab()
    const dismiss = screen.getByRole('button', { name: 'Dismiss' })
    expect(dismiss).toHaveFocus()

    sent.resolve({})
    await screen.findByText('Verification email sent. Check your inbox.')
    expect(dismiss).toHaveFocus()
  })
})

describe('Email verification modal: Resend link stays focusable', () => {
  beforeEach(() => {
    vi.mocked(resendVerification).mockReset()
    vi.mocked(getCurrentUserSafe).mockResolvedValue({
      id: 7,
      email: 'unverified@example.com',
      full_name: null,
      is_pro: false,
      is_beta: false,
      is_admin: false,
      email_verified: false,
    })
  })

  const prompt = () => act(() => { window.dispatchEvent(new Event(EMAIL_VERIFICATION_REQUIRED_EVENT)) })

  async function openPrompt() {
    prompt()
    // The address comes from the current-user query; wait for it so Resend has an email to send to.
    await screen.findByText('unverified@example.com')
    return screen.getByRole('button', { name: 'Resend link' })
  }

  it('keeps Resend link focused but inert while its request is in flight', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    const resend = await openPrompt()

    resend.focus()
    await user.keyboard('{Enter}')

    expectBusyAndFocused(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)
    sent.resolve({})
    await screen.findByRole('button', { name: 'Link sent' })
  })

  it('keeps Link sent focused but unavailable after its own success, and announces the send', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    const resend = await openPrompt()
    // The live region is mounted and empty before the send, so the sent line is announced.
    const status = screen.getByRole('status')
    expect(status).toBeEmptyDOMElement()

    resend.focus()
    await user.keyboard('{Enter}')
    sent.resolve({})

    await waitFor(() => expect(resend).toHaveAccessibleName('Link sent'))
    expect(resend).not.toHaveAttribute('aria-busy')
    expectInertButFocused(resend)
    expect(screen.getByRole('status')).toBe(status)
    expect(status).toHaveTextContent('New link sent. Only the newest link works.')
    await user.keyboard('{Enter}')
    await user.click(resend)
    expect(resendVerification).toHaveBeenCalledTimes(1)
  })

  it('announces a failed resend and leaves Resend link live; a repeat failure is announced again', async () => {
    const first = deferred<unknown>()
    const second = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    const resend = await openPrompt()

    resend.focus()
    await user.keyboard('{Enter}')
    first.reject(new ApiError(503, 'Service temporarily unavailable. Please try again in a moment.'))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't send a new link")
    expect(alert).toHaveTextContent('Please try again in a moment.')
    expect(resend).not.toHaveAttribute('aria-disabled')
    expect(resend).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    second.reject(new ApiError(503, 'Service temporarily unavailable. Please try again in a moment.'))
    // Re-inserted, not reused: a role="alert" whose text does not change is not announced again.
    expect(await screen.findByRole('alert')).not.toBe(alert)
    expect(resend).toHaveFocus()
  })

  it('keeps Resend link focused but unavailable after a 429, and says what to do', async () => {
    vi.mocked(resendVerification).mockRejectedValue(
      new ApiError(429, 'Too many resend requests. Please wait before trying again.'),
    )
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    const resend = await openPrompt()

    resend.focus()
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We've sent several links recently. Use the newest one, or try again later.",
    )
    expect(resend).toHaveAccessibleName('Resend link')
    expectInertButFocused(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)
  })

  it('re-arms Resend only for a new prompt: never under a send in flight, never while the dialog stays open', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValueOnce(sent.promise).mockResolvedValueOnce({})
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    let resend = await openPrompt()

    resend.focus()
    await user.keyboard('{Enter}')
    // A second gated 403 while the first send is in flight: still busy, so a press sends nothing.
    prompt()
    expect(resend).toHaveAttribute('aria-busy', 'true')
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)
    sent.resolve({})
    await screen.findByRole('button', { name: 'Link sent' })

    // Another while the dialog is still open is the same prompt: the fresh link is not replaced.
    prompt()
    expect(resend).toHaveAccessibleName('Link sent')
    expectInertButFocused(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    resend = await openPrompt()
    expect(resend).not.toHaveAttribute('aria-disabled')
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
    resend.focus()
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(2)
    await screen.findByRole('button', { name: 'Link sent' })
  })

  it('a prompt reopened while the last send is still in flight keeps Resend busy, so it cannot send twice', async () => {
    const sent = deferred<unknown>()
    vi.mocked(resendVerification).mockReturnValue(sent.promise)
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    const first = await openPrompt()

    first.focus()
    await user.keyboard('{Enter}')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    prompt()
    const resend = await screen.findByRole('button', { name: /Sending/ })
    resend.focus()
    expectBusyAndFocused(resend)
    await user.keyboard('{Enter}')
    expect(resendVerification).toHaveBeenCalledTimes(1)
    sent.resolve({})
    await screen.findByRole('button', { name: 'Link sent' })
  })

  it('reads sensibly before the address loads, and Resend sends nothing without one', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    const user = userEvent.setup()
    withQueryClient(<EmailVerificationModal />)
    prompt()

    expect(await screen.findByText('your email address')).toBeInTheDocument()
    const resend = screen.getByRole('button', { name: 'Resend link' })
    resend.focus()
    await user.keyboard('{Enter}')
    expect(resendVerification).not.toHaveBeenCalled()
    expect(resend).toHaveFocus()
  })
})

import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// A control busy with its own request (or flipped by its own success) stays focusable:
// aria-disabled plus an early return, never native `disabled`. Chromium blurs a focused element
// that turns disabled and jsdom does not, so these cases pin the attributes, the kept focus, and
// that a second activation fires no second request (lessons/frontend-busy-controls-stay-focusable.md).

const { usePathname, useSearchParams } = vi.hoisted(() => ({
  usePathname: vi.fn<() => string>(),
  useSearchParams: vi.fn<() => URLSearchParams>(),
}))
vi.mock('next/navigation', () => ({ usePathname, useSearchParams }))

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

/** Busy-but-focusable: announced unavailable, never natively disabled, still holding focus. */
function expectInertButFocused(el: HTMLElement) {
  expect(el).toHaveAttribute('aria-disabled', 'true')
  expect(el).not.toBeDisabled()
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
    expectInertButFocused(send)
    await user.click(send)
    await user.keyboard('{Enter}')
    expect(createInvite).toHaveBeenCalledTimes(1)

    mint.resolve(minted)
    await waitFor(() => expect(send).not.toHaveAttribute('aria-busy'))
    expect(send).toHaveFocus()
    expect(send).not.toBeDisabled()
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

  it('keeps the select focused but inert while its update is in flight', async () => {
    const update = deferred<FeedbackRecord>()
    vi.mocked(updateFeedbackStatus).mockReturnValue(update.promise)
    const user = userEvent.setup()
    withQueryClient(
      <table>
        <tbody>
          <FeedbackRow feedback={bugReport} />
        </tbody>
      </table>,
    )
    const select = screen.getByLabelText('Set status for feedback 1') as HTMLSelectElement
    select.focus()

    await user.selectOptions(select, 'triaged')

    await waitFor(() => expect(select).toHaveAttribute('aria-busy', 'true'))
    expectInertButFocused(select)
    await user.selectOptions(select, 'resolved')
    expect(updateFeedbackStatus).toHaveBeenCalledTimes(1)
    expect(updateFeedbackStatus).toHaveBeenCalledWith(1, 'triaged')
    // The guarded change is a no-op: the controlled value stays on the row's status.
    expect(select.value).toBe('new')

    update.resolve({ ...bugReport, status: 'triaged' })
    await waitFor(() => expect(select).not.toHaveAttribute('aria-busy'))
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
    expectInertButFocused(resend)
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
    expectInertButFocused(resend)
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

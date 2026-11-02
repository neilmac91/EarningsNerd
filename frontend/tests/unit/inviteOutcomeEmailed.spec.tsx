import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * The admin invite surfaces say what happened to each invite: it was created, and its email was accepted by the
 * email provider only when "Email invites" was on and the provider took it (the API's `emailed` flag, admin.py).
 * An acceptance is never a delivery, so nothing says an email was "sent" or "delivered" (audit ADM-01, ADM-02, ADM-03;
 * EN-BETA PB-01). "Email invites" is off by default, and on it carries the recipient's recorded request.
 */

vi.mock('@/features/admin/api/admin-api', async (original) => ({
  ...(await original<typeof import('@/features/admin/api/admin-api')>()),
  getInviteReadiness: vi.fn(),
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  resendInvite: vi.fn(),
  revokeInvite: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import AdminInvitesPage from '@/app/admin/invites/page'
import ResendShareModal from '@/features/admin/components/ResendShareModal'
import {
  createInvite,
  getInviteReadiness,
  listInvites,
  type CreateInviteInput,
  type MintResult,
} from '@/features/admin/api/admin-api'
import { toast } from 'sonner'
import { READY } from './fixtures/inviteReadiness'

/** A minted invite: emailed, the provider took it; asked to email and not taken, the send failed. */
const mint = (email: string, emailed: boolean, asked = true): MintResult => ({
  id: email.length,
  email,
  invite_link: `https://earningsnerd.io/invite/${email.split('@')[0]}`,
  expires_at: '2026-07-08T00:00:00Z',
  emailed,
  cohort: null,
  delivery_status: emailed ? 'accepted' : asked ? 'failed' : null,
})

/** Every toast the run raised, as text. */
const toasts = () =>
  [toast.success, toast.warning, toast.error].flatMap((fn) => vi.mocked(fn).mock.calls.map((call) => String(call[0])))

/** Send a batch. Email is off by default; `email` ticks it and records the recipient's request (how they asked). */
async function sendBatch(addresses: string, { email = false } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AdminInvitesPage />
    </QueryClientProvider>,
  )
  await screen.findByText(/No invites yet/i)
  const user = userEvent.setup()
  const box = screen.getByRole('checkbox', { name: /Email invites/ })
  await waitFor(() => expect(box).not.toHaveAttribute('aria-disabled'))
  expect(box).not.toBeChecked()
  if (email) {
    await user.click(box)
    await user.selectOptions(screen.getByLabelText('How they asked'), 'email')
  }
  const field = screen.getByLabelText('Email addresses')
  fireEvent.change(field, { target: { value: addresses } })
  fireEvent.blur(field)
  await waitFor(() => expect(screen.getByText(/to invite/).textContent).toMatch(/^2 to invite/))
  await user.click(screen.getByRole('button', { name: 'Send invites' }))
  await waitFor(() => expect(createInvite).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(toasts()).toHaveLength(1))
}

/** The created group's row for `email`. */
const rowFor = (email: string) => screen.getByText(email, { selector: 'li span' }).closest('li') as HTMLElement

describe('bulk invites report created and accepted by the email provider, never "sent" (ADM-01, ADM-02)', () => {
  beforeEach(() => {
    vi.mocked(getInviteReadiness).mockReset().mockResolvedValue(READY)
    vi.mocked(listInvites).mockReset().mockResolvedValue([])
    vi.mocked(createInvite).mockReset()
    for (const fn of [toast.success, toast.warning, toast.error]) vi.mocked(fn).mockReset()
  })

  it('a mixed run heads "2 created · 1 accepted by the email provider", says why the other was not sent, and warns', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) =>
      mint(input.email as string, input.email === 'ann@example.com'),
    )
    await sendBatch('ann@example.com, bob@example.com', { email: true })

    for (const [input] of vi.mocked(createInvite).mock.calls) expect(input.sendEmail).toBe(true)
    expect(screen.getByText('2 created · 1 accepted by the email provider')).toBeInTheDocument()
    expect(screen.getByText(/^Accepted means the email provider took it, not that it was delivered\./)).toBeInTheDocument()
    expect(within(rowFor('bob@example.com')).getByText('Not sent')).toBeInTheDocument()
    expect(within(rowFor('ann@example.com')).queryByText('Not sent')).not.toBeInTheDocument()
    expect(screen.getAllByText('Not sent')).toHaveLength(1)
    expect(toast.warning).toHaveBeenCalledWith(
      '2 invites created · 1 accepted by the email provider. Copy the rest from the list below.',
    )
    expect(toasts().join(' ')).not.toMatch(/\bsent\b|\bdelivered\b|\bemailed\b/i)
  })

  it('a run the provider took every email of says it accepted them, never that they arrived', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, true))
    await sendBatch('ann@example.com, bob@example.com', { email: true })

    expect(screen.getByText('2 created · 2 accepted by the email provider')).toBeInTheDocument()
    expect(screen.queryByText('Not sent')).not.toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledWith('2 invites created · 2 accepted by the email provider')
    expect(toasts().join(' ')).not.toMatch(/\bsent\b|\bdelivered\b/i)
  })

  it('by default, with Email invites off, the run reads "2 invite links created" and asks the API for no email', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, false, false))
    await sendBatch('ann@example.com, bob@example.com')

    for (const [input] of vi.mocked(createInvite).mock.calls) {
      expect(input.sendEmail).toBe(false)
      expect(input.permission).toBeUndefined()
    }
    expect(screen.getByText('2 invite links created')).toBeInTheDocument()
    // Every row is a link to share by hand; the heading says so once, no row marker repeats it.
    expect(screen.queryByText('Not emailed')).not.toBeInTheDocument()
    expect(screen.queryByText(/Accepted means/)).not.toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledWith('2 invite links created')
    expect(toasts().join(' ')).not.toMatch(/\bsent\b|emailed|accepted/i)
  })
})

describe("the share panel's warning for a link-only invite (E196 (2))", () => {
  it('is the warning Notice, its inset capped in the dialog body as a frame there must be (E229)', async () => {
    render(<ResendShareModal link="https://earningsnerd.io/invite/fresh" email={null} emailed={false} onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')
    await userEvent.setup().click(within(dialog).getByRole('button', { name: 'Share invite', expanded: false }))
    const notice = within(dialog).getByText('Not bound to an email').closest('[role="status"]') as HTMLElement
    expect(notice).toHaveTextContent('Not bound to an emailAnyone with this link can redeem it. Share only with the intended person.')
    expect(notice.classList).toContain('border-warning-light/25')
    // surface-padding-cap reads a Notice in a dialog's body only in the dialog's own file, so this call site is held here.
    expect(notice.classList).toContain('px-cap-4')
  })
})

describe('the resend dialog says what is known of the new link\'s email, never that it arrived (ADM-03)', () => {
  const link = 'https://earningsnerd.io/invite/fresh'

  it('accepted by the provider: says so, and that delivery is not confirmed', () => {
    render(<ResendShareModal link={link} email="ann@example.com" emailed deliveryStatus="accepted" onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: 'New invite link ready' })).toBeInTheDocument()
    expect(dialog).toHaveTextContent("Invitation email: Accepted by the email provider. Delivery isn't confirmed.")
    expect(dialog).not.toHaveTextContent(/re-sent|\bsent\b|we emailed|delivered/i)
  })

  it('asked for and not taken: says it was not sent, or that its outcome is unknown', () => {
    for (const [status, words] of [['failed', 'Invitation email: Not sent.'], ['unknown', 'Invitation email: Outcome unknown.']] as const) {
      const { unmount } = render(
        <ResendShareModal link={link} email="ann@example.com" emailed={false} deliveryStatus={status} onClose={() => {}} />,
      )
      expect(screen.getByRole('dialog')).toHaveTextContent(words)
      unmount()
    }
  })

  it('no email asked for (a link-only invite, or a link to share by hand): "New invite link ready", no email claim', () => {
    for (const email of [null, 'ann@example.com']) {
      const { unmount } = render(<ResendShareModal link={link} email={email} emailed={false} onClose={() => {}} />)
      const dialog = screen.getByRole('dialog')
      expect(within(dialog).getByRole('heading', { name: 'New invite link ready' })).toBeInTheDocument()
      expect(dialog).not.toHaveTextContent(/re-sent|emailed|Invitation email/i)
      unmount()
    }
  })
})

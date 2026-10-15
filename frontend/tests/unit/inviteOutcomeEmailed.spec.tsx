import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * The admin invite surfaces say what happened to each invite: it was created, and it was emailed only
 * when "Email invites" was on and the backend's best-effort send went through (the API's `emailed`
 * flag, admin.py). Never "sent" for an invite nobody emailed (audit ADM-01, ADM-02, ADM-03).
 */

vi.mock('@/features/admin/api/admin-api', () => ({
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  resendInvite: vi.fn(),
  revokeInvite: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import AdminInvitesPage from '@/app/admin/invites/page'
import ResendShareModal from '@/features/admin/components/ResendShareModal'
import { createInvite, listInvites, type CreateInviteInput, type MintResult } from '@/features/admin/api/admin-api'
import { toast } from 'sonner'

const mint = (email: string, emailed: boolean): MintResult => ({
  id: email.length,
  email,
  invite_link: `https://earningsnerd.io/invite/${email.split('@')[0]}`,
  expires_at: '2026-07-08T00:00:00Z',
  emailed,
  cohort: null,
})

/** Every toast the run raised, as text. */
const toasts = () =>
  [toast.success, toast.warning, toast.error].flatMap((fn) => vi.mocked(fn).mock.calls.map((call) => String(call[0])))

async function sendBatch(addresses: string, { emailOff = false } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AdminInvitesPage />
    </QueryClientProvider>,
  )
  await screen.findByText(/No invites yet/i)
  const user = userEvent.setup()
  if (emailOff) await user.click(screen.getByRole('checkbox', { name: /Email invites/ }))
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

describe('bulk invites report created and emailed, never "sent" (ADM-01, ADM-02)', () => {
  beforeEach(() => {
    vi.mocked(listInvites).mockReset().mockResolvedValue([])
    vi.mocked(createInvite).mockReset()
    for (const fn of [toast.success, toast.warning, toast.error]) vi.mocked(fn).mockReset()
  })

  it('a mixed run heads "2 created · 1 emailed", marks the row not emailed, and warns with a toast', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) =>
      mint(input.email as string, input.email === 'ann@example.com'),
    )
    await sendBatch('ann@example.com, bob@example.com')

    expect(screen.getByText('2 created · 1 emailed')).toBeInTheDocument()
    expect(within(rowFor('bob@example.com')).getByText('Not emailed')).toBeInTheDocument()
    expect(within(rowFor('ann@example.com')).queryByText('Not emailed')).not.toBeInTheDocument()
    expect(screen.getAllByText('Not emailed')).toHaveLength(1)
    expect(toast.warning).toHaveBeenCalledWith('2 invites created · 1 emailed. Copy the rest from the list below.')
    expect(toasts().join(' ')).not.toMatch(/\bsent\b/i)
  })

  it('a run where every email went out says so', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, true))
    await sendBatch('ann@example.com, bob@example.com')

    expect(screen.getByText('2 created · 2 emailed')).toBeInTheDocument()
    expect(screen.queryByText('Not emailed')).not.toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledWith('2 invites created · 2 emailed')
  })

  it('with Email invites off, the run reads "2 invite links created" and asks the API for no email', async () => {
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, false))
    await sendBatch('ann@example.com, bob@example.com', { emailOff: true })

    for (const [input] of vi.mocked(createInvite).mock.calls) expect(input.sendEmail).toBe(false)
    expect(screen.getByText('2 invite links created')).toBeInTheDocument()
    // Every row is a link to share by hand; the heading says so once, no row marker repeats it.
    expect(screen.queryByText('Not emailed')).not.toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledWith('2 invite links created')
    expect(toasts().join(' ')).not.toMatch(/\bsent\b|emailed/i)
  })
})

describe('the resend dialog claims a re-send only when the invite was emailed (ADM-03)', () => {
  const link = 'https://earningsnerd.io/invite/fresh'

  it('emailed: "Invite re-sent", and the body names the address it went to', () => {
    render(<ResendShareModal link={link} email="ann@example.com" emailed onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: 'Invite re-sent' })).toBeInTheDocument()
    expect(dialog).toHaveTextContent('We emailed it to ann@example.com.')
  })

  it('not emailed (a link-only invite, or a send that failed): "New invite link ready", no email claim', () => {
    for (const email of [null, 'ann@example.com']) {
      const { unmount } = render(<ResendShareModal link={link} email={email} emailed={false} onClose={() => {}} />)
      const dialog = screen.getByRole('dialog')
      expect(within(dialog).getByRole('heading', { name: 'New invite link ready' })).toBeInTheDocument()
      expect(dialog).not.toHaveTextContent(/re-sent|emailed/i)
      unmount()
    }
  })
})

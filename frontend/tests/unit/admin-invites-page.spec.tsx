import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the admin API module so the page renders without real network calls.
vi.mock('@/features/admin/api/admin-api', () => ({
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  resendInvite: vi.fn(),
  revokeInvite: vi.fn(),
}))

// sonner's Toaster is rendered globally in the real app, not here; stub toast calls.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import AdminInvitesPage from '@/app/admin/invites/page'
import {
  listInvites,
  resendInvite,
  type InviteRecord,
  type ResendResult,
} from '@/features/admin/api/admin-api'

const invite: InviteRecord = {
  id: 1,
  email: 'alice@example.com',
  status: 'pending',
  cohort: 'beta',
  expires_at: '2026-07-01T00:00:00Z',
  used_at: null,
  user_id: null,
  created_at: '2026-06-20T00:00:00Z',
}

/** The page's heading outline: SecondaryHeader's h1 first, then the sections, never skipping a level. */
function expectOutline(h1: string) {
  const headings = screen.getAllByRole('heading')
  expect(headings[0]).toHaveTextContent(h1)
  const levels = headings.map((h) => Number(h.tagName.slice(1)))
  expect(levels[0]).toBe(1)
  expect(levels.filter((level) => level === 1)).toHaveLength(1)
  levels.slice(1).forEach((level, i) => expect(level).toBeLessThanOrEqual(levels[i] + 1))
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AdminInvitesPage />
    </QueryClientProvider>,
  )
}

describe('AdminInvitesPage', () => {
  beforeEach(() => {
    vi.mocked(listInvites).mockReset()
  })

  it('renders both zones and the loaded invite row', async () => {
    vi.mocked(listInvites).mockResolvedValue([invite])
    renderPage()

    expect(screen.getByRole('heading', { name: 'Invite people' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Invites', level: 2 })).toBeInTheDocument()
    expectOutline('Invites')

    // The row populates once the query resolves.
    expect(await screen.findByText('alice@example.com')).toBeInTheDocument()
    // "Pending" appears both as the row badge and as a filter option, so assert >= 1.
    expect(screen.getAllByText('Pending').length).toBeGreaterThanOrEqual(1)
    // A pending invite exposes Resend + Revoke actions.
    expect(screen.getByRole('button', { name: 'Resend invite to alice@example.com' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Revoke invite to alice@example.com' })).toBeInTheDocument()
  })

  it('shows the empty state when there are no invites', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    renderPage()
    // One plain line in the card (ADM-07, ADM-09): no title, no nested GuidanceCard.
    const empty = await screen.findByText(/No invites yet/i)
    expect(empty).toHaveAttribute('role', 'status')
    expect(empty).toHaveTextContent(/^No invites yet\. Send your first one above\.$/)
    expect(screen.queryByText(/No Invites Found/i)).not.toBeInTheDocument()
  })

  it('names a link-only invite\'s actions by what it is, not "this invite" (ADM-22)', async () => {
    vi.mocked(listInvites).mockResolvedValue([{ ...invite, id: 3, email: null }])
    renderPage()
    // The visible labels stay "Resend" and "Revoke".
    expect(await screen.findByRole('button', { name: 'Resend this link-only invite' })).toHaveTextContent('Resend')
    expect(screen.getByRole('button', { name: 'Revoke this link-only invite' })).toHaveTextContent('Revoke')
  })

  it('shows a load failure as a Notice with a Retry that refetches (ADM-11)', async () => {
    vi.mocked(listInvites).mockRejectedValueOnce(new Error('network')).mockResolvedValue([invite])
    const user = userEvent.setup()
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not load the invites.')
    await user.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('alice@example.com')).toBeInTheDocument()
    expect(listInvites).toHaveBeenCalledTimes(2)
  })

  it('updates the live counter as valid/invalid emails are entered', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    renderPage()

    const field = screen.getByLabelText('Email addresses')
    fireEvent.change(field, { target: { value: 'good@example.com, nope' } })
    fireEvent.blur(field)

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument() // 1 to invite
    })
    expect(screen.getByText(/1 invalid/)).toBeInTheDocument()
    // The Send button enables once there is at least one valid, not-already-invited email.
    expect(screen.getByRole('button', { name: /Send invites/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Send invites/i })).not.toHaveAttribute('aria-disabled')
  })

  it('marks an already-invited address in the chip\'s own plain type, not a faded eyebrow (ADM-17)', async () => {
    vi.mocked(listInvites).mockResolvedValue([invite])
    renderPage()
    await screen.findByText('alice@example.com')
    const field = screen.getByLabelText('Email addresses')
    fireEvent.change(field, { target: { value: 'alice@example.com' } })
    fireEvent.blur(field)
    const marker = await screen.findByText('· already invited')
    // The marker reads in the chip's own size and ink: no opacity- class and no eyebrow treatment, under any variant.
    expect([...marker.classList].filter((cls) => /(^|:)(opacity-|text-data-xs$|uppercase$|tracking-eyebrow$)/.test(cls))).toEqual([])
  })

  it('disables Send invites when there is nothing valid to send', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    renderPage()
    // aria-disabled, not native: a send can empty the list while Send holds focus
    // (busyControls.admin-auth.spec.tsx).
    expect(screen.getByRole('button', { name: /Send invites/i })).toHaveAttribute('aria-disabled', 'true')
  })
})

describe('AdminInvitesPage resend dialog focus return', () => {
  type User = ReturnType<typeof userEvent.setup>

  // A resend revokes the old invite and mints a replacement with a new id (admin.py resend_invite).
  const resent: ResendResult = {
    id: 2,
    email: 'alice@example.com',
    invite_link: 'https://earningsnerd.io/invite/fresh-token',
    expires_at: '2026-07-08T00:00:00Z',
    emailed: true,
    cohort: 'beta',
    revoked_invite_id: 1,
  }
  // The refetched list: the fresh invite on top, the original row now revoked beneath it.
  const afterResend: InviteRecord[] = [
    { ...invite, id: 2, created_at: '2026-06-21T00:00:00Z' },
    { ...invite, status: 'revoked' },
  ]

  const closeVia: Array<[string, (user: User) => Promise<void>]> = [
    ['Done', (user) => user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Done' }))],
    ['Escape', (user) => user.keyboard('{Escape}')],
    [
      'scrim click',
      // The portal's root is the scrim, whether or not it also carries role="dialog".
      (user) => user.click(screen.getByRole('dialog').closest('body > *') as HTMLElement),
    ],
  ]

  beforeEach(() => {
    vi.mocked(listInvites).mockReset()
    vi.mocked(resendInvite).mockReset()
    vi.mocked(listInvites).mockResolvedValueOnce([invite]).mockResolvedValue(afterResend)
    vi.mocked(resendInvite).mockResolvedValue(resent)
  })

  /** Resend the original invite, wait for the share dialog and the post-resend refetch. */
  async function resendFromRow(user: User) {
    renderPage()
    const resend = await screen.findByRole('button', { name: 'Resend invite to alice@example.com' })
    const row = resend.closest('tr') as HTMLTableRowElement
    await user.click(resend)
    await screen.findByRole('dialog')
    await waitFor(() => expect(within(row).getByText('Revoked')).toBeInTheDocument())
    return { resend, row }
  }

  it.each(closeVia)('returns focus to the resending row when closed via %s', async (_how, close) => {
    const user = userEvent.setup()
    const { resend, row } = await resendFromRow(user)

    await close(user)

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(row).toContainElement(document.activeElement as HTMLElement)
    expect(resend).toHaveFocus()
    // Focus came back mid-cooldown: the button is inert but still focusable.
    expect(resend).toHaveTextContent(/^Resend \(\d+s\)$/)
    expect(resend).toHaveAttribute('aria-disabled', 'true')
    expect(resend).not.toBeDisabled()
    expect(resendInvite).toHaveBeenCalledTimes(1)
    expect(resendInvite).toHaveBeenCalledWith(1)
  })

  it('ignores activation of the focused Resend button during the cooldown', async () => {
    const user = userEvent.setup()
    const { resend } = await resendFromRow(user)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(resend).toHaveFocus())

    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    await user.click(resend)

    expect(resendInvite).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(resend).toHaveFocus()
  })

  it('keeps Resend focused but inert while the request is in flight', async () => {
    let settle: (result: ResendResult) => void = () => {}
    vi.mocked(resendInvite).mockReturnValue(
      new Promise<ResendResult>((resolve) => {
        settle = resolve
      }),
    )
    const user = userEvent.setup()
    renderPage()
    const resend = await screen.findByRole('button', { name: 'Resend invite to alice@example.com' })

    await user.click(resend)

    await waitFor(() => expect(resend).toHaveAttribute('aria-busy', 'true'))
    // Native `disabled` here would blur the button in Chrome before the dialog records its opener.
    expect(resend).toHaveAttribute('aria-disabled', 'true')
    expect(resend).not.toBeDisabled()
    expect(resend).toHaveFocus()
    await user.click(resend)
    expect(resendInvite).toHaveBeenCalledTimes(1)

    settle(resent)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(resend).not.toHaveAttribute('aria-busy')
  })
})

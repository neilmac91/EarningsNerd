import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import AdminInvitesPage from '@/app/admin/invites/page'
import { listInvites, type InviteRecord } from '@/features/admin/api/admin-api'

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
    expect(await screen.findByText(/No invites yet/i)).toBeInTheDocument()
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
  })

  it('disables Send invites when there is nothing valid to send', async () => {
    vi.mocked(listInvites).mockResolvedValue([])
    renderPage()
    expect(screen.getByRole('button', { name: /Send invites/i })).toBeDisabled()
  })
})

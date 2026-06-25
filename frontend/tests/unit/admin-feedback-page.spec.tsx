import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the admin API module so the page renders without real network calls.
vi.mock('@/features/admin/api/admin-api', () => ({
  listFeedback: vi.fn(),
  updateFeedbackStatus: vi.fn(),
}))

// sonner's Toaster is rendered globally in the real app, not here; stub toast calls.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import AdminFeedbackPage from '@/app/admin/feedback/page'
import {
  listFeedback,
  updateFeedbackStatus,
  type FeedbackRecord,
} from '@/features/admin/api/admin-api'

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

const featureRequest: FeedbackRecord = {
  id: 2,
  user_id: null,
  user_email: null,
  type: 'feature',
  message: 'Please add CSV download for the peers table.',
  page_url: null,
  status: 'triaged',
  created_at: '2026-06-21T00:00:00Z',
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AdminFeedbackPage />
    </QueryClientProvider>,
  )
}

describe('AdminFeedbackPage', () => {
  beforeEach(() => {
    vi.mocked(listFeedback).mockReset()
    vi.mocked(updateFeedbackStatus).mockReset()
  })

  it('renders feedback rows once the query resolves', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport, featureRequest])
    renderPage()

    expect(screen.getByRole('heading', { name: 'Feedback', level: 2 })).toBeInTheDocument()

    // Both rows populate once the query resolves.
    expect(await screen.findByText(bugReport.message)).toBeInTheDocument()
    expect(screen.getByText(featureRequest.message)).toBeInTheDocument()
    // The user email shows for the identified reporter; anonymous shows for the null one.
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('Anonymous')).toBeInTheDocument()
  })

  it('shows the empty state when there is no feedback', async () => {
    vi.mocked(listFeedback).mockResolvedValue([])
    renderPage()
    expect(await screen.findByText(/No feedback yet/i)).toBeInTheDocument()
  })

  it('changing a row status calls updateFeedbackStatus', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport])
    vi.mocked(updateFeedbackStatus).mockResolvedValue({ ...bugReport, status: 'resolved' })
    renderPage()

    await screen.findByText(bugReport.message)

    const statusSelect = screen.getByLabelText(`Set status for feedback ${bugReport.id}`)
    fireEvent.change(statusSelect, { target: { value: 'resolved' } })

    await waitFor(() => {
      expect(vi.mocked(updateFeedbackStatus)).toHaveBeenCalledWith(bugReport.id, 'resolved')
    })
  })
})

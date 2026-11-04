import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/api/client'
import type { CurrentUser } from '@/features/auth/api/auth-api'

// Uploads turned off between the capability read and Send: the server refuses the screenshots (503, before any claim of
// the submission key). Mirrors busyControls.forms.spec.tsx: the feedback API module, auth, toasts and flags are mocked.
const api = vi.hoisted(() => ({
  submitFeedback: vi.fn(),
  getFeedbackCapabilities: vi.fn(),
  getFeedbackSubmission: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('@/features/feedback/api/feedback-api', () => ({ submitFeedback: api.submitFeedback, getFeedbackCapabilities: api.getFeedbackCapabilities, getFeedbackSubmission: api.getFeedbackSubmission }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('sonner', () => ({ toast: { success: api.toastSuccess, error: api.toastError } }))
vi.mock('@/lib/api/session', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/session')>()),
  hasActiveSession: () => true,
}))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FEEDBACK_WIDGET: true,
}))

const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
const DISABLED = new ApiError(503, 'Screenshots are temporarily unavailable. Your draft has been kept.')
const NOTE = 'Screenshot explains this problem'
const reader: CurrentUser = { id: 1, email: '1@example.test', full_name: null, is_pro: false, is_beta: true, is_admin: false, email_verified: true }

function mountFeedback() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
  client.setQueryData(queryKeys.currentUser(), reader)
  render(<QueryClientProvider client={client}><FeedbackWidget /></QueryClientProvider>)
  return client
}

async function draftWithScreenshot() {
  fireEvent.click(screen.getByRole('button', { name: 'Feedback' }))
  await screen.findByRole('button', { name: 'Add screenshots' })
  const image = new File(['image'], 'private.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText('Screenshot files'), { target: { files: [image] } })
  fireEvent.change(screen.getByLabelText('Feedback message'), { target: { value: NOTE } })
  return image
}

beforeEach(() => {
  sessionStorage.clear()
  api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: true })
  // The real getFeedbackSubmission maps the receipt endpoint's 404 (a key the refused POST never claimed) to not_found.
  api.getFeedbackSubmission.mockImplementation(async (key: string) => ({ submission_id: key, state: 'not_found', retry_after_seconds: null, feedback: null }))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:feedback-test') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})
afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('FeedbackWidget: a screenshot draft when uploads are turned off mid-session', () => {
  it('refetches capabilities on the refusal, keeps the note, sets the screenshots aside and sends the note once under the same key', async () => {
    mountFeedback()
    await draftWithScreenshot()
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: false })
    api.submitFeedback.mockRejectedValueOnce(DISABLED).mockResolvedValueOnce({ id: 7, type: 'general', status: 'new', created_at: '2026-11-02T00:00:00Z' })
    const send = screen.getByRole('button', { name: 'Send feedback' })
    fireEvent.click(send)
    await screen.findByText(/^Screenshot uploads are unavailable right now\./)
    expect(api.getFeedbackCapabilities).toHaveBeenCalledTimes(2)
    expect(api.getFeedbackSubmission).not.toHaveBeenCalled()
    expect(api.toastError.mock.calls).toEqual([['Could not send your feedback. Your draft is still here.']])
    const key = api.submitFeedback.mock.calls[0][1].submissionId
    const message = screen.getByLabelText('Feedback message')
    expect(message).toHaveValue(NOTE)
    expect(message).not.toHaveAttribute('readonly')
    expect(send).toHaveAttribute('aria-disabled', 'true')
    expect(JSON.parse(sessionStorage.getItem('en_feedback_pending')!)).toEqual({ owner: 1, key })
    fireEvent.click(send)
    await settle()
    expect(api.submitFeedback).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Remove screenshot 1' }))
    expect(send).not.toHaveAttribute('aria-disabled')
    fireEvent.click(send)
    fireEvent.click(send)
    await waitFor(() => expect(api.toastSuccess).toHaveBeenCalledTimes(1))
    expect(api.submitFeedback).toHaveBeenCalledTimes(2)
    expect(api.submitFeedback.mock.calls[1][0]).toMatchObject({ message: NOTE })
    expect(api.submitFeedback.mock.calls[1][1]).toMatchObject({ submissionId: key, files: [] })
    expect(sessionStorage.getItem('en_feedback_pending')).toBeNull()
  })

  it('fences an earlier attempt under the kept key: a 409 on the text-only Send checks the receipt and keeps the note', async () => {
    mountFeedback()
    await draftWithScreenshot()
    api.getFeedbackCapabilities.mockResolvedValue({ attachments_enabled: false })
    api.submitFeedback.mockRejectedValueOnce(DISABLED)
      .mockRejectedValueOnce(new ApiError(409, 'This submission identifier belongs to a different draft.'))
    api.getFeedbackSubmission.mockImplementation(async (key: string) => ({ submission_id: key, state: 'submitted', retry_after_seconds: null, feedback: { id: 3 } }))
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText(/^Screenshot uploads are unavailable right now\./)
    fireEvent.click(screen.getByRole('button', { name: 'Remove screenshot 1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('Your earlier feedback was saved. This draft is still here if you want to send another note.')
    expect(api.submitFeedback).toHaveBeenCalledTimes(2)
    expect(api.submitFeedback.mock.calls[1][1].submissionId).toBe(api.submitFeedback.mock.calls[0][1].submissionId)
    expect(screen.getByLabelText('Feedback message')).toHaveValue(NOTE)
    expect(api.toastSuccess).not.toHaveBeenCalled()
  })

  it('keeps the existing receipt check when the refetch still reports uploads on (any other 503)', async () => {
    mountFeedback()
    await draftWithScreenshot()
    api.submitFeedback.mockRejectedValueOnce(new ApiError(503, 'Screenshots could not be saved. Your draft is ready to retry.'))
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('We could not confirm the submission. Send this same draft again to check it safely.')
    expect(api.getFeedbackCapabilities).toHaveBeenCalledTimes(2)  // the refetch ran and still reported uploads on
    expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Feedback message')).toHaveAttribute('readonly')
    expect(screen.queryByText(/^Screenshot uploads are unavailable right now\./)).not.toBeInTheDocument()
  })

  it.each([
    ['rejects', () => Promise.reject(new ApiError(500, 'Capabilities are unavailable.'))],
    ['answers nothing readable', () => Promise.resolve(null)],
  ])('keeps the existing receipt check when the capability refetch %s', async (_case, refetch) => {
    mountFeedback()
    await draftWithScreenshot()
    api.getFeedbackCapabilities.mockImplementationOnce(refetch)
    api.submitFeedback.mockRejectedValueOnce(DISABLED)
    fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    await screen.findByText('We could not confirm the submission. Send this same draft again to check it safely.')
    expect(api.getFeedbackCapabilities).toHaveBeenCalledTimes(2)
    expect(api.getFeedbackSubmission).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Feedback message')).toHaveValue(NOTE)
    expect(screen.getByRole('button', { name: 'Send feedback' })).not.toHaveAttribute('aria-busy', 'true')
  })
})

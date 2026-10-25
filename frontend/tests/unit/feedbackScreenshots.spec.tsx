import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FeedbackDetails from '@/features/admin/components/FeedbackDetails'
import type { FeedbackRecord } from '@/features/admin/api/admin-api'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import { queryKeys } from '@/lib/queryKeys'

const api = vi.hoisted(() => ({ getFeedbackAttachment: vi.fn(), getCurrentUserSafe: vi.fn(), downloadBlob: vi.fn() }))
vi.mock('@/features/feedback/api/feedback-api', () => ({ getFeedbackAttachment: api.getFeedbackAttachment }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/lib/downloadBlob', () => ({ downloadBlob: api.downloadBlob }))
const reader = (id: number, isAdmin = true): CurrentUser => ({ id, is_admin: isAdmin, email: 'admin@example.test', full_name: null, is_beta: true, is_pro: false, email_verified: true })
const feedback: FeedbackRecord = {
  id: 8, user_id: 3, user_email: 'reader@example.test', type: 'bug', message: 'A chart label overlaps', page_url: '/filing/3', status: 'new', created_at: '2026-10-25T10:00:00Z', attachment_count: 1,
  attachments: [{ id: '00000000-0000-4000-8000-000000000001', content_type: 'image/png', width: 100, height: 80, byte_count: 10, expires_at: '2027-04-23T10:00:00Z', availability: 'available', download_path: '/api/feedback/attachments/00000000-0000-4000-8000-000000000001' }],
}
const clients: QueryClient[] = []
function mount(record = feedback, open = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  clients.push(client)
  client.setQueryData(queryKeys.currentUser(), reader(1))
  const view = render(<QueryClientProvider client={client}><FeedbackDetails feedback={record} open={open} onClose={() => {}} /></QueryClientProvider>)
  return { client, ...view }
}
beforeEach(() => {
  vi.clearAllMocks()
  api.getCurrentUserSafe.mockResolvedValue(reader(1))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-screenshot') })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()) })

describe('private feedback screenshots', () => {
  it('loads only inside open details, downloads a private blob, and revokes its URL on close', async () => {
    const blob = new Blob(['image'], { type: 'image/png' })
    api.getFeedbackAttachment.mockResolvedValue(blob)
    const closed = mount(feedback, false)
    expect(api.getFeedbackAttachment).not.toHaveBeenCalled()
    closed.unmount()
    const view = mount()
    const image = await screen.findByRole('img', { name: 'Screenshot 1' })
    expect(image).toHaveAttribute('src', 'blob:private-screenshot')
    expect(image.closest('.ph-no-capture')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Download screenshot 1' }))
    expect(api.downloadBlob).toHaveBeenCalledWith(blob, 'feedback-screenshot-1.png')
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-screenshot')
  })

  it('admits at most two image reads and cancels queued reads when details closes', async () => {
    const releases: Array<(blob: Blob) => void> = []
    api.getFeedbackAttachment.mockImplementation(() => new Promise<Blob>((resolve) => releases.push(resolve)))
    const images = [0, 1, 2].map((index) => ({ ...feedback.attachments![0], id: `image-${index}` }))
    const view = mount({ ...feedback, attachments: images, attachment_count: 3 })
    await waitFor(() => expect(api.getFeedbackAttachment).toHaveBeenCalledTimes(2))
    expect(api.getFeedbackAttachment.mock.calls.map(([id]) => id)).toEqual(['image-0', 'image-1'])
    view.unmount()
    await act(async () => { releases.forEach((resolve) => resolve(new Blob(['image']))) })
    expect(api.getFeedbackAttachment).toHaveBeenCalledTimes(2)
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('does not publish a late image after the observed account or admin role changes', async () => {
    let resolve!: (blob: Blob) => void
    api.getFeedbackAttachment.mockReturnValue(new Promise<Blob>((yes) => { resolve = yes }))
    const { client } = mount()
    await waitFor(() => expect(api.getFeedbackAttachment).toHaveBeenCalledTimes(1))
    act(() => client.setQueryData(queryKeys.currentUser(), reader(2, false)))
    await act(async () => resolve(new Blob(['image'], { type: 'image/png' })))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('refuses a download after the cache identity changes before React renders it', async () => {
    api.getFeedbackAttachment.mockResolvedValue(new Blob(['image'], { type: 'image/png' }))
    const { client } = mount()
    await screen.findByRole('img')
    const button = screen.getByRole('button', { name: 'Download screenshot 1' })
    act(() => {
      client.setQueryData(queryKeys.currentUser(), reader(2, false))
      fireEvent.click(button)
    })
    expect(api.downloadBlob).not.toHaveBeenCalled()
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled())
  })

  it('distinguishes unavailable evidence from a recoverable load failure and keeps its retry focused', async () => {
    api.getFeedbackAttachment.mockRejectedValueOnce({ status: 503 }).mockResolvedValueOnce(new Blob(['image']))
    const view = mount()
    const retry = await screen.findByRole('button', { name: 'Try again' })
    retry.focus()
    fireEvent.click(retry)
    await screen.findByRole('img')
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(document.activeElement).toBe(screen.getByText('Screenshot 1'))
    view.unmount()
    api.getFeedbackAttachment.mockRejectedValue({ status: 410 })
    mount()
    expect(await screen.findByText('This screenshot is no longer available.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})

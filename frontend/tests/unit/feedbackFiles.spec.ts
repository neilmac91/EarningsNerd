import { afterEach, describe, expect, it, vi } from 'vitest'
import api from '@/lib/api/client'
import { getFeedbackAttachment, getFeedbackSubmission, submitFeedback } from '@/features/feedback/api/feedback-api'
import { clearPendingFeedback, feedbackFileError, readPendingFeedback, storePendingFeedback } from '@/features/feedback/lib/feedbackFiles'

const key = '00000000-0000-4000-8000-000000000001'
const file = (name = 'screen.png', type = 'image/png', bytes = 10) => new File([new Uint8Array(bytes)], name, { type })
afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks() })

describe('feedback evidence boundaries', () => {
  it('rejects unsupported, empty, oversized and over-count selections without an implicit partial batch', () => {
    expect(feedbackFileError([file()], 2)).toBeNull()
    expect(feedbackFileError([file()], 3)).toMatch(/up to 3/)
    expect(feedbackFileError([file(), file('vector.svg', 'image/svg+xml')], 0)).toMatch(/PNG, JPEG/)
    expect(feedbackFileError([file('empty.png', 'image/png', 0)], 0)).toMatch(/1 byte/)
    expect(feedbackFileError([file('large.png', 'image/png', 5 * 1024 * 1024 + 1)], 0)).toMatch(/5 MiB/)
    expect(feedbackFileError([file('max.png', 'image/png', 5 * 1024 * 1024)], 0)).toBeNull()
  })

  it('persists only receipt identity, clears a different reader, and an old cleanup cannot delete the next marker', () => {
    storePendingFeedback({ owner: 1, key })
    expect(JSON.parse(sessionStorage.getItem('en_feedback_pending')!)).toEqual({ owner: 1, key })
    expect(readPendingFeedback(1)).toEqual({ owner: 1, key })
    expect(readPendingFeedback(2)).toBeNull()
    expect(sessionStorage.length).toBe(0)
    storePendingFeedback({ owner: 2, key })
    clearPendingFeedback(1)
    expect(readPendingFeedback(2)).toEqual({ owner: 2, key })
    clearPendingFeedback(2)
    expect(sessionStorage.length).toBe(0)
    sessionStorage.setItem('en_feedback_pending', '{"owner":2,"key":"invalid"}')
    expect(readPendingFeedback(2)).toBeNull()
  })

  it('uses one multipart request with immutable reader/key headers and leaves its boundary to the browser', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { id: 12 } })
    const screenshot = file()
    const progress = vi.fn()
    await submitFeedback({ type: 'bug', message: 'The chart overlaps', pageUrl: '/filing/3' }, {
      submissionId: key, readerId: 1, files: [screenshot], onUploadProgress: progress,
    })
    expect(post).toHaveBeenCalledTimes(1)
    const [url, body, config] = post.mock.calls[0]
    expect(url).toBe('/api/feedback/with-attachments')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).getAll('files')).toEqual([screenshot])
    expect((body as FormData).get('message')).toBe('The chart overlaps')
    expect(config?.headers).toEqual({
      'Idempotency-Key': key, 'X-Feedback-User-Id': '1', 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': undefined,
    })
    expect(config?.timeout).toBe(75_000)
    config?.onUploadProgress?.({ loaded: 20, total: 10, bytes: 20, lengthComputable: true })
    expect(progress).toHaveBeenCalledWith(100)
  })

  it('keeps text submission compatible, scopes status misses, and constructs private read paths locally', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { id: 13 } })
    await submitFeedback({ type: 'general', message: 'A useful note' }, { submissionId: key, readerId: 2, files: [] })
    expect(post.mock.calls[0][0]).toBe('/api/feedback/')
    expect(post.mock.calls[0][1]).toEqual({ type: 'general', message: 'A useful note', page_url: undefined })
    const get = vi.spyOn(api, 'get').mockRejectedValueOnce({ status: 404 }).mockRejectedValueOnce({ status: 503 }).mockResolvedValueOnce({ data: new Blob() })
    expect((await getFeedbackSubmission(key)).state).toBe('not_found')
    await expect(getFeedbackSubmission(key)).rejects.toEqual({ status: 503 })
    await getFeedbackAttachment('https://untrusted.example/image')
    expect(get.mock.calls[2][0]).toBe('/api/feedback/attachments/https%3A%2F%2Funtrusted.example%2Fimage')
    expect(get.mock.calls[2][1]).toMatchObject({ responseType: 'blob' })
  })
})

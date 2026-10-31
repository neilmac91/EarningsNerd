import api from '@/lib/api/client'
import { getErrorStatus } from '@/lib/api/types'

export type FeedbackType = 'bug' | 'feature' | 'general'

export interface FeedbackInput {
  type: FeedbackType
  message: string
  pageUrl?: string
}

export interface FeedbackReceipt {
  id: number
  type: FeedbackType
  status: string
  created_at: string
}

export interface FeedbackSubmissionStatus {
  submission_id: string
  state: 'submitted' | 'processing' | 'retryable' | 'not_found'
  retry_after_seconds: number | null
  feedback: FeedbackReceipt | null
}

export interface FeedbackCapabilities {
  attachments_enabled: boolean
  max_files: number
  max_file_bytes: number
  max_total_bytes: number
  accepted_content_types: string[]
}

export interface FeedbackAttachment {
  id: string
  content_type: string
  width: number
  height: number
  byte_count: number
  expires_at: string
  availability: 'available' | 'expired' | 'deleted'
  download_path: string | null
}

interface SubmissionOptions {
  submissionId: string
  readerId: number
  files: readonly File[]
  onUploadProgress?: (percent: number) => void
}

/** All evidence travels in one authenticated request; the browser supplies the multipart boundary. */
export async function submitFeedback(input: FeedbackInput, options?: SubmissionOptions): Promise<FeedbackReceipt | FeedbackSubmissionStatus> {
  const headers = options ? {
    'Idempotency-Key': options.submissionId,
    'X-Feedback-User-Id': String(options.readerId),
    'X-Requested-With': 'XMLHttpRequest',
  } : undefined
  const fields = { type: input.type, message: input.message, page_url: input.pageUrl }
  if (options?.files.length) {
    const form = new FormData()
    form.append('type', input.type)
    form.append('message', input.message)
    if (input.pageUrl) form.append('page_url', input.pageUrl)
    for (const file of options.files) form.append('files', file)
    const response = await api.post('/api/feedback/with-attachments', form, {
      headers: { ...headers, 'Content-Type': undefined },
      timeout: 75_000,
      onUploadProgress: ({ loaded, total }) => {
        if (total) options.onUploadProgress?.(Math.min(100, Math.round(loaded / total * 100)))
      },
    })
    return response.data
  }
  const response = await api.post('/api/feedback/', fields, { headers })
  return response.data
}

export async function getFeedbackCapabilities(signal?: AbortSignal): Promise<FeedbackCapabilities> {
  const response = await api.get('/api/feedback/capabilities', { signal })
  return response.data
}

export async function getFeedbackSubmission(submissionId: string, signal?: AbortSignal): Promise<FeedbackSubmissionStatus> {
  try {
    const response = await api.get(`/api/feedback/submissions/${encodeURIComponent(submissionId)}`, { signal })
    return response.data
  } catch (error) {
    if (getErrorStatus(error) !== 404) throw error
    return { submission_id: submissionId, state: 'not_found', retry_after_seconds: null, feedback: null }
  }
}

/** Construct the known API path locally, never fetch an arbitrary URL from feedback metadata. */
export async function getFeedbackAttachment(id: string, signal?: AbortSignal): Promise<Blob> {
  const response = await api.get(`/api/feedback/attachments/${encodeURIComponent(id)}`, { responseType: 'blob', signal })
  return response.data
}

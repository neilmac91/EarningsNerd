import api from '@/lib/api/client'

export type FeedbackType = 'bug' | 'feature' | 'general'

export interface FeedbackInput {
  type: FeedbackType
  message: string
  pageUrl?: string
}

/** Submit in-dashboard beta feedback. Authenticated (the API client attaches the session). */
export async function submitFeedback(input: FeedbackInput) {
  const response = await api.post('/api/feedback/', {
    type: input.type,
    message: input.message,
    page_url: input.pageUrl,
  })
  return response.data
}

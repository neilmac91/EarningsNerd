import api from '@/lib/api/client'

export interface ContactSubmission {
  name: string
  email: string
  subject: string | null
  message: string
}

export interface ContactSubmissionResponse {
  id: number
  name: string
  email: string
  subject: string | null
  message: string
  status: string
  created_at: string
}

export const submitContactForm = async (
  data: ContactSubmission,
  turnstileToken?: string,
): Promise<ContactSubmissionResponse> => {
  const config = turnstileToken
    ? { headers: { 'cf-turnstile-response': turnstileToken } }
    : undefined
  const response = await api.post('/api/contact/', data, config)
  return response.data
}

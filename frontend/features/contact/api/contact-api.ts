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

export const submitContactForm = async (data: ContactSubmission): Promise<ContactSubmissionResponse> => {
  const response = await api.post('/api/contact/', data)
  return response.data
}

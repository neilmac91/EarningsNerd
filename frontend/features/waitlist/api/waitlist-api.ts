import api from '@/lib/api/client'

export interface WaitlistJoinPayload {
  email: string
  name: string | null
  referral_code: string | null
  source: string
  honeypot: string
}

export interface WaitlistJoinResult {
  success?: boolean
  error?: string
  message?: string
  position: number
  referral_code: string
  referral_link: string
}

export interface WaitlistStats {
  total_signups: number
}

export interface WaitlistStatusResult {
  position: number
  referral_code: string
  referral_link: string
  referrals_count: number
  positions_gained: number
  email_verified: boolean
}

// The waitlist endpoints are public (no auth); routing them through the shared axios client (was raw
// fetch) unifies baseURL + `withCredentials` + error handling on the client's `ApiError`. Callers read
// `err.detail` on an HTTP error and treat `err.status === 0` (no response) as a network failure.

export const joinWaitlist = async (
  payload: WaitlistJoinPayload,
  turnstileToken?: string,
): Promise<WaitlistJoinResult> => {
  const response = await api.post('/api/waitlist/join', payload, {
    headers: turnstileToken ? { 'cf-turnstile-response': turnstileToken } : undefined,
  })
  return response.data
}

export const getWaitlistStats = async (): Promise<WaitlistStats> => {
  const response = await api.get('/api/waitlist/stats')
  return response.data
}

export const getWaitlistStatus = async (email: string): Promise<WaitlistStatusResult> => {
  const response = await api.get(`/api/waitlist/status/${encodeURIComponent(email)}`)
  return response.data
}

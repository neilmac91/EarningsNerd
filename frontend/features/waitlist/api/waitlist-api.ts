import api from '@/lib/api/client'

export interface WaitlistJoinPayload {
  email: string
  name: string | null
  referral_code: string | null
  source: string
  honeypot: string
}

/** A join that landed: the only answer that carries a place and a referral code. */
export interface WaitlistJoined {
  success: true
  message: string
  position: number
  referral_code: string
  referral_link: string
}

/** A join the router did not take. An address already on the list gets its code and message only: never that
 * signup's place, code or link, which would go to anyone who typed the address. */
export interface WaitlistNotJoined {
  success?: false
  /** The router's code for a join it did not take: already_registered (a 200) or invalid_referral (a 400). */
  error?: string
  message?: string
  /** The honeypot's 400 is an HTTPException: a `detail` in place of a message. */
  detail?: string
}

export type WaitlistJoinResult = WaitlistJoined | WaitlistNotJoined

export interface WaitlistStats {
  total_signups: number
}

// The waitlist endpoints are public (no auth); routing them through the shared axios client (was raw
// fetch) unifies baseURL + `withCredentials` + error handling on the client's `ApiError`. Callers read
// `err.detail` on an HTTP error and treat `err.status === 0` (no response) as a network failure; a 400
// from the join comes back as data instead (below).

export const joinWaitlist = async (
  payload: WaitlistJoinPayload,
  turnstileToken?: string,
): Promise<WaitlistJoinResult> => {
  const response = await api.post('/api/waitlist/join', payload, {
    headers: turnstileToken ? { 'cf-turnstile-response': turnstileToken } : undefined,
    // A 400 is the router's own answer, read as data: an unknown referral code is { success: false, error:
    // 'invalid_referral', message } with no `detail`, so the ApiError would carry only axios's "Request
    // failed with status code 400". As data, the form routes on the code, as it routes already_registered.
    validateStatus: (status) => (status >= 200 && status < 300) || status === 400,
  })
  return response.data
}

export const getWaitlistStats = async (): Promise<WaitlistStats> => {
  const response = await api.get('/api/waitlist/stats')
  return response.data
}

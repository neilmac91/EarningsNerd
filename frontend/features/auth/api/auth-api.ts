import api, { ApiError, withSessionCookiesForPost, withoutRefreshBeside } from '@/lib/api/client'
import { isApiError, getErrorStatus } from '@/lib/api/types'
import { markSessionActive, markSessionConfirmed, clearSessionActive, getSessionGeneration, assertSessionGeneration, hasActiveSession, getExplicitSessionGeneration, assertExplicitSessionGeneration, isExplicitSessionGenerationCurrent, beginLogout, endLogout } from '@/lib/api/session'
import type { AccountAgreement } from '@/features/legal/api/legal-api'

// Cloudflare Turnstile token is sent as a header the backend reads; omitted when unset so
// nothing changes until Turnstile is configured on both ends.
const turnstileConfig = (token?: string) =>
  token ? { headers: { 'cf-turnstile-response': token } } : undefined

// Auth APIs
export const register = async (
  email: string,
  password: string,
  fullName?: string,
  turnstileToken?: string,
  inviteCode?: string,
  agreement?: AccountAgreement,
) => {
  const response = await api.post(
    '/api/auth/register',
    { email, password, full_name: fullName, invite_code: inviteCode || undefined, ...agreement },
    turnstileConfig(turnstileToken),
  )
  // Mark the session active so the API client may silently refresh an expired access token
  // for this user. Guests stay unmarked and never attempt a (pointless) refresh.
  markSessionActive()
  return response.data
}

/**
 * Start an invited social sign-up. The closed-beta invite is a live single-use credential, so it is
 * sent in the request body (never a URL: request logs record query strings); the backend stores its
 * hash against the OAuth state, sets the state cookie and returns the provider URL to navigate to.
 */
export const startOAuthWithInvite = async (provider: 'google' | 'apple', invite?: string, agreement?: AccountAgreement): Promise<string> => {
  const response = await api.post<{ url: string }>(`/api/auth/${provider}/start`, { ...(invite ? { invite } : {}), ...agreement })
  return response.data.url
}

/**
 * The password login. Its answer sets the new session's cookies, so no silent refresh of any tab runs beside it
 * (E29 (4), client.ts's withoutRefreshBeside): this tab's refresh in flight answers first, or is cancelled at
 * LOGIN_REFRESH_WAIT_MS, then the refreshes queued for the session cookies' lock before the login's request, in any
 * tab, within what is left of it; a refresh a 401 asks for in this tab meanwhile, or in another tab after the login's
 * request, waits for the login's answer. The login holds the lock shared, so a logout in another tab posts beside it,
 * as on main. At the limit it posts without the lock: a refresh another tab has in flight, which cannot be cancelled
 * from here, can answer after it, and any refresh still waiting for the lock may go out beside it.
 */
export const login = async (email: string, password: string, turnstileToken?: string) => {
  const generation = getExplicitSessionGeneration()
  const response = await withoutRefreshBeside(LOGIN_REFRESH_WAIT_MS, () => api.post(
    '/api/auth/login',
    { email, password },
    turnstileConfig(turnstileToken),
  ))
  assertExplicitSessionGeneration(generation)
  markSessionActive()
  return response.data
}

/** Shape of GET /api/auth/me. Keep in sync with auth.py get_current_user_info. */
export interface CurrentUser {
  id: number
  email: string
  full_name: string | null
  is_pro: boolean
  is_beta: boolean
  is_admin: boolean
  email_verified: boolean
}

export const getCurrentUser = async (options?: { signal?: AbortSignal }): Promise<CurrentUser> => {
  const generation = getSessionGeneration()
  const response = await api.get('/api/auth/me', { signal: options?.signal })
  assertSessionGeneration(generation)
  options?.signal?.throwIfAborted()
  // A confirmed identity means there's a session — mark it so the client will silently
  // refresh an expired access token. This also covers OAuth redirect logins, where the
  // JS login()/register() path (which normally sets the marker) never runs. A /me that a refresh replays during a
  // logout in this tab marks nothing: the logout is ending that session (session.ts's beginLogout).
  markSessionConfirmed()
  return response.data
}

export const getCurrentUserSafe = async (options?: { signal?: AbortSignal }): Promise<CurrentUser | null> => {
  const generation = getSessionGeneration()
  const sessionWasActive = hasActiveSession()
  try {
    return await getCurrentUser(options)
  } catch (error: unknown) {
    assertSessionGeneration(generation)
    options?.signal?.throwIfAborted()
    if (error instanceof ApiError && error.sessionLossConfirmed === false) throw error
    if (isApiError(error) && getErrorStatus(error) === 401) {
      // A guest request must not clear a marker established by a concurrent successful login.
      if (sessionWasActive) clearSessionActive()
      return null
    }
    throw error
  }
}

export interface AuthConnection {
  provider: string
  provider_email: string | null
  linked_at: string | null
}

export interface AuthConnections {
  has_password: boolean
  providers: AuthConnection[]
}

export const getConnections = async (): Promise<AuthConnections> => {
  const response = await api.get('/api/auth/connections')
  return response.data
}

export const unlinkProvider = async (provider: string) => {
  const response = await api.delete(`/api/auth/connections/${provider}`)
  return response.data
}

/**
 * How long a logout waits, at most, for the silent refreshes in flight to answer before it posts: this tab's, then the
 * ones queued for the session cookies' lock before its request, in any tab, within what is left. Before a logout
 * posts: start no new silent refresh, and let every refresh already on its way answer first. A refresh's answer sets
 * the session cookies, and one that lands after the logout's answer sets them again, the access token among them,
 * which nothing revokes: the browser would stay signed in until it expires (E133).
 *
 * Each logout calls `beginLogout` first: until its `endLogout`, the session reads as inactive in this tab, so no 401
 * starts a refresh (every refresh path needs the flag) and a /me a refresh replays cannot mark it active again. Its
 * post then goes through client.ts's `withSessionCookiesForPost`: this tab's refresh in flight answers, or is cancelled
 * at the limit (`refreshSettled`), then the refreshes queued before its request answer under the session cookies'
 * lock, one at a time, and those any tab asks for after its request wait for its answer. It holds the lock shared, so
 * it waits for no other tab's login or logout, as on main. The check that no login was accepted in this tab meanwhile
 * runs in the post's send, after both waits, so it shares a turn with the post. What this leaves open: at the limit, a
 * refresh another tab has in flight, which cannot be cancelled from here, can set the cookies again after the logout's
 * answer, and any refresh still waiting for the lock may go out beside it; a refresh another tab asks for while a login
 * in a third is out, queued between that login and this logout, makes the logout wait for the login, and post with its
 * cookies; and where the browser has no lock manager, any other tab's refresh can set them again.
 */
export const LOGOUT_REFRESH_WAIT_MS = 10_000
// How long a login waits, at most, for the silent refreshes in flight to answer before it posts (E29 (4)), as a logout
// does.
export const LOGIN_REFRESH_WAIT_MS = 10_000

/** A logout of every session refused because another login was accepted while it waited (see logoutAllSessions). */
export class LogoutAllSuperseded extends Error {
  constructor() {
    super('Another login was accepted while the logout of every session waited, so it logged nothing out.')
    this.name = 'LogoutAllSuperseded'
  }
}

/** The logout of every session. The app calls it only in the one-logout flight, never beside a Log out (E157:
 * accountQueryState's logoutAllInTurn; held by tests/unit/logoutCallSitesGate.spec.ts). */
export const logoutAllSessions = async () => {
  const generation = beginLogout()
  try {
    const response = await withSessionCookiesForPost(LOGOUT_REFRESH_WAIT_MS, async () => {
      // A login accepted while this waited holds the tab's cookies now, and the server ends every session of the
      // account its request carries: posting would log that account out everywhere and leave the reader's other
      // devices signed in. So it refuses, distinctly from success, and its caller neither clears nor navigates. A
      // passive loss of the session meanwhile is no such transition: it still posts. The check runs after both waits,
      // in the post's turn.
      if (!isExplicitSessionGenerationCurrent(generation)) throw new LogoutAllSuperseded()
      return api.post('/api/auth/logout-all')
    })
    return response.data
  } finally {
    if (isExplicitSessionGenerationCurrent(generation)) clearSessionActive()
    endLogout(generation)
  }
}

export const logout = async () => {
  const generation = beginLogout()
  try {
    const response = await withSessionCookiesForPost(LOGOUT_REFRESH_WAIT_MS, async () => {
      // A login accepted while this waited is the account this tab now shows, and the logout's request could sign it
      // out. A passive loss of the session meanwhile is no such transition: the logout still posts. The check runs
      // after both waits, in the post's turn.
      if (!isExplicitSessionGenerationCurrent(generation)) return undefined
      return api.post('/api/auth/logout')
    })
    return response?.data
  } finally {
    // Always drop the session flag, even if the server call fails, so a logged-out client
    // stops attempting silent refreshes.
    if (isExplicitSessionGenerationCurrent(generation)) clearSessionActive()
    endLogout(generation)
  }
}

// User data management APIs (GDPR compliance)
export const exportUserData = async () => {
  const response = await api.get('/api/users/export', {
    responseType: 'blob', // Important for file downloads
  })

  // Create download link
  const blob = new Blob([response.data], { type: 'application/json' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `earningsnerd_data_export_${new Date().toISOString().split('T')[0]}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)

  return { success: true }
}

export const deleteUserAccount = async () => {
  const response = await api.delete('/api/users/me')
  return response.data
}

// Profile + password management
export const updateProfile = async (fullName: string | null) => {
  const response = await api.patch('/api/users/me', { full_name: fullName })
  return response.data
}

export const changePassword = async (currentPassword: string | null, newPassword: string) => {
  // current_password is omitted for OAuth-only users setting a password for the first time.
  const response = await api.post('/api/auth/change-password', {
    current_password: currentPassword || undefined,
    new_password: newPassword,
  })
  return response.data
}

export const verifyEmail = async (token: string) => {
  const response = await api.post('/api/auth/verify-email', { token })
  return response.data
}

export const resendVerification = async (email: string) => {
  const response = await api.post('/api/auth/resend-verification', { email })
  return response.data
}

export const forgotPassword = async (email: string) => {
  const response = await api.post('/api/auth/forgot-password', { email })
  return response.data
}

export const resetPassword = async (token: string, newPassword: string) => {
  const response = await api.post('/api/auth/reset-password', { token, new_password: newPassword })
  return response.data
}

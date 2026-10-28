import api, { ApiError, sessionCookiesSettled, withSessionCookiesForPost, withoutRefreshBeside } from '@/lib/api/client'
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
 * The password login. Its answer sets the new session's cookies, so no silent refresh of any tab runs beside it (E29
 * (4), client.ts's withoutRefreshBeside): this tab's refresh in flight answers first, or is cancelled at
 * LOGIN_REFRESH_WAIT_MS, then the refreshes queued for the session cookies' lock before the login's request, in any
 * tab, within what is left of it; a refresh a 401 asks for in this tab meanwhile, or in another tab after the login's
 * request, waits for the login's answer. The login holds the lock shared, so a logout in another tab posts beside it,
 * as on main, unless a refresh is queued between them (requests are granted in order). At the limit it posts without
 * the lock: a refresh another tab has in flight, which cannot be cancelled from here, can answer after it, and any
 * refresh still waiting for the lock may go out beside it.
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

// How long the identity read waits, at most, for the silent refreshes queued before it, in any tab, to answer (E29).
export const IDENTITY_READ_REFRESH_WAIT_MS = 10_000

export const getCurrentUser = async (options?: { signal?: AbortSignal }): Promise<CurrentUser> => {
  const generation = getSessionGeneration()
  // A refresh another tab sent with the previous session's cookies can answer after an OAuth sign-in's navigation has
  // set the new session's (E29): read once it has, so this tab shows the account the browser then holds.
  await sessionCookiesSettled(IDENTITY_READ_REFRESH_WAIT_MS, options?.signal)
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
 * ones queued for the session cookies' lock before its request, in any tab, within what is left. Before a logout posts:
 * start no new silent refresh, and let every refresh already on its way answer first. A refresh's answer sets the
 * session cookies, and one that lands after the logout's answer sets them again, the access token among them, which
 * nothing revokes: the browser would stay signed in until it expires (E133).
 *
 * Each logout calls `beginLogout` first: until its `endLogout`, the session reads as inactive in this tab, so no 401
 * starts a refresh (every refresh path needs the flag) and a /me a refresh replays cannot mark it active again. Its
 * post then goes through client.ts's `withSessionCookiesForPost`: this tab's refresh in flight answers, or is cancelled
 * at the limit (`refreshSettled`), then the refreshes queued before its request answer under the session cookies' lock,
 * one at a time, and those any tab asks for after its request wait for its answer. It holds the lock shared, so it
 * waits for no other tab's login or logout, as on main, unless a refresh is queued between them (requests are granted
 * in order). The check that no login was accepted in this tab meanwhile runs in the post's send, after both waits, so
 * it shares a turn with the post. What this leaves open: at the limit, a refresh another tab has in flight, which
 * cannot be cancelled from here, can set the cookies again after the logout's answer, and any refresh still waiting for
 * the lock may go out beside it. A refresh queued between another tab's login and this logout makes the logout wait for
 * that login, then post with its cookies: given a login, a refresh asked for while it is out, and a logout pressed
 * after that refresh, all within one post's time. Two tabs are enough: this tab's own refresh, asked for by a 401 while
 * the other tab's login is out, queues behind that login, and this logout's refreshSettled waits on it. A refresh that
 * waited past REFRESH_LOCK_WAIT_MS goes out beside whatever holds the lock; and where the browser has no lock manager,
 * or refuses the lock, the logout posts once this tab's refresh has settled, as before, and any other tab's refresh can
 * set the cookies again after its answer.
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

// How long a password change waits, at most, for the silent refreshes before it to answer (E29), as a logout does.
export const PASSWORD_CHANGE_REFRESH_WAIT_MS = 10_000

// Why a password change posted nothing: a login or a logout accepted in this tab since it was asked for changed the
// session the tab shows.
const sessionChangedMeanwhile = () =>
  new DOMException('Your session changed before your password was saved, so it was not changed.', 'AbortError')

// The password change's post, holding the session cookies' lock shared and refusing at its limit (client.ts's
// withSessionCookiesForPost). A login or a logout accepted in this tab while it waited changed the account the tab
// shows, so it posts only while the explicit generation it was asked under is current, in the post's own turn, after
// both waits, as a logout does.
function postPasswordChange(currentPassword: string | null, newPassword: string, generation: number) {
  return withSessionCookiesForPost(PASSWORD_CHANGE_REFRESH_WAIT_MS, async () => {
    if (!isExplicitSessionGenerationCurrent(generation)) throw sessionChangedMeanwhile()
    // current_password is omitted for OAuth-only users setting a password for the first time.
    return api.post('/api/auth/change-password', {
      current_password: currentPassword || undefined,
      new_password: newPassword,
    })
  }, 'refuse')
}

/**
 * Sets or changes the password. Its answer revokes every session of the account and gives this browser a new refresh
 * token, so a refresh sent before it with the token it revokes, in any tab, that answered after it would set that
 * token over the new one, and the browser's next refresh would be refused, signing the reader out (E29). So it posts
 * as a logout does, holding the session cookies' lock shared: this tab's refresh in flight answers first, then the
 * refreshes queued for the lock before its request, in any tab, while those asked for after it wait for its answer and
 * go out with the new token. Unlike a logout, at PASSWORD_CHANGE_REFRESH_WAIT_MS it posts nothing and rejects with
 * client.ts's SessionStillRenewing. It does not cancel this tab's refresh: one cancelled after the API rotated its
 * token leaves the browser holding the token rotated away, which the renewal below would present, and the replay sweep
 * would end every session of the account (E96). Nor does it post beside a refresh still unanswered. The route needs
 * the access token, but a refresh asked for under the hold would wait for the lock its own post holds, so the path is
 * in client.ts's NO_REFRESH_PATHS: a 401 (the access token lapsed) is renewed after the hold, by the identity read,
 * whose own 401 refreshes and confirms a lost session as any read's does, and the post goes out once more through the
 * hold. Neither post goes out once a login or a logout has been accepted in this tab since the change was asked for.
 * What this leaves open: a refresh that waited past REFRESH_LOCK_WAIT_MS goes out beside whatever holds the lock;
 * where the browser has no lock manager or refuses the lock, any other tab's refresh, and this tab's own asked for
 * while the post is out, can answer after it; a Log out pressed in this tab while the post is out posts beside it, as
 * on main, and their answers can land in either order; the post can wait behind a refresh queued after another tab's
 * login, then post with that login's cookies, as a logout can (withSessionCookiesForPost); and it changes the password
 * of the account the browser holds, which the renewal's read does not compare with the account the tab shows, so a tab
 * left stale by another tab's sign-in changes that account's (E29 (6)).
 */
export const changePassword = async (currentPassword: string | null, newPassword: string) => {
  const generation = getExplicitSessionGeneration()
  try {
    return (await postPasswordChange(currentPassword, newPassword, generation)).data
  } catch (error: unknown) {
    if (getErrorStatus(error) !== 401) throw error
  }
  try {
    await getCurrentUser()
  } catch (error: unknown) {
    // A login or a logout accepted in this tab during the renewal fences its read (getCurrentUser's generation check).
    if (error instanceof DOMException && error.name === 'AbortError') throw sessionChangedMeanwhile()
    throw error
  }
  return (await postPasswordChange(currentPassword, newPassword, generation)).data
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

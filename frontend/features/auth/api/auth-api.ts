import api from '@/lib/api/client'
import { isApiError, getErrorStatus } from '@/lib/api/types'
import { markSessionActive, clearSessionActive } from '@/lib/api/session'

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
) => {
  const response = await api.post(
    '/api/auth/register',
    { email, password, full_name: fullName },
    turnstileConfig(turnstileToken),
  )
  // Mark the session active so the API client may silently refresh an expired access token
  // for this user. Guests stay unmarked and never attempt a (pointless) refresh.
  markSessionActive()
  return response.data
}

export const login = async (email: string, password: string, turnstileToken?: string) => {
  const response = await api.post(
    '/api/auth/login',
    { email, password },
    turnstileConfig(turnstileToken),
  )
  markSessionActive()
  return response.data
}

export const getCurrentUser = async () => {
  const response = await api.get('/api/auth/me')
  // A confirmed identity means there's a session — mark it so the client will silently
  // refresh an expired access token. This also covers OAuth redirect logins, where the
  // JS login()/register() path (which normally sets the marker) never runs.
  markSessionActive()
  return response.data
}

export const getCurrentUserSafe = async () => {
  try {
    return await getCurrentUser()
  } catch (error: unknown) {
    if (isApiError(error) && getErrorStatus(error) === 401) {
      // Not logged in — clear any stale session marker so we stop attempting refreshes.
      clearSessionActive()
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

export const logoutAllSessions = async () => {
  try {
    const response = await api.post('/api/auth/logout-all')
    return response.data
  } finally {
    clearSessionActive()
  }
}

export const logout = async () => {
  try {
    const response = await api.post('/api/auth/logout')
    return response.data
  } finally {
    // Always drop the session flag, even if the server call fails, so a logged-out client
    // stops attempting silent refreshes.
    clearSessionActive()
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

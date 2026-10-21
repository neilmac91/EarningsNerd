import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { hasActiveSession, getSessionGeneration, isSessionGenerationCurrent, assertSessionGeneration, notifySessionLost } from './session'
import { getErrorStatus } from './types'
import { refreshAccessToken } from './refresh'

// Custom error class that preserves backend error details
export class ApiError extends Error {
  status: number
  detail: string
  isRetryable: boolean
  // Internal classification only: an original access 401 after transient refresh failure
  // is not evidence that the refresh session is gone. HTTP status/detail stay unchanged.
  sessionLossConfirmed?: boolean
  // The backend's own words: set only when the response body carried a readable `detail`, a string or
  // a validation 422's `{ loc, msg, type }` list, whose first `msg` it takes (detailMessage).
  // Undefined when `detail` is this client's status fallback or axios's message ("Request failed
  // with status code N"), so a surface that shows backend text verbatim reads this, never `detail`.
  backendDetail?: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    // 503 (Service Unavailable), 429 (Rate Limited), and 5xx errors are retryable
    this.isRetryable = status === 503 || status === 429 || (status >= 500 && status < 600)
  }
}

/**
 * The message a backend `detail` carries, as one sentence a person can read. A string detail is the
 * backend's own message. FastAPI's validation 422 sends a list of `{ loc, msg, type }` objects, which
 * used to reach the UI as "[object Object]": its first `msg` stands for it, without the "Value error, "
 * or "Assertion failed, " that pydantic puts before a custom validator's own sentence (a msg that is
 * only the prefix stays as sent). Anything else yields undefined, so the status-based message below
 * applies.
 */
export function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail || undefined
  const first: unknown = Array.isArray(detail) ? detail[0] : detail
  if (first && typeof first === 'object' && 'msg' in first) {
    const msg = (first as { msg: unknown }).msg
    if (typeof msg === 'string' && msg) return msg.replace(/^(?:Value error|Assertion failed), /, '') || msg
  }
  return undefined
}

// Determine API URL: prefer env var, fallback based on environment
export const getApiUrl = () => {
  // Always use environment variable if set (for production deployments)
  if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL
  }
  // For client-side: check window location
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return 'http://localhost:8000'
    }
  }
  // For server-side: check NODE_ENV
  if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000'
  }
  // Default to production API
  return 'https://api.earningsnerd.io'
}

// Get the API URL - for client-side this will be determined at runtime
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return getApiUrl()
  }
  // Server-side: use localhost in development
  return process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://api.earningsnerd.io'
}

// Create axios instance with baseURL
const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
  withCredentials: true,
})

type SessionRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean; _sessionGeneration?: number; _sessionWasActive?: boolean }

// Set baseURL dynamically on each request (for client-side)
api.interceptors.request.use((config: SessionRequestConfig) => {
  config._sessionGeneration ??= getSessionGeneration()
  config._sessionWasActive ??= hasActiveSession()
  // Always set baseURL dynamically to ensure correct URL in client-side
  if (typeof window !== 'undefined') {
    config.baseURL = getApiUrl()
  }
  return config
})

// Endpoints whose own 401s must never trigger a silent refresh (the refresh itself, plus
// the credential-issuing endpoints — a failed login is not an expired session).
const NO_REFRESH_PATHS = [
  '/api/auth/refresh',
  '/api/auth/login',
  '/api/auth/register',
  '/api/auth/logout',
]

// Dispatched on a 403 whose detail asks the user to verify their email, so a global
// listener (EmailVerificationModal) can show a graceful prompt instead of a raw error.
export const EMAIL_VERIFICATION_REQUIRED_EVENT = 'email-verification-required'

export function isRefreshableRequest(url?: string): boolean {
  if (!url) return true
  // Match on the path only, so a query param that happens to contain an auth path
  // (e.g. ?redirect=/api/auth/login) doesn't wrongly mark the request non-refreshable.
  const pathname = url.split('?')[0]
  return !NO_REFRESH_PATHS.some((path) => pathname.includes(path))
}

// Single in-flight refresh shared across concurrent 401s, so a burst of requests that all
// expire together triggers exactly one /refresh call rather than a stampede. Exported so the
// sanctioned raw-fetch SSE path (features/summaries/api) shares this ONE promise — otherwise a
// concurrent 401 there + here would fire two /refresh calls on the same single-use rotating
// refresh token, and the loser would 401 and log the user out.
let refreshPromise: Promise<void> | null = null
let refreshGeneration: number | null = null

export function ensureRefreshed(): Promise<void> {
  const generation = getSessionGeneration()
  // Wait out an earlier account's refresh, without interpreting its result as this account's
  // result or starting concurrent rotating-cookie refreshes. This does not control Set-Cookie.
  if (refreshPromise && refreshGeneration !== generation) {
    return refreshPromise.catch(() => undefined).then(() => {
      assertSessionGeneration(generation)
      return ensureRefreshed()
    })
  }
  if (!refreshPromise) {
    refreshGeneration = generation
    refreshPromise = refreshAccessToken(getApiUrl()).finally(() => {
      refreshPromise = null
      refreshGeneration = null
    })
  }
  return refreshPromise
}

/**
 * Settles once the refresh in flight, if any, has answered, whatever its outcome, or once `limitMs` has passed.
 * A logout waits on it before it posts: the refresh's answer sets the session cookies, and one that lands after
 * the logout's answer sets them again, the access token among them, which keeps the tab signed in until that
 * token expires (E133). The limit keeps a refresh that never answers from holding the logout.
 */
export function refreshSettled(limitMs: number): Promise<void> {
  const inFlight = refreshPromise
  if (!inFlight) return Promise.resolve()
  let timer: ReturnType<typeof setTimeout> | undefined
  const limit = new Promise<void>((resolve) => { timer = setTimeout(resolve, limitMs) })
  return Promise.race([inFlight.then(() => undefined, () => undefined), limit]).finally(() => clearTimeout(timer))
}

// Response error interceptor: silent token refresh on 401, then backend error extraction.
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: unknown }>) => {
    // Extract the status code and detail message from the backend
    const status = error.response?.status || 0
    const original = error.config as SessionRequestConfig | undefined
    const generation = original?._sessionGeneration ?? getSessionGeneration()
    let sessionLossConfirmed: boolean | undefined
    const currentGeneration = () => isSessionGenerationCurrent(generation)

    // Expired access token on a logged-in session: refresh once and replay the request.
    // Gated on hasActiveSession() so guests never attempt a (pointless) refresh, and on
    // _retry so a request is only ever retried a single time.
    if (
      status === 401 &&
      currentGeneration() &&
      original &&
      !original._retry &&
      isRefreshableRequest(original.url) &&
      original._sessionWasActive &&
      hasActiveSession()
    ) {
      original._retry = true
      let refreshed = false
      try {
        await ensureRefreshed()
        refreshed = true
      } catch (refreshError) {
        // Network/429/5xx failures do not prove the refresh session is gone. Keep the marker
        // so a later request can recover, and classify BEFORE /me interprets this access 401.
        sessionLossConfirmed = getErrorStatus(refreshError) === 401
      }
      // Replay outside the try: an error from the *retried* request (e.g. 500/429, or a
      // persistent 401) must propagate as-is, not be mistaken for a refresh failure.
      if (refreshed && currentGeneration()) {
        return await api(original)
      }
    }

    if (status === 401 && isRefreshableRequest(original?.url) && currentGeneration()) {
      sessionLossConfirmed ??= true
      if (sessionLossConfirmed && original?._sessionWasActive) notifySessionLost(generation)
    }

    const backendDetail = detailMessage(error.response?.data?.detail)

    // Surface the email-verification gate as a friendly global prompt (e.g. on checkout).
    if (
      status === 403 &&
      backendDetail &&
      /verify your email/i.test(backendDetail) &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new CustomEvent(EMAIL_VERIFICATION_REQUIRED_EVENT, { detail: backendDetail }))
    }

    // Create user-friendly error message based on status and backend detail
    let errorMessage: string

    if (backendDetail) {
      // Use the backend's user-friendly message
      errorMessage = backendDetail
    } else if (status === 503) {
      errorMessage = 'Service temporarily unavailable. Please try again in a moment.'
    } else if (status === 429) {
      errorMessage = 'Too many requests. Please wait a moment before trying again.'
    } else if (status === 404) {
      errorMessage = 'The requested resource was not found.'
    } else if (status >= 500) {
      errorMessage = 'A server error occurred. Please try again later.'
    } else if (error.message?.includes('Network Error') || error.message?.includes('ECONNREFUSED')) {
      errorMessage = 'Could not reach the server. Try again in a moment.'
    } else if (error.message?.includes('timeout')) {
      errorMessage = 'The request timed out. Please try again.'
    } else {
      errorMessage = error.message || 'An unexpected error occurred.'
    }

    // Throw our custom ApiError with the extracted details
    const apiError = new ApiError(status, errorMessage)
    apiError.sessionLossConfirmed = sessionLossConfirmed
    if (typeof backendDetail === 'string' && backendDetail) apiError.backendDetail = backendDetail
    throw apiError
  }
)

export default api

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

// Custom error class that preserves backend error details
export class ApiError extends Error {
  status: number
  detail: string
  isRetryable: boolean

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    // 503 (Service Unavailable), 429 (Rate Limited), and 5xx errors are retryable
    this.isRetryable = status === 503 || status === 429 || (status >= 500 && status < 600)
  }
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

// Set baseURL dynamically on each request (for client-side)
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    config.baseURL = getApiUrl()
  }
  return config
})

// ─── Auto-refresh interceptor ────────────────────────────────────────────────
// On 401: silently call /api/auth/refresh (uses the httpOnly refresh cookie),
// then retry the original request. If refresh also fails, redirect to /login.

type RetryConfig = InternalAxiosRequestConfig & { _retried?: boolean }

let isRefreshing = false
let refreshQueue: Array<{ resolve: () => void; reject: (err: unknown) => void }> = []

function flushQueue() {
  refreshQueue.forEach(({ resolve }) => resolve())
  refreshQueue = []
}

function rejectQueue(err: unknown) {
  refreshQueue.forEach(({ reject }) => reject(err))
  refreshQueue = []
}

// Auth endpoints that must never trigger a refresh attempt
const AUTH_SKIP = ['/api/auth/login', '/api/auth/refresh', '/api/auth/logout', '/api/auth/register']

// Dispatched on a 403 whose detail asks the user to verify their email, so a
// global listener (EmailVerificationModal) can show a graceful prompt.
export const EMAIL_VERIFICATION_REQUIRED_EVENT = 'email-verification-required'

// ─── Response interceptor ────────────────────────────────────────────────────

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const originalRequest = error.config as RetryConfig | undefined
    const status = error.response?.status ?? 0
    const url = originalRequest?.url ?? ''

    // Attempt silent token refresh on 401, except for auth endpoints themselves
    const shouldRefresh =
      status === 401 &&
      originalRequest &&
      !originalRequest._retried &&
      !AUTH_SKIP.some((path) => url.includes(path))

    if (shouldRefresh) {
      if (isRefreshing) {
        // Queue request until refresh completes
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: () => {
              originalRequest._retried = true
              resolve(api(originalRequest))
            },
            reject,
          })
        })
      }

      originalRequest._retried = true
      isRefreshing = true

      try {
        await api.post('/api/auth/refresh')
        flushQueue()
        isRefreshing = false
        return api(originalRequest)
      } catch (refreshErr) {
        rejectQueue(refreshErr)
        isRefreshing = false
        // Refresh token is expired or invalid — force re-login
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
        throw new ApiError(401, 'Your session has expired. Please log in again.')
      }
    }

    // ─── Standard error handling ──────────────────────────────────────────────
    const backendDetail = error.response?.data?.detail

    // Surface the email-verification gate as a friendly global prompt
    if (
      status === 403 &&
      backendDetail &&
      /verify your email/i.test(backendDetail) &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new CustomEvent(EMAIL_VERIFICATION_REQUIRED_EVENT, { detail: backendDetail }))
    }

    let errorMessage: string

    if (backendDetail) {
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
      errorMessage = `Unable to connect to the server. Please ensure the backend API is running on ${getApiUrl()}`
    } else if (error.message?.includes('timeout')) {
      errorMessage = 'The request timed out. Please try again.'
    } else {
      errorMessage = error.message || 'An unexpected error occurred.'
    }

    throw new ApiError(status, errorMessage)
  }
)

export default api

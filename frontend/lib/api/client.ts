import axios, { AxiosError } from 'axios'

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
  // Always set baseURL dynamically to ensure correct URL in client-side
  if (typeof window !== 'undefined') {
    config.baseURL = getApiUrl()
  }
  return config
})

// Response error interceptor to extract backend error details
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    // Extract the status code and detail message from the backend
    const status = error.response?.status || 0
    const backendDetail = error.response?.data?.detail

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
      errorMessage = `Unable to connect to the server. Please ensure the backend API is running on ${getApiUrl()}`
    } else if (error.message?.includes('timeout')) {
      errorMessage = 'The request timed out. Please try again.'
    } else {
      errorMessage = error.message || 'An unexpected error occurred.'
    }

    // Throw our custom ApiError with the extracted details
    throw new ApiError(status, errorMessage)
  }
)

export default api

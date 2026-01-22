import axios from 'axios'

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

export default api

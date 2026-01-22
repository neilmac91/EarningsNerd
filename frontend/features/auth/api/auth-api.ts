import api from '@/lib/api/client'

// Auth APIs
export const register = async (email: string, password: string, fullName?: string) => {
  const response = await api.post('/api/auth/register', {
    email,
    password,
    full_name: fullName,
  })
  return response.data
}

export const login = async (email: string, password: string) => {
  const response = await api.post('/api/auth/login', {
    email,
    password,
  })
  return response.data
}

export const getCurrentUser = async () => {
  const response = await api.get('/api/auth/me')
  return response.data
}

export const getCurrentUserSafe = async () => {
  try {
    return await getCurrentUser()
  } catch (error: unknown) {
    const axiosErr = error as { response?: { status?: number } }
    if (axiosErr.response?.status === 401) {
      return null
    }
    throw error
  }
}

export const logout = async () => {
  const response = await api.post('/api/auth/logout')
  return response.data
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

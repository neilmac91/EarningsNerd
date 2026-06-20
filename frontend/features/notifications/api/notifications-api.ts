import api from '@/lib/api/client'

export interface NotificationPreferences {
  notify_10k: boolean
  notify_10q: boolean
  notify_8k: boolean
  channel: string
  digest: string
  realtime: boolean
  // Effective gating (server-derived) so the UI can lock Pro-only toggles.
  realtime_available: boolean
  eightk_available: boolean
}

export type NotificationPreferencesUpdate = Partial<
  Pick<NotificationPreferences, 'notify_10k' | 'notify_10q' | 'notify_8k' | 'channel' | 'digest' | 'realtime'>
>

export const getNotificationPreferences = async (): Promise<NotificationPreferences> => {
  const response = await api.get('/api/users/me/notification-preferences')
  return response.data
}

export const updateNotificationPreferences = async (
  update: NotificationPreferencesUpdate,
): Promise<NotificationPreferences> => {
  const response = await api.put('/api/users/me/notification-preferences', update)
  return response.data
}

// In-app notification bell ------------------------------------------------------

export interface NotificationItem {
  id: number
  filing_id: number
  ticker: string
  company_name: string
  filing_type: string
  filing_date: string | null
  created_at: string | null
  read: boolean
}

export interface NotificationList {
  items: NotificationItem[]
  unread_count: number
}

export const getNotifications = async (): Promise<NotificationList> => {
  const response = await api.get('/api/users/me/notifications')
  return response.data
}

/** Mark the bell as opened (resets the unread count). Returns the now-read recent list. */
export const markNotificationsSeen = async (): Promise<NotificationList> => {
  const response = await api.post('/api/users/me/notifications/seen')
  return response.data
}

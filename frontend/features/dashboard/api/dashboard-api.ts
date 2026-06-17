import api from '@/lib/api/client'

export interface WhatChangedItem {
  metric: string
  label: string
  direction: 'up' | 'down' | 'flat'
  pct: number | null
  current: number
  prior: number | null
}

export interface WhatChanged {
  headline: string
  items: WhatChangedItem[]
  data_quality: 'ok' | 'partial'
}

export interface FeedItem {
  filing_id: number
  accession_number: string | null
  company: { id: number; ticker: string; name: string }
  filing_type: string
  filing_date: string | null
  period_end_date: string | null
  summary_id: number | null
  summary_status: string
  what_changed: WhatChanged | null
}

export interface CalendarEvent {
  ticker: string
  company_name: string
  earnings_date: string | null
  time: string | null
  eps_estimated: number | null
  revenue_estimated: number | null
}

export const getDashboardFeed = async (limit = 20): Promise<FeedItem[]> => {
  const response = await api.get('/api/dashboard/feed', { params: { limit } })
  return response.data.items
}

export const getUpcomingCalendar = async (days = 14): Promise<CalendarEvent[]> => {
  const response = await api.get('/api/dashboard/calendar/upcoming', { params: { days } })
  return response.data.events
}

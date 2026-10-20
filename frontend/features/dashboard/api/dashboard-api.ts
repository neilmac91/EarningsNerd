import api from '@/lib/api/client'

export interface WhatChangedItem {
  metric: string
  label: string
  direction: 'up' | 'down' | 'flat'
  pct: number | null
  current: number
  prior: number | null
  // Server-computed display string (one delta policy) + design-system tone; rendered verbatim.
  display: string
  tone: 'gain' | 'loss' | 'flat'
}

export interface WhatChanged {
  headline: string
  items: WhatChangedItem[]
  data_quality: 'ok' | 'partial'
}

/** The Item 1A wording-change counts of the filing's cached comparison, served behind
 *  ENABLE_SECTION_CHANGES to a viewer with access (null otherwise, and while the filing has no
 *  comparison yet); `review` is the viewer's own progress, for a Pro reader only. */
export interface WordingChangesSummary {
  items_total: number
  has_changes: boolean
  /** The filing's own section only refers back to the annual report: nothing to compare. */
  reference_only: boolean
  /** The prior filing's section only referred back, so every paragraph reads as new. */
  prior_reference_only: boolean
  review: { labeled: number; completed_at: string | null } | null
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
  wording_changes?: WordingChangesSummary | null
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

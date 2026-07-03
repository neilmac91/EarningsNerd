import api from '@/lib/api/client'

/* =============================================================================
   Earnings calendar — typed API client (features/calendar/api/calendar-api.ts)
   -----------------------------------------------------------------------------
   Contract per tasks/earnings-calendar-strategy.md §3.3 / §3.7:
     GET  /api/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD          (public)
     POST /api/watchlist/{ticker}/earnings-alert                (enable, auth)
     DELETE /api/watchlist/{ticker}/earnings-alert              (disable, auth)
   `event_date` is an America/New_York CALENDAR DAY — treat it as a plain
   string everywhere; render with formatLocalDate (never `new Date(iso)`).

   Fixtures: set NEXT_PUBLIC_CALENDAR_FIXTURES='true' to run the whole page
   against ./calendar-fixtures.ts (dynamic import — fixture code never enters
   the production bundle when the flag is off).
============================================================================= */

export type EventTime = 'bmo' | 'amc' | 'dmh' | null
export type EventStatus = 'estimated' | 'confirmed' | 'reported'
export type EventConfidence = 'high' | 'medium' | 'low'

export interface CalendarEvent {
  ticker: string
  company_name: string
  /** America/New_York calendar day, YYYY-MM-DD. */
  event_date: string
  event_time: EventTime
  status: EventStatus
  confidence: EventConfidence
  eps_estimate: number | null
  eps_actual: number | null
  anticipation_score: number
}

export const USE_CALENDAR_FIXTURES = process.env.NEXT_PUBLIC_CALENDAR_FIXTURES === 'true'

export const getCalendar = async (from: string, to: string): Promise<CalendarEvent[]> => {
  if (USE_CALENDAR_FIXTURES) {
    const fixtures = await import('./calendar-fixtures')
    return fixtures.fixtureCalendar(from, to)
  }
  const response = await api.get('/api/calendar', { params: { from, to } })
  return response.data.events
}

/** Tickers the signed-in user has earnings alerts enabled for.
    ASSUMPTION (README §Assumptions): served from the Watchlist rows'
    `earnings_alert` flag (strategy §3.7 models the subscription as
    `Watchlist.earnings_alert BOOLEAN`). */
export const getEarningsAlertTickers = async (): Promise<string[]> => {
  if (USE_CALENDAR_FIXTURES) {
    const fixtures = await import('./calendar-fixtures')
    return fixtures.fixtureAlertTickers()
  }
  const response = await api.get('/api/watchlist/earnings-alerts')
  return response.data.tickers
}

/** Machine-readable code the backend attaches to the FREE-plan cap 403
    (strategy §3.7). The PRO cap 403 is a terse generic message with NO code —
    the frontend must render it verbatim and never pre-empt it. */
export const EARNINGS_ALERT_LIMIT_CODE = 'earnings_alert_limit'

export class EarningsAlertError extends Error {
  readonly status: number
  readonly code?: string
  constructor(status: number, detail: string, code?: string) {
    super(detail)
    this.name = 'EarningsAlertError'
    this.status = status
    this.code = code
  }
}

/* The shared axios client's interceptor collapses error bodies to
   ApiError(status, detail-string), which would drop the machine-readable
   `code`. Rather than refactor the shared client, the toggle accepts 403 as a
   non-throwing status (per-request validateStatus) and classifies the body
   itself. 401s still throw through the interceptor, so the silent-refresh
   flow is untouched. */
const ACCEPT_403 = {
  validateStatus: (s: number) => (s >= 200 && s < 300) || s === 403,
}

export const enableEarningsAlert = async (ticker: string): Promise<void> => {
  if (USE_CALENDAR_FIXTURES) {
    const fixtures = await import('./calendar-fixtures')
    return fixtures.fixtureEnableAlert(ticker)
  }
  const res = await api.post(`/api/watchlist/${encodeURIComponent(ticker)}/earnings-alert`, null, ACCEPT_403)
  if (res.status === 403) {
    const data = (res.data ?? {}) as { detail?: string; code?: string }
    throw new EarningsAlertError(403, data.detail ?? 'Could not enable this alert.', data.code)
  }
}

export const disableEarningsAlert = async (ticker: string): Promise<void> => {
  if (USE_CALENDAR_FIXTURES) {
    const fixtures = await import('./calendar-fixtures')
    return fixtures.fixtureDisableAlert(ticker)
  }
  // Disabling is always allowed (strategy §3.7); real errors propagate as ApiError.
  await api.delete(`/api/watchlist/${encodeURIComponent(ticker)}/earnings-alert`)
}

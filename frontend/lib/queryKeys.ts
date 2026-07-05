/**
 * Central React Query key registry (roadmap F1).
 *
 * ONE place that builds every query key, so a key and the code that invalidates it can never drift.
 * Rules:
 *  - No-arg entities are functions too (`queryKeys.watchlist()`), for a uniform call style.
 *  - Parametrized entities are factories returning `as const` tuples (stable literal types).
 *  - Reconciled entities (F1) each collapse a former split into ONE key + ONE fetcher:
 *      • currentUser  — was ['user'] AND ['current-user'] with two different fetchers (a split-brain
 *        cache). Canonical key ['current-user']; canonical fetcher getCurrentUserSafe (null on 401).
 *      • subscription — was ['subscription'] and ['subscription', user?.id]; the id was never used to
 *        fetch. Canonical key ['subscription'].
 *      • usage        — was ['usage'] AND ['copilot-usage'] hitting the SAME /usage endpoint, so a
 *        copilot answer left the dashboard's usage view stale. Canonical key ['usage'].
 *
 * Grep-gate (F1 done-criterion): no string-literal query keys for the reconciled entities
 * (user / current-user / subscription / usage / copilot-usage) anywhere outside this file.
 */
export const queryKeys = {
  // ── Reconciled (F1) ──────────────────────────────────────────────────────────
  currentUser: () => ['current-user'] as const,
  subscription: () => ['subscription'] as const,
  usage: () => ['usage'] as const,

  // ── No-arg entities ──────────────────────────────────────────────────────────
  savedSummaries: () => ['saved-summaries'] as const,
  watchlist: () => ['watchlist'] as const,
  watchlistInsights: () => ['watchlist-insights'] as const,
  earningsAlertTickers: () => ['earnings-alert-tickers'] as const,
  adminInvites: () => ['admin-invites'] as const,
  dashboardFeed: () => ['dashboard-feed'] as const,
  dashboardCalendar: () => ['dashboard-calendar'] as const,
  trendingTickers: () => ['trending-tickers'] as const,
  notifications: () => ['notifications'] as const,
  notificationPreferences: () => ['notification-preferences'] as const,
  authConnections: () => ['auth-connections'] as const,

  // ── Parametrized factories ───────────────────────────────────────────────────
  insiders: (ticker: string, windowDays: number) => ['insiders', ticker, windowDays] as const,
  peers: (ticker: string, metric: string) => ['peers', ticker, metric] as const,
  calendar: (from: string, to: string) => ['calendar', from, to] as const,
  fullTextSearch: (query: string, forms: string | undefined, startDate: string, endDate: string) =>
    ['full-text-search', query, forms, startDate, endDate] as const,
  filingFundamentals: (filingId: string | number) => ['filing-fundamentals', filingId] as const,
  // admin-feedback keeps a shared prefix so the prefix-invalidation in FeedbackRow catches every
  // filtered variant (TanStack partial-match): invalidate `all()`, query with `list(filters)`.
  adminFeedback: {
    all: () => ['admin-feedback'] as const,
    list: (filters: unknown) => ['admin-feedback', filters] as const,
  },
  tickerCompany: (ticker: string) => ['ticker-company', ticker] as const,
  tickerFilings: (ticker: string) => ['ticker-filings', ticker] as const,
  filing: (filingId: string | number) => ['filing', filingId] as const,
  summary: (filingId: string | number) => ['summary', filingId] as const,
  summaryProgress: (filingId: string | number) => ['summary-progress', filingId] as const,
  whatChanged: (filingId: string | number) => ['what-changed', filingId] as const,
  company: (ticker: string) => ['company', ticker] as const,
  companyFilings: (ticker: string) => ['filings', ticker] as const,
  companies: (query: string) => ['companies', query] as const,
  hotFilings: (limit: number) => ['hot-filings', limit] as const,
} as const

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
 *      • subscription — identity scopes the cache even though the HTTP request uses cookies.
 *        Read byUser(id); invalidate/cancel/remove through the all() family prefix.
 *      • usage        — was ['usage'] AND ['copilot-usage'] hitting the SAME /usage endpoint, so a
 *        copilot answer left the dashboard's usage view stale. One identity-scoped usage family, including Copilot counters.
 *
 * Grep-gate (F1 done-criterion): no string-literal query keys for the reconciled entities
 * (user / current-user / subscription / usage / copilot-usage) anywhere outside this file.
 */
export const queryKeys = {
  // ── Reconciled (F1) ──────────────────────────────────────────────────────────
  currentUser: () => ['current-user'] as const,
  subscription: {
    all: () => ['subscription'] as const,
    byUser: (userId: number | undefined) => ['subscription', userId] as const,
  },
  usage: {
    all: () => ['usage'] as const,
    byUser: (userId: number | undefined) => ['usage', userId] as const,
  },

  // ── No-arg entities ──────────────────────────────────────────────────────────
  savedSummaries: () => ['saved-summaries'] as const,
  watchlist: () => ['watchlist'] as const,
  watchlistInsights: () => ['watchlist-insights'] as const,
  earningsAlertTickers: () => ['earnings-alert-tickers'] as const,
  adminInvites: () => ['admin-invites'] as const,
  dashboardFeed: () => ['dashboard-feed'] as const,
  dashboardCalendar: () => ['dashboard-calendar'] as const,
  notifications: () => ['notifications'] as const,
  notificationPreferences: () => ['notification-preferences'] as const,
  authConnections: () => ['auth-connections'] as const,
  /** The public registration gate (/api/auth/registration): invite-only or public, read by surfaces
   *  that offer an account CTA on the client (the pricing page), so none advertises a signup the
   *  API would reject (features/marketing/lib/access.ts). */
  registrationConfig: () => ['registration-config'] as const,
  /** Cloudflare's Turnstile script, loaded once a page by TurnstileWidget: a load that fails is its notice's
   *  Try again, as a failed read's is. */
  turnstileScript: () => ['turnstile-script'] as const,

  // Same prefix as the library: save/delete invalidation refreshes every saved-state consumer.
  savedSummaryStatus: (summaryId: number | undefined, userId: number | undefined) =>
    ['saved-summaries', 'status', userId, summaryId] as const,

  // ── Parametrized factories ───────────────────────────────────────────────────
  insiders: (ticker: string, windowDays: number) => ['insiders', ticker, windowDays] as const,
  peers: (ticker: string, metric: string) => ['peers', ticker, metric] as const,
  calendar: (from: string, to: string) => ['calendar', from, to] as const,
  fullTextSearch: (query: string, forms: string | undefined, startDate: string, endDate: string) =>
    ['full-text-search', query, forms, startDate, endDate] as const,
  filingFundamentals: (filingId: string | number) => ['filing-fundamentals', filingId] as const,
  // admin-feedback keeps a shared prefix so the prefix-invalidation in FeedbackRow catches every
  // filtered variant (TanStack partial-match): invalidate `all()`, query with `list(filters)`.
  feedback: {
    all: () => ['feedback'] as const,
    capabilities: (readerId: number) => ['feedback', 'capabilities', readerId] as const,
    submission: (readerId: number, generation: number, key: string | null) => ['feedback', 'submission', readerId, generation, key] as const,
  },
  adminFeedback: {
    attachment: (readerId: number, generation: number, id: string) => ['admin-feedback', 'attachment', readerId, generation, id] as const,
    all: () => ['admin-feedback'] as const,
    list: (filters: unknown) => ['admin-feedback', filters] as const,
  },
  analysisCoverage: (ticker: string | null) => ['analysis-coverage', ticker] as const,
  // /analysis?ticker= resolves its link under its own key, as TickerFilingsView does with tickerCompany.
  // On `company` the company page's loading gate would read a query two modules observe
  // (spinnerGateHoldsFailure.spec.ts), although the two pages never mount together.
  analysisCompany: (ticker: string) => ['analysis-company', ticker] as const,
  tickerCompany: (ticker: string) => ['ticker-company', ticker] as const,
  tickerFilings: (ticker: string) => ['ticker-filings', ticker] as const,
  filing: (filingId: string | number) => ['filing', filingId] as const,
  filingContent: (filingId: number) => ['filing-content', filingId] as const,
  summary: (filingId: string | number) => ['summary', filingId] as const,
  summaryProgress: (filingId: string | number) => ['summary-progress', filingId] as const,
  // The change report differs by viewer: a Pro reader gets every Item 1A wording change, everyone
  // else the teaser. The key carries the signed-in reader's id (null for anonymous), so anonymous
  // readers share one entry (the one the filing page seeds from its server read) and no signed-in
  // reader's own read overwrites it. Read through features/summaries/hooks/useWhatChanged. A reader
  // whose /me failed reads under the anonymous key with their own session, so the family is removed
  // on logout and login (features/auth/lib/accountQueryState); the seed returns as initial data.
  whatChanged: {
    all: () => ['what-changed'] as const,
    byViewer: (filingId: string | number, viewerId: number | null) => ['what-changed', filingId, viewerId] as const,
  },
  // The signed-in Pro reader's own review of a filing's wording changes (labels, receipt); read
  // only with the full change list in front of them (features/summaries/hooks/useWordingReview).
  // One family, removed with the account's other snapshots on logout and login
  // (features/auth/lib/accountQueryState), so the next account in this tab never sees these labels.
  wordingReview: {
    all: () => ['wording-review'] as const,
    byFiling: (filingId: string | number) => ['wording-review', filingId] as const,
  },
  company: (ticker: string) => ['company', ticker] as const,
  companyFilings: (ticker: string, limit?: number) => ['filings', ticker, limit ?? null] as const,
  companies: (query: string) => ['companies', query] as const,
} as const

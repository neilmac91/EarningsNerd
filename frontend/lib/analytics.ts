import posthog from 'posthog-js'
import * as Sentry from '@sentry/nextjs'

const safeCapture = (event: string, properties?: Record<string, unknown>) => {
  if (typeof window === 'undefined') {
    return
  }
  posthog.capture(event, properties)
}

const safeIdentify = (userId: string, traits?: Record<string, unknown>) => {
  if (typeof window === 'undefined') {
    return
  }
  posthog.identify(userId, traits)
  // Mirror the identity into Sentry so client errors are attributable to the same user id the
  // backend tags (str(user.id)). Id only — no PII beyond the internal id. Never let it throw.
  try {
    Sentry.setUser({ id: userId })
  } catch {
    /* monitoring must never break the app */
  }
}

const safeReset = () => {
  if (typeof window === 'undefined') {
    return
  }
  posthog.reset()
  try {
    Sentry.setUser(null)
  } catch {
    /* monitoring must never break the app */
  }
}

export const analytics = {
  identify: (userId: string, traits?: Record<string, unknown>) => {
    safeIdentify(userId, traits)
  },

  reset: () => {
    safeReset()
  },

  signupStarted: (source?: string) => {
    safeCapture('signup_started', { source: source || 'direct' })
  },

  signupCompleted: (userId: string) => {
    // Identify on the internal id only — no email/PII into PostHog person properties.
    safeIdentify(userId, {
      plan: 'free',
      signup_date: new Date().toISOString(),
    })
    safeCapture('signup_completed')
  },

  // Verify-first signup: register no longer auto-logs-in, so there's no user id to identify
  // yet. Capture an anonymous "submitted" step; identify happens later at login/verify and
  // PostHog stitches the anonymous events to the person.
  signupSubmitted: () => {
    safeCapture('signup_submitted')
  },

  loginCompleted: (userId: string) => {
    // Identify on the internal id only — no email/PII into PostHog person properties.
    safeIdentify(userId)
    safeCapture('login_completed')
  },

  logout: () => {
    safeCapture('logout')
    safeReset()
  },

  companySearched: (query: string, resultsCount: number) => {
    safeCapture('company_searched', {
      query,
      results_count: resultsCount,
    })
  },

  // Closes the search→navigation loop: fired when a user actually selects a result, so
  // search → company_viewed conversion is causal (not just inferred from a later page view).
  companySearchResultClicked: (query: string, ticker: string, position: number) => {
    safeCapture('company_search_result_clicked', {
      query,
      ticker,
      position,
    })
  },

  companyViewed: (ticker: string, name: string, entryPoint?: string) => {
    safeCapture('company_viewed', { ticker, name, entry_point: entryPoint })
  },

  // Activation funnel: zero-effort entry — a visitor clicks through to the
  // pre-generated example summary instead of searching.
  exampleCtaClicked: (placement: string, target: string) => {
    safeCapture('example_cta_clicked', { placement, target })
  },

  filingViewed: (
    filingId: number,
    ticker: string | null,
    filingType: string,
    entryPoint?: string,
  ) => {
    safeCapture('filing_viewed', {
      filing_id: filingId,
      ticker,
      filing_type: filingType,
      entry_point: entryPoint,
    })
  },

  summaryGenerated: (ticker: string | null, filingType: string, filingId: number) => {
    safeCapture('summary_generated', {
      ticker,
      filing_type: filingType,
      filing_id: filingId,
    })
  },

  // Activation funnel: fired when a visitor actually sees summary content.
  // Generation outcomes (generation_started/succeeded/failed/timed_out) are
  // captured server-side with the same distinct_id (forwarded on the stream
  // request) so the funnel joins on one person without double counting.
  summaryViewed: (props: {
    filingId: number
    ticker: string | null
    filingType: string
    entryPoint: string
    resultType?: string
    qualityVerdict?: string
    durationMs?: number
  }) => {
    safeCapture('summary_viewed', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      entry_point: props.entryPoint,
      result_type: props.resultType,
      quality_verdict: props.qualityVerdict,
      duration_ms: props.durationMs,
    })
  },

  // Activation funnel: the visitor was actually shown the upgrade wall (free/guest limit
  // reached). Distinct from the server-side `paywall_hit` (which records the limit check
  // failing) — this is the client-confirmed UX moment, so the two must not be conflated.
  paywallPromptShown: (props: {
    filingId: number
    ticker: string | null
    filingType: string
    entryPoint: string
  }) => {
    safeCapture('paywall_prompt_shown', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      entry_point: props.entryPoint,
    })
  },

  // The visitor clicked an upgrade CTA on a Copilot paywall surface (the FREE teaser or a monthly-
  // limit error). Pairs with `paywall_prompt_shown` to measure shown → clicked conversion intent.
  paywallCtaClicked: (props: {
    filingId: number
    ticker: string | null
    filingType: string
    entryPoint: string
  }) => {
    safeCapture('paywall_cta_clicked', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      entry_point: props.entryPoint,
    })
  },

  // "Ask this Filing" Copilot funnel + answer quality. `copilot_question_asked` opens the funnel;
  // `copilot_answer_completed` carries the quality signals (grounded count, not-disclosed rate,
  // XBRL tool-use) so we can monitor honesty/accuracy in aggregate. Pairs with `paywall_prompt_shown`
  // (entry_point "copilot_rail") for FREE→Pro conversion.
  copilotQuestionAsked: (props: { filingId: number; ticker: string | null; filingType: string }) => {
    safeCapture('copilot_question_asked', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
    })
  },

  /** Multi-Period Analysis: a Pro user kicked off a run (dataset + narrative). */
  analysisRun: (props: { ticker: string; mode: string; start: string; end: string }) => {
    safeCapture('analysis_generated', {
      ticker: props.ticker,
      mode: props.mode,
      start_period: props.start,
      end_period: props.end,
    })
  },

  /** A user successfully downloaded an export artifact (fired AFTER the blob/file lands, so the
   *  event measures deliveries, not attempts). `surface` names the feature; the GDPR account-data
   *  export (`dataExported`) is deliberately a separate event and must not be reused here. */
  exportGenerated: (props: {
    surface: 'analysis' | 'filing_summary'
    format: 'pdf' | 'png' | 'xlsx' | 'csv'
    ticker?: string | null
    mode?: string
    periodKey?: string
    /** Chart panel title (PNG exports only). */
    panel?: string
    filingId?: number
  }) => {
    safeCapture('export_generated', {
      surface: props.surface,
      format: props.format,
      ticker: props.ticker,
      mode: props.mode,
      period_key: props.periodKey,
      panel: props.panel,
      filing_id: props.filingId,
    })
  },

  copilotAnswerCompleted: (props: {
    filingId: number
    ticker: string | null
    filingType: string
    kind: 'answer' | 'not_disclosed'
    grounded: number
    citations: number
    usedXbrl: boolean
  }) => {
    safeCapture('copilot_answer_completed', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      kind: props.kind,
      not_disclosed: props.kind === 'not_disclosed',
      grounded: props.grounded,
      citations: props.citations,
      used_xbrl: props.usedXbrl,
    })
  },

  copilotAnswerErrored: (props: { filingId: number; message: string }) => {
    safeCapture('copilot_answer_errored', {
      filing_id: props.filingId,
      message: props.message,
    })
  },

  // A non-launcher Ask affordance opened the Copilot: the end-of-summary callout, a starter chip, a
  // tappable suggested follow-up, the first-run coachmark, or a text-selection action. `surface`
  // attributes which surface drove the open so discovery can be measured per entry point.
  copilotEntryClicked: (props: { filingId: number; ticker: string | null; filingType: string; surface: string }) => {
    safeCapture('copilot_entry_clicked', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      surface: props.surface,
    })
  },

  // Activation DEPTH (item 1.8): the user clicked a Copilot citation ([n] / [F#]) to verify a claim
  // against its source — the in-app viewer scroll-flash-highlights the cited passage
  // (action 'scroll_highlight'), or the no-viewer FREE teaser opens the SEC deep link
  // ('open_original'). Distinct from `summary_viewed` (summary merely rendered): this measures the
  // click-to-source "aha" — the verifiability moment the product is built on. `citation_kind`
  // separates XBRL figure citations from filing-text excerpts; `verified` is the backend's claim.
  sourceSpanClicked: (props: {
    filingId: number
    ticker: string | null
    filingType: string
    citationIndex: string
    citationKind: 'xbrl' | 'text'
    verified: boolean
    action: 'scroll_highlight' | 'open_original'
  }) => {
    safeCapture('source_span_click', {
      filing_id: props.filingId,
      ticker: props.ticker,
      filing_type: props.filingType,
      citation_index: props.citationIndex,
      citation_kind: props.citationKind,
      verified: props.verified,
      action: props.action,
    })
  },

  summarySaved: (filingId: number, ticker: string | null) => {
    safeCapture('summary_saved', {
      filing_id: filingId,
      ticker,
    })
  },

  watchlistAdded: (ticker: string) => {
    safeCapture('watchlist_added', { ticker })
  },

  watchlistRemoved: (ticker: string) => {
    safeCapture('watchlist_removed', { ticker })
  },

  // Homepage section impression (IntersectionObserver, once per pageview) — the denominator for
  // per-section CTR that the homepage-sections review found missing (findings §3). Section slugs:
  // 'notable_filings' | 'reporting_this_week' | ...
  homepageSectionViewed: (section: string) => {
    safeCapture('homepage_section_viewed', { section })
  },

  // A "Notable filings" card was clicked through to the company page. `reason` is the selection
  // slug (earnings_results, activist_stake, …) so CTR can be split by why the card was shown.
  notableFilingClicked: (props: { ticker: string; form: string; reason: string }) => {
    safeCapture('notable_filing_clicked', {
      ticker: props.ticker,
      form: props.form,
      reason: props.reason,
    })
  },

  // Dashboard "what changed" feed: a filing card was clicked through to its summary.
  dashboardFeedClicked: (filingId: number, ticker: string | null, filingType: string) => {
    safeCapture('dashboard_feed_clicked', {
      filing_id: filingId,
      ticker,
      filing_type: filingType,
    })
  },

  pricingViewed: (billingCycle: 'monthly' | 'yearly') => {
    safeCapture('pricing_viewed', { billing_cycle: billingCycle })
  },

  billingCycleToggled: (from: string, to: string) => {
    safeCapture('billing_cycle_toggled', { from, to })
  },

  checkoutStarted: (plan: string, price: number, billingCycle: string, variant?: string) => {
    safeCapture('checkout_started', {
      plan,
      price,
      billing_cycle: billingCycle,
      // Pricing A/B arm (roadmap 2.3) — present so the exposed→checkout funnel can split by variant.
      ...(variant ? { variant } : {}),
    })
  },

  errorOccurred: (error: string, context?: Record<string, unknown>) => {
    safeCapture('error_occurred', {
      error,
      ...context,
    })
  },

  dataExported: (userId: string) => {
    safeCapture('data_exported', { user_id: userId })
  },

  accountDeleted: (userId: string) => {
    safeCapture('account_deleted', { user_id: userId })
  },
}

export default analytics

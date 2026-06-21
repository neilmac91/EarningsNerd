import posthog from 'posthog-js'

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
}

const safeReset = () => {
  if (typeof window === 'undefined') {
    return
  }
  posthog.reset()
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

  signupCompleted: (userId: string, email: string) => {
    safeIdentify(userId, {
      email,
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

  loginCompleted: (userId: string, email: string) => {
    safeIdentify(userId, { email })
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

  checkoutStarted: (plan: string, price: number, billingCycle: string) => {
    safeCapture('checkout_started', {
      plan,
      price,
      billing_cycle: billingCycle,
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

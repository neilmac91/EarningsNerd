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

  companyViewed: (ticker: string, name: string) => {
    safeCapture('company_viewed', { ticker, name })
  },

  filingViewed: (filingId: number, ticker: string | null, filingType: string) => {
    safeCapture('filing_viewed', {
      filing_id: filingId,
      ticker,
      filing_type: filingType,
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

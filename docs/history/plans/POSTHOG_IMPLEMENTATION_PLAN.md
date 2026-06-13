# PostHog Implementation Plan

This document outlines the comprehensive plan for setting up PostHog analytics for EarningsNerd, covering event tracking, session recordings, feature flags, and conversion funnels.

## Goals

1. **Event Tracking** — Track key user actions throughout the product
2. **Session Recordings** — See exactly how users interact with the site
3. **Feature Flags** — A/B test pricing and other features
4. **Funnels** — Track waitlist → signup → paid conversion

---

## Current State

### Already Implemented

- `posthog-js` installed (v1.331.3)
- Basic provider at `frontend/app/posthog-provider.tsx`
- Manual pageview tracking enabled
- Provider wrapped in root layout via `providers.tsx`
- Environment variables: `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`

### Gaps to Address

- [ ] Session recording not enabled
- [ ] No custom events beyond pageviews
- [ ] No user identification (critical for funnels)
- [ ] Feature flags not configured
- [ ] No funnel-specific event tracking

---

## Phase 1: Enhanced PostHog Configuration

**File:** `frontend/app/posthog-provider.tsx`

Update the PostHog initialization to enable session recordings, autocapture, and feature flags:

```typescript
posthog.init(key, {
  api_host: host,
  capture_pageview: false,
  capture_pageleave: true,
  
  // Session Recording
  session_recording: {
    maskAllInputs: false,
    maskInputOptions: { password: true },
    recordCrossOriginIframes: false,
  },
  
  // Autocapture for clicks/form submissions
  autocapture: true,
  
  // Feature Flags
  bootstrap: { featureFlags: {} },
  
  // Debug mode in development
  loaded: (posthog) => {
    if (process.env.NODE_ENV === 'development') {
      posthog.debug()
    }
  },
})
```

**Status:** [ ] Not started

---

## Phase 2: User Identification

User identification links anonymous sessions to real users—essential for accurate funnel tracking.

### Implementation Points

| Event | Action | Location |
|-------|--------|----------|
| Registration | `posthog.identify(userId, { email, plan: 'free' })` | `app/register/page.tsx` |
| Login | `posthog.identify(userId, { email })` | `app/login/page.tsx` |
| Logout | `posthog.reset()` | `app/dashboard/page.tsx` |
| Page Load (authenticated) | `posthog.identify(userId)` | `app/dashboard/page.tsx` |

**Status:** [ ] Not started

---

## Phase 3: Funnel Event Tracking

### Primary Conversion Funnel

```
Waitlist → Signup → Active User → Paid Subscriber
```

### Event Schema

| Step | Event Name | Properties | File to Instrument |
|------|------------|------------|-------------------|
| 1 | `waitlist_join` | `{ source }` | Future waitlist component |
| 2 | `signup_started` | `{ source }` | `app/register/page.tsx` |
| 3 | `signup_completed` | `{ method }` | `app/register/page.tsx` |
| 4 | `login_completed` | `{ method }` | `app/login/page.tsx` |
| 5 | `summary_generated` | `{ ticker, filing_type, filing_id }` | `app/filing/[id]/page-client.tsx` |
| 6 | `pricing_viewed` | `{ billing_cycle }` | `app/pricing/page.tsx` |
| 7 | `checkout_started` | `{ plan, price, billing_cycle }` | `app/pricing/page.tsx` |
| 8 | `subscription_activated` | `{ plan, price }` | Backend webhook |

### Secondary Events (Product Usage)

| Event Name | Properties | File |
|------------|------------|------|
| `company_searched` | `{ query, results_count }` | `components/CompanySearch.tsx` |
| `company_viewed` | `{ ticker, name }` | `app/company/[ticker]/page.tsx` |
| `filing_viewed` | `{ filing_id, ticker, filing_type }` | `app/filing/[id]/page-client.tsx` |
| `watchlist_added` | `{ ticker }` | `components/` or `app/company/` |
| `watchlist_removed` | `{ ticker }` | `app/dashboard/page.tsx` |
| `summary_saved` | `{ filing_id, ticker }` | `app/filing/[id]/page-client.tsx` |
| `billing_cycle_toggled` | `{ from, to }` | `app/pricing/page.tsx` |

**Status:** [ ] Not started

---

## Phase 4: Feature Flags for A/B Testing

### Pricing Experiment Setup

**PostHog Dashboard:**
1. Create feature flag: `pricing-experiment`
2. Set up variants:
   - `control`: Current pricing ($19/mo, $190/yr)
   - `variant-a`: Alternative pricing (e.g., $29/mo, $249/yr)
3. Configure rollout percentage (start with 50/50)

**Frontend Implementation:**

```typescript
// app/pricing/page.tsx
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import posthog from 'posthog-js'

function PricingContent() {
  const pricingVariant = useFeatureFlagVariantKey('pricing-experiment')
  
  // Define prices based on variant
  const prices = pricingVariant === 'variant-a' 
    ? { monthly: 29, yearly: 249, monthlyDisplay: '$29', yearlyDisplay: '$249' }
    : { monthly: 19, yearly: 190, monthlyDisplay: '$19', yearlyDisplay: '$190' }
  
  // Track feature flag exposure
  useEffect(() => {
    if (pricingVariant) {
      posthog.capture('pricing_experiment_exposed', {
        variant: pricingVariant,
      })
    }
  }, [pricingVariant])
  
  // ... rest of component using prices object
}
```

### Future Feature Flag Ideas

| Flag Name | Purpose |
|-----------|---------|
| `pricing-experiment` | A/B test different price points |
| `new-dashboard-layout` | Test new dashboard design |
| `summary-format-v2` | Test new summary presentation |
| `onboarding-flow` | Test guided onboarding |

**Status:** [ ] Not started

---

## Phase 5: Session Recording Configuration

### PostHog Dashboard Settings

1. **Enable Session Recording** in Project Settings → Session Recording
2. **Minimum Duration:** 3 seconds (filters out bounces)
3. **Sampling Rate:** 100% initially, reduce if volume is high
4. **Console Log Capture:** Enable for debugging
5. **Network Request Capture:** Enable (mask sensitive headers)

### Privacy Configuration

```typescript
session_recording: {
  maskAllInputs: false,           // Don't mask all inputs
  maskInputOptions: { 
    password: true,               // Always mask passwords
    // email: true,               // Uncomment to mask emails
  },
  maskTextSelector: '[data-ph-mask]',  // Custom mask selector
  recordCrossOriginIframes: false,
}
```

### Recording Triggers (Optional)

Set up recording triggers in PostHog for specific events:
- Users who viewed pricing but didn't convert
- Users who hit the free summary limit
- Users who encountered errors
- First-time users

**Status:** [ ] Not started

---

## Phase 6: Analytics Utility Module

Create a centralized analytics module for consistent event tracking.

**File:** `frontend/lib/analytics.ts`

```typescript
import posthog from 'posthog-js'

export const analytics = {
  // ============================================
  // User Identification
  // ============================================
  
  identify: (userId: string, traits: Record<string, unknown>) => {
    posthog.identify(userId, traits)
  },
  
  reset: () => {
    posthog.reset()
  },
  
  // ============================================
  // Authentication Events
  // ============================================
  
  signupStarted: (source?: string) => {
    posthog.capture('signup_started', { source: source || 'direct' })
  },
  
  signupCompleted: (userId: string, email: string) => {
    posthog.identify(userId, { 
      email, 
      plan: 'free', 
      signup_date: new Date().toISOString() 
    })
    posthog.capture('signup_completed')
  },
  
  loginCompleted: (userId: string, email: string) => {
    posthog.identify(userId, { email })
    posthog.capture('login_completed')
  },
  
  logout: () => {
    posthog.capture('logout')
    posthog.reset()
  },
  
  // ============================================
  // Product Events
  // ============================================
  
  companySearched: (query: string, resultsCount: number) => {
    posthog.capture('company_searched', { 
      query, 
      results_count: resultsCount 
    })
  },
  
  companyViewed: (ticker: string, name: string) => {
    posthog.capture('company_viewed', { ticker, name })
  },
  
  filingViewed: (filingId: number, ticker: string, filingType: string) => {
    posthog.capture('filing_viewed', { 
      filing_id: filingId, 
      ticker, 
      filing_type: filingType 
    })
  },
  
  summaryGenerated: (ticker: string, filingType: string, filingId: number) => {
    posthog.capture('summary_generated', { 
      ticker, 
      filing_type: filingType, 
      filing_id: filingId 
    })
  },
  
  summarySaved: (filingId: number, ticker: string) => {
    posthog.capture('summary_saved', { filing_id: filingId, ticker })
  },
  
  watchlistAdded: (ticker: string) => {
    posthog.capture('watchlist_added', { ticker })
  },
  
  watchlistRemoved: (ticker: string) => {
    posthog.capture('watchlist_removed', { ticker })
  },
  
  // ============================================
  // Conversion Events
  // ============================================
  
  pricingViewed: (billingCycle: 'monthly' | 'yearly') => {
    posthog.capture('pricing_viewed', { billing_cycle: billingCycle })
  },
  
  billingCycleToggled: (from: string, to: string) => {
    posthog.capture('billing_cycle_toggled', { from, to })
  },
  
  checkoutStarted: (plan: string, price: number, billingCycle: string) => {
    posthog.capture('checkout_started', { 
      plan, 
      price, 
      billing_cycle: billingCycle 
    })
  },
  
  // Note: subscription_activated should be tracked server-side
  // via Stripe webhook for accuracy
  
  // ============================================
  // Error Events
  // ============================================
  
  errorOccurred: (error: string, context?: Record<string, unknown>) => {
    posthog.capture('error_occurred', { 
      error, 
      ...context 
    })
  },
}

export default analytics
```

**Status:** [ ] Not started

---

## Phase 7: PostHog Dashboard Setup

### Funnels to Create

#### 1. User Acquisition Funnel
```
$pageview (/) → signup_started → signup_completed
```

#### 2. Free to Paid Conversion Funnel
```
signup_completed → summary_generated → pricing_viewed → checkout_started → subscription_activated
```

#### 3. Feature Adoption Funnel
```
signup_completed → company_searched → filing_viewed → summary_generated
```

### Dashboards to Create

#### Growth Dashboard
- Daily/Weekly/Monthly Active Users
- New signups over time
- Signup conversion rate
- User retention (cohort analysis)

#### Product Dashboard
- Summary generations per day
- Most searched companies
- Feature usage breakdown
- Error rates

#### Revenue Dashboard
- Pricing page views
- Checkout start rate
- Conversion rate by billing cycle
- Revenue by cohort (if tracking in PostHog)

### Session Recording Playlists

1. **Conversion Dropoffs** — Users who viewed pricing but didn't start checkout
2. **Free Limit Hits** — Users who hit the 5 summary limit
3. **Error Sessions** — Sessions containing `error_occurred` events
4. **New User Journeys** — First sessions from new signups

**Status:** [ ] Not started

---

## Implementation Checklist

### Priority 1: Foundation (Do First)
- [ ] Update `posthog-provider.tsx` with enhanced config
- [ ] Create `lib/analytics.ts` utility module
- [ ] Add user identification on login/register

### Priority 2: Core Funnel Events
- [ ] Instrument `signup_started` and `signup_completed`
- [ ] Instrument `login_completed`
- [ ] Instrument `pricing_viewed` and `checkout_started`
- [ ] Set up PostHog funnels in dashboard

### Priority 3: Product Events
- [ ] Instrument `summary_generated`
- [ ] Instrument `company_searched`
- [ ] Instrument `watchlist_added/removed`
- [ ] Instrument `filing_viewed`

### Priority 4: A/B Testing
- [ ] Create `pricing-experiment` feature flag in PostHog
- [ ] Implement feature flag in pricing page
- [ ] Track experiment exposure

### Priority 5: Backend Integration
- [ ] Add server-side PostHog for `subscription_activated` (Stripe webhook)
- [ ] Consider server-side tracking for sensitive events

---

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/app/posthog-provider.tsx` | Enhanced configuration |
| `frontend/lib/analytics.ts` | New file - centralized analytics |
| `frontend/app/register/page.tsx` | Signup tracking + identification |
| `frontend/app/login/page.tsx` | Login tracking + identification |
| `frontend/app/pricing/page.tsx` | Pricing events + feature flags |
| `frontend/app/filing/[id]/page-client.tsx` | Summary generation tracking |
| `frontend/components/CompanySearch.tsx` | Search tracking |
| `frontend/app/dashboard/page.tsx` | User identification on load, logout tracking |
| `frontend/app/company/[ticker]/page.tsx` | Company view tracking |

---

## Environment Variables

Ensure these are set in production:

```env
NEXT_PUBLIC_POSTHOG_KEY=phc_xxxxxxxxxxxxxxxxxxxx
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```

---

## Testing Checklist

Before going live, verify:

- [ ] Events appear in PostHog Live Events view
- [ ] User identification links sessions correctly
- [ ] Session recordings capture user interactions
- [ ] Feature flags load and variants are assigned
- [ ] Funnels show correct step progression
- [ ] No PII is captured unintentionally in recordings

---

## Resources

- [PostHog Next.js Integration](https://posthog.com/docs/libraries/next-js)
- [PostHog Session Recording](https://posthog.com/docs/session-replay)
- [PostHog Feature Flags](https://posthog.com/docs/feature-flags)
- [PostHog Funnels](https://posthog.com/docs/product-analytics/funnels)
- [PostHog React Hooks](https://posthog.com/docs/libraries/react)

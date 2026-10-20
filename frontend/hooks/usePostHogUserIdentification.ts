'use client'

import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCookiePreferences } from '@/components/CookieConsent'
import { analytics } from '@/lib/analytics'
import { queryKeys } from '@/lib/queryKeys'
import { usePostHogReady } from '@/lib/posthogReady'

/**
 * App-wide PostHog identification (roadmap 2.4). Once the signed-in user and their subscription
 * resolve — and only if analytics consent is granted — set `is_pro` + `plan` as PostHog person
 * properties so every event (and the distinct-filings insight) can split Free vs Pro. If the
 * subscription read fails, the user is still identified, by id alone.
 *
 * Previously only the dashboard set a plan trait and `loginCompleted()` identified with no traits,
 * so a user landing anywhere else carried no `is_pro`. This runs once, app-wide.
 *
 * Reuses the existing `queryKeys.currentUser()` / `queryKeys.subscription.byUser(user?.id)` React Query caches (no extra requests)
 * and `analytics.identify` (which also mirrors the id into Sentry). Idempotent: a ref guards against
 * re-identifying on every render — it only fires when the user id or pro status changes.
 *
 * It also waits for PostHog to be ready (lib/posthogReady.ts) and runs again when it is, so a reader whose account
 * resolved while analytics was off is identified once a first allow from the footer's Cookie settings has loaded
 * the SDK, with no remount to run it.
 */
export function usePostHogUserIdentification(): void {
  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const { data: subscription, isError: subscriptionFailed } = useQuery({
    queryKey: queryKeys.subscription.byUser(user?.id),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!user, // subscription is account-scoped; don't fire a guaranteed-401 for guests
  })

  const posthogReady = usePostHogReady()
  const lastIdentity = useRef<string | null>(null)

  useEffect(() => {
    if (!user?.id || !posthogReady) return
    // Respect the analytics opt-in: PostHog is opted-out without it, and we shouldn't touch Sentry's
    // user either. (null preferences = no choice yet → wait for consent.)
    if (getCookiePreferences()?.analytics !== true) return

    // Entitlements SSoT: wait for the subscription row and use it directly, rather than the
    // denormalized `user.is_pro` mirror (which can be briefly out of sync). If the subscription
    // read fails (an API error, or the client's 30-second timeout), identify by the id alone and
    // tag no possibly-stale plan: the consent clause (lib/consentCopy.ts) tells a logged-in reader
    // their statistics are tied to their account id, and nothing here retries the read. A later
    // successful read changes the identity and adds the plan.
    if (subscription === undefined) {
      if (!subscriptionFailed) return // still loading: the first identify carries the plan
      const identity = `${user.id}:unknown`
      if (lastIdentity.current === identity) return
      lastIdentity.current = identity
      analytics.identify(String(user.id))
      return
    }
    const isPro = Boolean(subscription.is_pro)
    const identity = `${user.id}:${isPro}`
    if (lastIdentity.current === identity) return // already identified with this state
    lastIdentity.current = identity

    analytics.identify(String(user.id), { is_pro: isPro, plan: isPro ? 'pro' : 'free' })
  }, [user?.id, subscription, subscriptionFailed, posthogReady])
}

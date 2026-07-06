'use client'

import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCookiePreferences } from '@/components/CookieConsent'
import { analytics } from '@/lib/analytics'
import { queryKeys } from '@/lib/queryKeys'

/**
 * App-wide PostHog identification (roadmap 2.4). Once the signed-in user and their subscription
 * resolve — and only if analytics consent is granted — set `is_pro` + `plan` as PostHog person
 * properties so every event (and the distinct-filings insight) can split Free vs Pro.
 *
 * Previously only the dashboard set a plan trait and `loginCompleted()` identified with no traits,
 * so a user landing anywhere else carried no `is_pro`. This runs once, app-wide.
 *
 * Reuses the existing `queryKeys.currentUser()` / `queryKeys.subscription()` React Query caches (no extra requests)
 * and `analytics.identify` (which also mirrors the id into Sentry). Idempotent: a ref guards against
 * re-identifying on every render — it only fires when the user id or pro status changes.
 */
export function usePostHogUserIdentification(): void {
  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const { data: subscription } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!user, // subscription is account-scoped; don't fire a guaranteed-401 for guests
  })

  const lastIdentity = useRef<string | null>(null)

  useEffect(() => {
    if (!user?.id) return
    // Respect the analytics opt-in: PostHog is opted-out without it, and we shouldn't touch Sentry's
    // user either. (null preferences = no choice yet → wait for consent.)
    if (getCookiePreferences()?.analytics !== true) return

    // Entitlements SSoT: wait for the subscription row and use it directly, rather than the
    // denormalized `user.is_pro` mirror (which can be briefly out of sync). If the subscription
    // query never resolves (rare error), we simply don't tag a possibly-stale plan.
    if (subscription === undefined) return
    const isPro = Boolean(subscription.is_pro)
    const identity = `${user.id}:${isPro}`
    if (lastIdentity.current === identity) return // already identified with this state
    lastIdentity.current = identity

    analytics.identify(String(user.id), { is_pro: isPro, plan: isPro ? 'pro' : 'free' })
  }, [user?.id, subscription])
}

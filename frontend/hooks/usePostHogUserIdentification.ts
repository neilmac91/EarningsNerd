'use client'

import { useEffect, useRef } from 'react'
import { hashKey, useQuery, useQueryClient } from '@tanstack/react-query'

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCookiePreferences } from '@/components/CookieConsent'
import { analytics } from '@/lib/analytics'
import { reportAccountRead } from '@/lib/posthogIdentity'
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
  const { data: user, status: userStatus } = useQuery({
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
  const guest = user === null
  const queryClient = useQueryClient()
  const accountId = user ? String(user.id) : null

  useEffect(() => {
    // PostHog's start waits on this read for a browser with a session (lib/posthogIdentity.ts). A read that failed
    // confirms no account, so an identity PostHog kept is reset rather than trusted.
    if (userStatus === 'success') reportAccountRead(accountId)
    else if (userStatus === 'error') reportAccountRead(null)
  }, [userStatus, accountId])

  useEffect(() => {
    // An account deletion and "Log out of all devices" clear the whole cache instead of writing a guest, and React
    // Query tells no observer of a removed query, so this hook would never see the account go. Catch the removal: the
    // read reported before no longer holds, so PostHog's next start must not trust it (lib/posthogIdentity.ts), and
    // the same account read again, by any observer, is identified again.
    const identity = hashKey(queryKeys.currentUser())
    return queryClient.getQueryCache().subscribe((event) => {
      if (event.type !== 'removed' || event.query.queryHash !== identity) return
      reportAccountRead(null)
      lastIdentity.current = null
      analytics.forgetAccount()
    })
  }, [queryClient])

  useEffect(() => {
    if (!user?.id) {
      // No account: forget the one identified before, in PostHog and Sentry too. Only the dashboard's Log out resets
      // PostHog itself; the menus' Log out and a lost session reach here as a guest (the cache clears above reach the
      // subscription), and so does a browser PostHog kept identified from an earlier visit once it loads. A login then
      // identifies the account again once analytics is allowed; lib/analytics.ts never identifies while it is refused.
      lastIdentity.current = null
      if (guest) analytics.forgetAccount()
      return
    }
    if (!posthogReady) return
    // Respect the analytics opt-in: PostHog is opted-out without it, and we shouldn't touch Sentry's
    // user either. (null preferences = no choice yet → wait for consent.)
    if (getCookiePreferences()?.analytics !== true) return

    // Entitlements SSoT: wait for the subscription row and use it directly, rather than the
    // denormalized `user.is_pro` mirror (which can be briefly out of sync). If the subscription
    // read fails (an API error, or the client's 30-second timeout), identify by the id alone and
    // tag no plan, not even one an earlier read left cached (a failed refetch keeps its data): the
    // consent clause (lib/consentCopy.ts) tells a logged-in reader their statistics are tied to
    // their account id, and nothing here retries the read. A later successful read changes the
    // identity and adds the plan.
    if (subscriptionFailed) {
      const identity = `${user.id}:unknown`
      if (lastIdentity.current === identity) return
      lastIdentity.current = identity
      analytics.identify(String(user.id))
      return
    }
    if (subscription === undefined) return // still loading: the first identify carries the plan
    const isPro = Boolean(subscription.is_pro)
    const identity = `${user.id}:${isPro}`
    if (lastIdentity.current === identity) return // already identified with this state
    lastIdentity.current = identity

    analytics.identify(String(user.id), { is_pro: isPro, plan: isPro ? 'pro' : 'free' })
  }, [user?.id, guest, subscription, subscriptionFailed, posthogReady])
}

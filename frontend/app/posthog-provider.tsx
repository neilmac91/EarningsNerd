'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, Suspense, useState } from 'react'
import { subscribeCookiePreferences } from '@/lib/browserConsent'
import { applyPostHogConsent, browserAnalyticsAllowed, failPostHogClosed, postHogGuardFailed } from '@/lib/posthogConsent'
import { sanitizeTelemetryUrl } from '@/lib/telemetryPrivacy'
import { initializePostHogPrivacy, postHogPrivacyConfig } from '@/lib/posthogPrivacy'
import { PostHogReadyContext } from '@/lib/posthogReady'

function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname && posthog?.__loaded && browserAnalyticsAllowed()) {
      try {
        let url = window.origin + pathname
        if (searchParams && searchParams.toString()) {
          url = url + `?${searchParams.toString()}`
        }
        posthog.capture('$pageview', {
          '$current_url': sanitizeTelemetryUrl(url),
        })
      } catch (error) {
        console.error('PostHog: Failed to capture pageview', error)
      }
    }
  }, [pathname, searchParams])

  return null
}

function PostHogPageViewWrapper() {
  return (
    <Suspense fallback={null}>
      <PostHogPageView />
    </Suspense>
  )
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  // Seeded from the SDK, for a provider that mounts again after PostHog has loaded (GlobalErrorBoundary's "Try
  // again", a global-error reset): a second init is a no-op that never calls `loaded`, so nothing else would set it.
  // A client whose consent guard failed stays not ready. The server render and the first hydration still start at
  // false, since posthog.init runs only in the effect below.
  const [initialized, setInitialized] = useState(() => Boolean(posthog?.__loaded) && !postHogGuardFailed(posthog))
  // The visitor's analytics choice as this provider last applied it; with `initialized` it makes PostHogReadyContext.
  const [analyticsAllowed, setAnalyticsAllowed] = useState(false)

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com'
    let active = true
    let starting = false
    const followChoice = () => {
      const allowed = browserAnalyticsAllowed()
      setAnalyticsAllowed(allowed)
      if (!key) return // Identification can still mirror the account id into Sentry after consent.
      // Every failure below keeps PostHog off and reaches Sentry (failPostHogClosed), never only the console.
      try {
        if (posthog.__loaded) {
          if (!applyPostHogConsent(posthog)) setInitialized(false)
          return
        }
        if (!allowed || starting) return
        // Start PostHog only under its consent guard, installed here before init: unguarded, a withdrawal could
        // not stop queued or retried requests.
        if (!applyPostHogConsent(posthog)) return
        starting = true
        posthog.init(key, {
          api_host: host,
          capture_pageview: false,
          capture_pageleave: true,
          autocapture: true,
          opt_out_capturing_by_default: true,
          ...postHogPrivacyConfig(posthog),
          bootstrap: { featureFlags: {} },
          loaded: () => {
            // posthog-js swallows a throw from `loaded` and carries on, so none may leave it. Initialization may
            // finish after a refusal/clear in this or another tab. Never use the choice captured by the init
            // closure to opt back in or start recording.
            try {
              initializePostHogPrivacy(posthog)
              const guarded = applyPostHogConsent(posthog)
              if (!active) return
              if (guarded) setInitialized(true)
              setAnalyticsAllowed(browserAnalyticsAllowed())
            } catch (error) {
              // Every throw here comes before setInitialized(true), so the page never reads ready.
              failPostHogClosed(posthog, error)
            }
          },
        })
      } catch (error) {
        failPostHogClosed(posthog, error)
        setInitialized(false)
      }
    }
    // Subscribe before init: synchronous loaded callbacks and concurrent choices follow one store.
    const unsubscribe = subscribeCookiePreferences(followChoice)
    followChoice()
    return () => { active = false; unsubscribe() }
  }, [])

  // One tree before and after the SDK loads. The provider stays mounted around the page and only the page-view
  // tracker joins once PostHog has loaded, so a first allow from the footer's Cookie settings never remounts the
  // route: a draft and the opener's focus survive it. Before consent the provider only hands its hooks the global
  // client, as their default context does, and consent still gates posthog.init above.
  // Account identification waits on this (lib/posthogReady.ts): the visitor allows analytics and the SDK has loaded,
  // or there is no key and nothing to load.
  const ready = analyticsAllowed && (initialized || !process.env.NEXT_PUBLIC_POSTHOG_KEY)
  return (
    <PostHogReadyContext.Provider value={ready}>
      <PHProvider client={posthog}>
        {initialized && posthog?.__loaded ? <PostHogPageViewWrapper /> : null}
        {children}
      </PHProvider>
    </PostHogReadyContext.Provider>
  )
}

'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, Suspense, useState } from 'react'
import { getCookiePreferences, type CookiePreferences } from '@/components/CookieConsent'

function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname && posthog && posthog?.__loaded) {
      try {
        let url = window.origin + pathname
        if (searchParams && searchParams.toString()) {
          url = url + `?${searchParams.toString()}`
        }
        posthog.capture('$pageview', {
          '$current_url': url,
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
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com'

    // Early return if PostHog key is not configured
    if (!key) {
      console.warn('PostHog: NEXT_PUBLIC_POSTHOG_KEY not set, analytics disabled')
      return
    }

    // Check cookie consent before initializing PostHog
    const initializePostHog = (preferences?: CookiePreferences | null) => {
      try {
        const consent = preferences || getCookiePreferences()

        // Only initialize if user has consented to analytics
        // OR if no preferences set yet (will be handled by cookie banner)
        if (consent && !consent.analytics) {
          // User explicitly rejected analytics
          if (posthog?.__loaded) {
            // If already loaded, opt out
            posthog.opt_out_capturing()
          }
          return
        }

        // Don't initialize until user has made a choice
        // Exception: if no consent recorded, we'll wait for the banner
        if (!consent && typeof window !== 'undefined') {
          // Wait for cookie consent to be set
          return
        }

        // Initialize PostHog with consent-aware settings
        if (!initialized && !posthog?.__loaded) {
          posthog.init(key, {
            api_host: host,
            capture_pageview: false, // We handle it manually
            capture_pageleave: consent?.analytics || false,
            autocapture: consent?.analytics || false,
            session_recording: {
              maskAllInputs: true, // Mask all inputs by default for privacy
              maskInputOptions: { password: true },
              maskTextSelector: '[data-ph-mask]',
              recordCrossOriginIframes: false,
              // Only enable session recording if explicitly consented
              // Note: This is controlled by startSessionRecording() call below
            },
            disable_session_recording: !consent?.sessionRecording, // Disable if not consented
            bootstrap: { featureFlags: {} },
            loaded: (posthogClient) => {
              if (process.env.NODE_ENV === 'development') {
                posthogClient.debug()
              }

              // Start session recording only if user explicitly consented
              if (consent?.sessionRecording) {
                posthogClient.startSessionRecording()
              } else {
                posthogClient.stopSessionRecording()
              }

              // Opt in if analytics consented
              if (consent?.analytics) {
                posthogClient.opt_in_capturing()
              }
            },
          })

          setInitialized(true)
        } else if (posthog?.__loaded) {
          // Update existing PostHog instance based on consent
          if (consent?.analytics) {
            posthog.opt_in_capturing()

            // Update session recording based on consent
            if (consent.sessionRecording) {
              posthog.startSessionRecording()
            } else {
              posthog.stopSessionRecording()
            }
          } else {
            posthog.opt_out_capturing()
            posthog.stopSessionRecording()
          }
        }
      } catch (error) {
        console.error('PostHog: Failed to initialize or update PostHog', error)
      }
    }

    // Initialize on mount
    initializePostHog()

    // Listen for consent changes
    const handleConsentChange = (event: Event) => {
      const customEvent = event as CustomEvent<CookiePreferences>
      initializePostHog(customEvent.detail)
    }

    window.addEventListener('cookieConsentChanged', handleConsentChange)

    return () => {
      window.removeEventListener('cookieConsentChanged', handleConsentChange)
    }
  }, [initialized])

  return (
    <PHProvider client={posthog}>
      <PostHogPageViewWrapper />
      {children}
    </PHProvider>
  )
}

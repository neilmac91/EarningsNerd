'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, Suspense } from 'react'

function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname && posthog) {
      let url = window.origin + pathname
      if (searchParams && searchParams.toString()) {
        url = url + `?${searchParams.toString()}`
      }
      posthog.capture('$pageview', {
        '$current_url': url,
      })
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
  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com'

    if (key) {
      posthog.init(key, {
        api_host: host,
        capture_pageview: false, // We handle it manually
        capture_pageleave: true, // Optional, but good to have
        autocapture: true,
        session_recording: {
          maskAllInputs: false,
          maskInputOptions: { password: true },
          maskTextSelector: '[data-ph-mask]',
          recordCrossOriginIframes: false,
        },
        bootstrap: { featureFlags: {} },
        loaded: (posthogClient) => {
          if (process.env.NODE_ENV === 'development') {
            posthogClient.debug()
          }
        },
      })
    }
  }, [])

  return (
    <PHProvider client={posthog}>
      <PostHogPageViewWrapper />
      {children}
    </PHProvider>
  )
}

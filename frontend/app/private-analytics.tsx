'use client'

import { useSyncExternalStore } from 'react'
import { Analytics } from '@vercel/analytics/next'
import type { BeforeSendEvent } from '@vercel/analytics'
import { getCookiePreferences } from '@/components/CookieConsent'
import { isCredentialLocation, sanitizeTelemetry } from '@/lib/telemetryPrivacy'

/** The visitor's stored analytics choice: the consent bar's `cookie_consent`, the state PostHog obeys. */
const analyticsAllowed = () => getCookiePreferences()?.analytics === true

export function beforeSendVercel(event: BeforeSendEvent): BeforeSendEvent | null {
  // A choice withdrawn after the script loaded: the library cannot unload it (below), so nothing it sends leaves.
  if (!analyticsAllowed()) return null
  // Vercel adds document.referrer after its hook, so a sensitive referrer must drop the event.
  if (document.referrer && (isCredentialLocation(document.referrer) || document.referrer.includes('?') || document.referrer.includes('#'))) return null
  return sanitizeTelemetry(event)
}

function onConsentChange(update: () => void) {
  window.addEventListener('cookieConsentChanged', update)
  return () => window.removeEventListener('cookieConsentChanged', update)
}

/**
 * Vercel Web Analytics loads only once the visitor allows analytics (D-046), as the consent bar says: the choice is
 * read from the stored preferences after hydration (the server render and the hydration render use `false`) and
 * again on each `cookieConsentChanged` the bar fires, as PostHog reads it. Until then, and while analytics are not
 * allowed, nothing renders, so no script is requested.
 *
 * A withdrawal mid-page: @vercel/analytics 2.0.1 has no unload. Its <Analytics> appends one script tag on mount and
 * removes nothing on unmount, so the script stays in the page until the next full load. Unmounting stops the
 * pageviews the component sends on navigation, and beforeSendVercel, which stays registered with the script,
 * drops every event while the stored choice is not analytics. From the next page load, nothing loads.
 */
export function PrivateAnalytics() {
  const allowed = useSyncExternalStore(onConsentChange, analyticsAllowed, () => false)
  return allowed ? <Analytics beforeSend={beforeSendVercel} /> : null
}

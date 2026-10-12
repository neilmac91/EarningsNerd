'use client'

import { Analytics } from '@vercel/analytics/next'
import type { BeforeSendEvent } from '@vercel/analytics'
import { isCredentialLocation, sanitizeTelemetry } from '@/lib/telemetryPrivacy'

export function beforeSendVercel(event: BeforeSendEvent): BeforeSendEvent | null {
  // Vercel adds document.referrer after its hook, so a sensitive referrer must drop the event.
  if (document.referrer && (isCredentialLocation(document.referrer) || document.referrer.includes('?') || document.referrer.includes('#'))) return null
  return sanitizeTelemetry(event)
}

export function PrivateAnalytics() {
  return <Analytics beforeSend={beforeSendVercel} />
}

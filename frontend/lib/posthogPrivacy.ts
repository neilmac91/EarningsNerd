import type { CaptureResult, PostHog, PostHogConfig } from 'posthog-js'
import { canRecordTelemetry, sanitizeTelemetry, sanitizeTelemetryText, sanitizeTelemetryUrl } from './telemetryPrivacy'

/** Clean old SDK attribution/flag stores as well as current event properties. */
export function sanitizePostHogPersistence(client: PostHog): void {
  for (const persistence of [client.persistence, client.sessionPersistence]) {
    if (persistence) persistence.register(sanitizeTelemetry(persistence.props))
  }
}

export function initializePostHogPrivacy(client: PostHog): void {
  sanitizePostHogPersistence(client)
  // SDK flags requests bypass before_send and read this compact attribution object directly.
  // Seed the same SDK shape with sanitized URLs; retain existing (now sanitized) attribution.
  client.persistence?.register_once({
    $initial_person_info: {
      u: sanitizeTelemetryUrl(window.location.href),
      r: sanitizeTelemetryUrl(document.referrer),
    },
  }, undefined)
  client.sessionPersistence?.register_once({
    $referrer: sanitizeTelemetryUrl(document.referrer) || '$direct',
    $referring_domain: document.referrer ? new URL(document.referrer).hostname : '$direct',
  }, undefined)
}

export function beforeSendPostHog(client: PostHog, event: CaptureResult | null): CaptureResult | null {
  if (!event) return null
  const mayRecord = canRecordTelemetry()
  sanitizePostHogPersistence(client)
  if (event.event === '$snapshot') {
    if (!mayRecord) return null
    // The recorder masks data before compression. Binary gzip strings can accidentally match
    // URL patterns, so sanitize only envelope metadata and preserve the opaque replay payload.
    const { $snapshot_data, ...properties } = event.properties
    const clean = sanitizeTelemetry({ ...event, properties }, true)
    return { ...clean, properties: { ...clean.properties, $snapshot_data } }
  }
  return sanitizeTelemetry(event, true)
}

export const POSTHOG_RECORDING_PRIVACY = {
  maskAllInputs: true,
  maskInputOptions: { password: true },
  maskTextSelector: '[data-ph-mask]',
  blockSelector: 'input[type="hidden"], input[type="file"]',
  recordCrossOriginIframes: false,
  recordHeaders: false,
  recordBody: false,
  maskAttributeFn: (name, value, element) => {
    if (/(?:token|password|secret|authorization)/i.test(name)) return '[REDACTED]'
    // rrweb's maskAllInputs does not mask hidden fields; these can contain auth tokens.
    if (name === 'value' && element instanceof HTMLInputElement && ['hidden', 'file'].includes(element.type)) return '[REDACTED]'
    return sanitizeTelemetryText(value)
  },
  maskCapturedNetworkRequestFn: (request) => canRecordTelemetry() ? sanitizeTelemetry(request) : null,
} satisfies NonNullable<PostHogConfig['session_recording']>

export function postHogPrivacyConfig(client: PostHog): Partial<PostHogConfig> {
  return {
    save_referrer: false,
    save_campaign_params: false,
    enable_recording_console_log: false,
    before_send: (event) => beforeSendPostHog(client, event),
    session_recording: POSTHOG_RECORDING_PRIVACY,
  }
}

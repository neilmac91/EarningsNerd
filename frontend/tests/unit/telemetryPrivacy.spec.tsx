import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, act } from '@testing-library/react'
import type { PostHog, PostHogConfig, QueuedRequestWithOptions } from 'posthog-js'
import { gzipSync, gunzipSync } from 'node:zlib'

const consent = vi.hoisted(() => ({ current: { analytics: true, sessionRecording: true } as { analytics: boolean; sessionRecording: boolean } | null }))
const mockPostHog = vi.hoisted(() => ({
  __loaded: false,
  init: vi.fn(), capture: vi.fn(), opt_in_capturing: vi.fn(), opt_out_capturing: vi.fn(),
  startSessionRecording: vi.fn(), stopSessionRecording: vi.fn(), debug: vi.fn(),
}))
vi.mock('posthog-js', async (original) => ({ ...await original<object>(), default: mockPostHog }))
vi.mock('posthog-js/react', () => ({ PostHogProvider: ({ children }: { children: React.ReactNode }) => children }))
vi.mock('@/components/CookieConsent', () => ({ getCookiePreferences: () => consent.current }))
vi.mock('next/navigation', () => ({ usePathname: () => window.location.pathname, useSearchParams: () => new URLSearchParams(window.location.search) }))
vi.mock('@vercel/analytics/next', () => ({ Analytics: () => null }))

const TOKEN = 'synthetic-auth-value-never-a-real-token'
const JWT = ['eyJhbGciOiJub25lIn0', 'eyJzdWIiOiJmaXh0dXJlIn0', 'c3ludGhldGlj'].join('.')
const tokenUrl = `https://example.test/reset-password?token=${TOKEN}`
const AUTH_ROUTES = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email', '/check-email?email=synthetic%40example.test']
let removeNavigationGuard: (() => void) | undefined
let client: PostHog | undefined

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/pricing')
  localStorage.clear()
  sessionStorage.clear()
  Object.defineProperty(document, 'referrer', { configurable: true, value: '' })
  consent.current = { analytics: true, sessionRecording: true }
  mockPostHog.__loaded = false
  vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_synthetic_project')
})

afterEach(async () => {
  cleanup()
  removeNavigationGuard?.()
  removeNavigationGuard = undefined
  await client?.shutdown()
  client = undefined
  vi.useRealTimers()
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('authentication credentials never enter telemetry', () => {
  it('strips every URL query/fragment recursively, preserving only the SDK ingestion token', async () => {
    const { sanitizeTelemetry } = await import('@/lib/telemetryPrivacy')
    const event = {
      event: '$identify', properties: { token: 'phc_public_ingestion', symbol: 'AAPL',
        $set: { url: tokenUrl, token: TOKEN },
        nested: [{ $initial_referrer: encodeURIComponent(tokenUrl), message: `Failed GET /verify-email?new_credential=${TOKEN}`, log: `Authorization: Bearer ${TOKEN}`, diagnostic: `Rejected JWT ${JWT}` }],
      },
      $set_once: { $initial_current_url: `https://example.test/path?unrecognized=${TOKEN}#${TOKEN}` },
      $set: { $referrer: tokenUrl, access_token: TOKEN },
    }
    const clean = sanitizeTelemetry(event, true)
    expect(JSON.stringify(clean)).not.toContain(TOKEN)
    expect(JSON.stringify(clean)).not.toContain(JWT)
    expect(clean.properties.token).toBe('phc_public_ingestion')
    expect(clean.properties.symbol).toBe('AAPL')
    expect(clean.$set_once.$initial_current_url).toBe('https://example.test/path')
    expect(clean.properties.nested[0].$initial_referrer).toBe(encodeURIComponent('https://example.test/reset-password'))
    expect(event.properties.$set.token).toBe(TOKEN) // Do not mutate application inputs.
  })

  it('sanitizes real PostHog capture payloads and flags requests, including old persisted person URLs', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })))
    const { PostHog: RealPostHog } = await import('posthog-js')
    const privacy = await import('@/lib/posthogPrivacy')
    client = new RealPostHog()
    const requests: QueuedRequestWithOptions[] = []
    const events: unknown[] = []
    const intercept = (request: QueuedRequestWithOptions) => {
      requests.push(structuredClone({ ...request, callback: undefined }))
      request.callback?.({ statusCode: 200, json: { featureFlags: {}, featureFlagPayloads: {} } })
    }
    // The public capture listener sees fully enriched payloads. Flags bypass that path and
    // are inspected separately at their actual SDK request dispatcher. No provider is called.
    vi.spyOn(client, '_send_request').mockImplementation(intercept)
    client.on('eventCaptured', (event) => events.push(event))
    client.init('phc_synthetic_project', {
      ...privacy.postHogPrivacyConfig(client),
      api_host: 'https://example.invalid',
      autocapture: false, capture_pageview: false, capture_pageleave: false,
      disable_session_recording: true, disable_external_dependency_loading: true,
      request_batching: false, advanced_disable_feature_flags_on_first_load: true,
      api_transport: 'fetch',
      persistence: 'memory',
      loaded: () => {
        client!.register({
          $initial_person_info: { r: tokenUrl, u: tokenUrl },
          $initial_referrer_info: { $referrer: tokenUrl },
          $stored_person_properties: { old_url: tokenUrl },
          $client_session_props: { props: { r: tokenUrl, u: tokenUrl } },
        })
        privacy.initializePostHogPrivacy(client!)
      },
    })
    expect(client.__loaded).toBe(true)
    const captured = client.capture('$pageview', { $current_url: tokenUrl, $set: { landing: tokenUrl }, nested: { $set: { $referrer: tokenUrl } } }, { $set_once: { $initial_current_url: tokenUrl } })
    expect(captured).toBeDefined()
    client.capture('$autocapture', { $referrer: tokenUrl, symbol: 'AAPL' })
    client.capture('$web_vitals', { $current_url: tokenUrl })
    client.opt_in_capturing()
    client.reloadFeatureFlags()
    await vi.advanceTimersByTimeAsync(1000)
    const flags = requests.filter((request) => request.url.includes('/flags/'))
    expect(events.length).toBeGreaterThanOrEqual(4)
    expect(flags.length).toBeGreaterThan(0)
    expect(JSON.stringify(requests)).not.toContain(TOKEN)
    expect(JSON.stringify(events)).not.toContain(TOKEN)
    expect(JSON.stringify(client.persistence?.props)).not.toContain(TOKEN)
    expect(JSON.stringify(events)).toContain('phc_synthetic_project')
    expect(JSON.stringify(events)).toContain('AAPL')
  })

  it.each(AUTH_ROUTES)('blocks recording before entering %s and never releases compressed queued snapshots in the same document', async (route) => {
    const guard = await import('@/lib/telemetryPrivacy')
    const privacy = await import('@/lib/posthogPrivacy')
    const { PostHog: RealPostHog } = await import('posthog-js')
    const isolated = new RealPostHog()
    const stopped = vi.fn()
    guard.onRecordingBlocked(stopped)
    removeNavigationGuard = guard.installTelemetryNavigationGuard()
    expect(guard.canRecordTelemetry()).toBe(true)
    window.history.pushState(null, '', route)
    expect(stopped).toHaveBeenCalledOnce()
    window.history.replaceState(null, '', '/dashboard')
    expect(guard.canRecordTelemetry()).toBe(false)
    expect(privacy.beforeSendPostHog(isolated, { event: '$snapshot', properties: { $snapshot_data: 'opaque-compressed-snapshot', token: 'phc_synthetic_project' } })).toBeNull()
    const ordinary = privacy.beforeSendPostHog(isolated, { event: 'ordinary_event', properties: { token: 'phc_synthetic_project', symbol: 'AAPL' } })
    expect(ordinary?.properties.symbol).toBe('AAPL')
  })

  it('preserves valid compressed replay bytes on safe routes while sanitizing the envelope', async () => {
    const { PostHog: RealPostHog } = await import('posthog-js')
    const { beforeSendPostHog } = await import('@/lib/posthogPrivacy')
    // Alphanumeric DOM text contains no URLs. Its deterministic gzip bytes nevertheless
    // contain a slash/query-like sequence, which must never be treated as readable text.
    let seed = 2
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let text = ''
    for (let index = 0; index < 4096; index++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
      text += alphabet[(seed >>> 16) % alphabet.length]
    }
    const serialized = JSON.stringify({ node: { type: 3, textContent: text }, initialOffset: { top: 0, left: 0 } })
    const compressed = gzipSync(serialized, { level: 9 })
    expect(gunzipSync(compressed).toString()).toBe(serialized)
    const snapshotData = [{ type: 2, data: compressed.toString('latin1'), timestamp: 1 }]
    const event = {
      event: '$snapshot', properties: {
        $snapshot_data: snapshotData,
        $current_url: tokenUrl,
        token: 'phc_synthetic_project',
      },
    }
    const isolated = new RealPostHog()
    const clean = beforeSendPostHog(isolated, event)
    expect(clean).not.toBeNull()
    const outgoing = (clean!.properties.$snapshot_data as typeof snapshotData)[0].data
    expect(Buffer.from(outgoing, 'latin1').equals(compressed)).toBe(true)
    expect(gunzipSync(Buffer.from(outgoing, 'latin1')).toString()).toBe(serialized)
    expect(clean!.properties.$current_url).toBe('https://example.test/reset-password')
    expect(clean!.properties.token).toBe('phc_synthetic_project')
    const { protectTelemetryRoute } = await import('@/lib/telemetryPrivacy')
    protectTelemetryRoute('/reset-password')
    expect(beforeSendPostHog(isolated, event)).toBeNull()
  })

  it('covers auth entry before SDK initialization and popstate restore', async () => {
    const guard = await import('@/lib/telemetryPrivacy')
    const stopped = vi.fn()
    guard.onRecordingBlocked(stopped)
    removeNavigationGuard = guard.installTelemetryNavigationGuard()
    // Next announces the destination before window.location changes or SDK initialization.
    guard.protectTelemetryRoute(`/verify-email?token=${TOKEN}`)
    expect(stopped).toHaveBeenCalledOnce()
    expect(window.location.pathname).toBe('/pricing')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(guard.canRecordTelemetry()).toBe(false)
  })

  it('masks replay URLs, network data and hidden/file controls before snapshot compression', async () => {
    const { POSTHOG_RECORDING_PRIVACY: recording } = await import('@/lib/posthogPrivacy')
    const hidden = document.createElement('input')
    hidden.type = 'hidden'
    hidden.value = TOKEN
    const file = document.createElement('input')
    file.type = 'file'
    expect(hidden.matches(recording.blockSelector)).toBe(true)
    expect(file.matches(recording.blockSelector)).toBe(true)
    expect(recording.maskAttributeFn('value', TOKEN, hidden)).not.toContain(TOKEN)
    expect(recording.maskAttributeFn('href', tokenUrl, document.createElement('a'))).toBe('https://example.test/reset-password')
    const clean = recording.maskCapturedNetworkRequestFn({ name: tokenUrl })
    expect(clean?.name).toBe('https://example.test/reset-password')
    window.history.replaceState(null, '', `/reset-password?token=${TOKEN}`)
    expect(recording.maskCapturedNetworkRequestFn({ name: tokenUrl })).toBeNull()
  })

  it('honors analytics consent and recording consent at startup, updates and attempted resume after auth', async () => {
    const guard = await import('@/lib/telemetryPrivacy')
    const { PostHogProvider } = await import('@/app/posthog-provider')
    let config: Partial<PostHogConfig> | undefined
    mockPostHog.init.mockImplementation((_key, supplied: Partial<PostHogConfig>) => {
      config = supplied
      mockPostHog.__loaded = true
      supplied.loaded?.(mockPostHog as unknown as PostHog)
    })
    consent.current = null
    const view = render(<PostHogProvider><span>App remains available</span></PostHogProvider>)
    expect(mockPostHog.init).not.toHaveBeenCalled()
    consent.current = { analytics: true, sessionRecording: true }
    act(() => window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: consent.current })))
    expect(config?.before_send).toBeTypeOf('function')
    expect(config?.enable_recording_console_log).toBe(false)
    expect(mockPostHog.startSessionRecording).toHaveBeenCalled()
    guard.protectTelemetryRoute('/reset-password')
    mockPostHog.startSessionRecording.mockClear()
    act(() => window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: consent.current })))
    expect(mockPostHog.startSessionRecording).not.toHaveBeenCalled()
    expect(mockPostHog.stopSessionRecording).toHaveBeenCalled()
    consent.current = { analytics: false, sessionRecording: false }
    act(() => window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: consent.current })))
    expect(mockPostHog.opt_out_capturing).toHaveBeenCalled()
    view.unmount()
  })

  it.each(AUTH_ROUTES)('does not start recording on a consented %s initial load', async (route) => {
    window.history.replaceState(null, '', route)
    const { PostHogProvider } = await import('@/app/posthog-provider')
    mockPostHog.init.mockImplementation((_key, config: Partial<PostHogConfig>) => {
      expect(config.disable_session_recording).toBe(true)
      mockPostHog.__loaded = true
      config.loaded?.(mockPostHog as unknown as PostHog)
    })
    render(<PostHogProvider><span>Account flow remains available</span></PostHogProvider>)
    expect(mockPostHog.startSessionRecording).not.toHaveBeenCalled()
    expect(mockPostHog.stopSessionRecording).toHaveBeenCalled()
  })

  it('sanitizes Vercel event URLs and drops the event if its later-added referrer contains query or fragment data', async () => {
    const { beforeSendVercel } = await import('@/app/private-analytics')
    expect(beforeSendVercel({ type: 'pageview', url: tokenUrl })?.url).toBe('https://example.test/reset-password')
    Object.defineProperty(document, 'referrer', { configurable: true, value: tokenUrl })
    expect(beforeSendVercel({ type: 'pageview', url: 'https://example.test/pricing' })).toBeNull()
    Object.defineProperty(document, 'referrer', { configurable: true, value: 'https://search.test/' })
    expect(beforeSendVercel({ type: 'pageview', url: 'https://example.test/pricing' })).not.toBeNull()
  })

  it('sends a real Sentry error envelope with URL-bearing breadcrumbs and extras scrubbed', async () => {
    const Sentry = await import('@sentry/nextjs')
    const config = await import('@/lib/sentryConfig')
    const envelopes: unknown[] = []
    Sentry.init({
      dsn: 'https://public@example.invalid/1', defaultIntegrations: false, autoSessionTracking: false,
      dataCollection: config.SENTRY_DATA_COLLECTION,
      ...config.SENTRY_TELEMETRY_PRIVACY, ...config.SENTRY_REPLAY_SAMPLE_RATES,
      transport: () => ({ send: async (envelope) => { envelopes.push(envelope); return { statusCode: 200 } }, flush: async () => true }),
    })
    Sentry.addBreadcrumb({ category: 'navigation', data: { to: tokenUrl } })
    Sentry.captureException(new Error(`Failed at ${tokenUrl} Authorization: Bearer ${TOKEN}`), { extra: { nested: { initial_referrer: tokenUrl } } })
    expect(await Sentry.flush(2000)).toBe(true)
    expect(envelopes).toHaveLength(1)
    expect(JSON.stringify(envelopes)).not.toContain(TOKEN)
    expect(JSON.stringify(envelopes)).toContain('Failed at https://example.test/reset-password')
    expect(config.SENTRY_REPLAY_SAMPLE_RATES).toEqual({ replaysSessionSampleRate: 0, replaysOnErrorSampleRate: 0 })
    await Sentry.close(2000)
  })
})

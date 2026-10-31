import { test, expect, type Page, type Request } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { gunzipSync } from 'node:zlib'
import ts from 'typescript'
import type { PostHog } from 'posthog-js'
import type * as Privacy from '../../lib/telemetryPrivacy'
import type * as Consent from '../../lib/browserConsent'
import type * as ConsentGuard from '../../lib/posthogConsent'
import type * as PostHogPrivacy from '../../lib/posthogPrivacy'
import type { analytics } from '../../lib/analytics'

// A browser transport test, independent of Next/backend and production environment variables.
// Every request is fulfilled locally, including the SDK's config, flags, events and replay.
const SITE = 'https://telemetry-fixture.invalid'
const INGEST = 'https://telemetry-ingest.invalid'
const PROJECT_KEY = 'phc_synthetic_privacy_network_test'
const CANARIES = ['synthetic-reset-canary', 'synthetic-referrer-canary', 'synthetic-person-canary', 'synthetic-stored-canary']

interface HarnessWindow extends Window {
  posthog: PostHog
  privacy: typeof Privacy
  posthogPrivacy: typeof PostHogPrivacy
  consent: typeof Consent
  consentGuard: typeof ConsentGuard
  analytics: typeof analytics
  heldConsentEvents?: StorageEventInit[]
  releaseConsentEvents?: () => void
}

interface WireRequest { url: string; payload: unknown }

function decodeRequest(request: Request): unknown {
  const body = request.postDataBuffer()
  if (!body?.length) return null
  if (body[0] === 0x1f && body[1] === 0x8b) return JSON.parse(gunzipSync(body).toString())
  const text = body.toString()
  if (text.startsWith('data=')) {
    const data = new URLSearchParams(text).get('data')!
    return JSON.parse(Buffer.from(data, 'base64').toString())
  }
  return JSON.parse(text)
}

function helperScript(): string {
  const compile = (name: string) => ts.transpileModule(
    readFileSync(path.resolve(__dirname, `../../lib/${name}.ts`), 'utf8'),
    { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } },
  ).outputText
  return `(() => {
    const modules = {};
    const load = (name, execute) => { const exports = {}; execute(exports, id => modules[id]); modules[name] = exports; return exports; };
    window.consent = load('./browserConsent', function(exports, require) { ${compile('browserConsent')} });
    window.consentGuard = load('./posthogConsent', function(exports, require) { ${compile('posthogConsent')} });
    window.privacy = load('./telemetryPrivacy', function(exports, require) { ${compile('telemetryPrivacy')} });
    window.posthogPrivacy = load('./posthogPrivacy', function(exports, require) { ${compile('posthogPrivacy')} });
    modules['posthog-js'] = { __esModule: true, get default() { return window.posthog; } };
    modules['@sentry/nextjs'] = { setUser: () => {} };
    modules['@/components/CookieConsent'] = window.consent;
    window.analytics = load('./analytics', function(exports, require) { ${compile('analytics')} }).analytics;
  })();`
}

async function fixture(page: Page, initialPath: string, batching = false) {
  let failEvents = false
  let releaseHeld: (() => void) | undefined
  let holdEvent = false
  const wire: WireRequest[] = []
  const authRequests: string[] = []
  await page.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin === SITE && url.pathname === '/api/auth/reset-password') {
      authRequests.push(request.postData() || '')
      return route.fulfill({ contentType: 'application/json', body: '{"success":true}' })
    }
    if (url.origin === SITE && request.isNavigationRequest()) {
      return route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Telemetry fixture</title><main><h1>Safe page</h1><button>Interact</button></main>' })
    }
    // Do not continue any request: a new SDK endpoint must remain inside this fixture too.
    if (url.origin !== INGEST) return route.abort('blockedbyclient')
    wire.push({ url: request.url(), payload: decodeRequest(request) })
    if (url.pathname.startsWith('/e') && holdEvent) {
      await new Promise<void>(resolve => { releaseHeld = resolve })
      return route.fulfill({ status: 503, contentType: 'application/json', body: '{}' })
    }
    if (url.pathname.startsWith('/e') && failEvents) return route.fulfill({ status: 503, contentType: 'application/json', body: '{}' })
    const config = {
      sessionRecording: { endpoint: '/s/', sampleRate: 1, minimumDurationMilliseconds: 0 },
      supportedCompression: ['gzip', 'gzip-js', 'base64'],
      hasFeatureFlags: true,
      featureFlags: {}, featureFlagPayloads: {},
    }
    return route.fulfill({
      contentType: 'application/json', body: JSON.stringify(config),
      headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS' },
    })
  })
  await page.goto(`${SITE}${initialPath}`, { referer: `${SITE}/login?token=${CANARIES[1]}` })
  await page.evaluate(({ stored, person, site }) => {
    localStorage.setItem('ph_privacy-network', JSON.stringify({
      distinct_id: 'synthetic-distinct-id',
      $device_id: 'synthetic-device-id',
      $initial_person_info: { u: `${site}/reset-password?token=${stored}`, r: `${site}/login?token=${stored}` },
      $stored_person_properties: { landing: `${site}/reset-password?token=${person}`, token: person },
      $referrer: `${site}/login?token=${stored}`,
    }))
  }, { stored: CANARIES[3], person: CANARIES[2], site: SITE })
  await page.addScriptTag({ path: path.resolve(__dirname, '../../node_modules/posthog-js/dist/array.full.no-external.js') })
  await page.addScriptTag({ content: helperScript() })
  await page.evaluate(({ key, host, batching }) => {
    const w = window as unknown as HarnessWindow
    w.consent.saveCookiePreferences({ essential: true, analytics: true, sessionRecording: false, timestamp: '' })
    w.consentGuard.installPostHogConsentGuard(w.posthog)
    w.consent.subscribeCookiePreferences(() => w.consentGuard.applyPostHogConsent(w.posthog))
    w.privacy.installTelemetryNavigationGuard()
    const privacyConfig = w.posthogPrivacy.postHogPrivacyConfig(w.posthog)
    w.posthog.init(key, {
      ...privacyConfig,
      api_host: host,
      persistence: 'localStorage', persistence_name: 'privacy-network',
      capture_pageview: false, capture_pageleave: false, autocapture: false,
      opt_out_capturing_by_default: true,
      // Otherwise the real SDK intentionally drops Chromium automation as bot traffic.
      opt_out_useragent_filter: true,
      request_batching: batching,
      loaded: client => {
        w.posthogPrivacy.initializePostHogPrivacy(client)
        w.consentGuard.applyPostHogConsent(w.posthog)
      },
    })
    w.posthog.capture('$pageview', { $current_url: window.location.href })
    // Application identity traits are sanitized before entering the SDK; inherited raw
    // persistence above separately exercises the migration of previously stored values.
    w.posthog.setPersonPropertiesForFlags(w.privacy.sanitizeTelemetry({ landing: window.location.href }))
    w.posthog.reloadFeatureFlags()
  }, { key: PROJECT_KEY, host: INGEST, batching })
  return {
    wire, authRequests,
    fail: (value: boolean) => { failEvents = value },
    hold: () => { holdEvent = true },
    release: () => { holdEvent = false; releaseHeld?.() },
  }
}

function events(wire: WireRequest[]): Array<Record<string, unknown>> {
  return wire.filter(request => /\/(?:e|s)\/?$/.test(new URL(request.url).pathname))
    .flatMap(request => {
      const payload = request.payload as { batch?: unknown[] } | null
      return Array.isArray(payload) ? payload : Array.isArray(payload?.batch) ? payload.batch : [payload]
    })
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
}

test('real PostHog transport sanitizes authentication URLs and keeps replay off despite remote recording configuration', async ({ page }) => {
  const { wire, authRequests } = await fixture(page, `/reset-password?token=${CANARIES[0]}#access_token=${CANARIES[0]}`)
  await expect.poll(() => wire.some(request => new URL(request.url).pathname.startsWith('/flags'))).toBe(true)
  await expect.poll(() => events(wire).map(event => event.event)).toContain('$pageview')
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(false)
  for (const canary of CANARIES) expect(JSON.stringify(wire)).not.toContain(canary)
  const persistence = await page.evaluate(() => {
    const client = (window as unknown as HarnessWindow).posthog
    return JSON.stringify([client.persistence?.props, client.sessionPersistence?.props])
  })
  for (const canary of CANARIES) expect(persistence).not.toContain(canary)
  await page.evaluate(async token => {
    const w = window as unknown as HarnessWindow
    await fetch('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ token }) })
    history.replaceState({}, '', '/pricing')
    // Even stale snapshots presented directly at the real capture boundary are rejected.
    w.posthog.capture('$snapshot', { $snapshot_data: [{ type: 2, data: token }] })
    w.posthog.capture('safe-after-auth', { $current_url: location.href })
  }, CANARIES[0])
  await expect.poll(() => events(wire).map(event => event.event)).toContain('safe-after-auth')
  expect(events(wire).filter(event => event.event === '$snapshot')).toHaveLength(0)
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(false)
  expect(authRequests.map(body => JSON.parse(body))).toEqual([{ token: CANARIES[0] }])
  for (const canary of CANARIES) expect(JSON.stringify(wire)).not.toContain(canary)
})

async function choose(page: Page, analytics: boolean) {
  await page.evaluate(analytics => {
    const w = window as unknown as HarnessWindow
    w.consent.saveCookiePreferences({ essential: true, analytics, sessionRecording: false, timestamp: '' })
  }, analytics)
}

async function capture(page: Page, event: string, instant = false) {
  await page.evaluate(({ event, instant }) => {
    (window as unknown as HarnessWindow).posthog.capture(event, {}, instant ? { send_instantly: true } : undefined)
  }, { event, instant })
}

test('identity reset preserves validated analytics consent across logout and login', async ({ page }) => {
  const { wire } = await fixture(page, '/pricing')
  await page.evaluate(() => {
    const w = window as unknown as HarnessWindow
    w.analytics.loginCompleted('synthetic-first-account')
    w.analytics.logout()
    w.analytics.pricingViewed('monthly')
  })
  await expect.poll(() => events(wire).map(event => event.event)).toContain('pricing_viewed')
  const logout = events(wire).find(event => event.event === 'logout')!
  const anonymous = events(wire).find(event => event.event === 'pricing_viewed')!
  expect(logout.properties).toMatchObject({ distinct_id: 'synthetic-first-account' })
  expect(anonymous.properties).not.toMatchObject({ distinct_id: 'synthetic-first-account' })
  await page.evaluate(() => {
    const w = window as unknown as HarnessWindow
    w.analytics.loginCompleted('synthetic-second-account')
    w.analytics.pricingViewed('yearly')
    w.analytics.reset()
    w.analytics.companySearched('synthetic-query', 0)
  })
  await expect.poll(() => events(wire).map(event => event.event)).toContain('company_searched')
  expect(events(wire).find(event => event.event === 'pricing_viewed' && (event.properties as Record<string, unknown>)?.billing_cycle === 'yearly')?.properties)
    .toMatchObject({ distinct_id: 'synthetic-second-account' })
  expect(events(wire).find(event => event.event === 'company_searched')?.properties)
    .not.toMatchObject({ distinct_id: 'synthetic-second-account' })
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(false)
})

test('identity reset never grants consent after refusal, missing or invalid storage, or failed-write withdrawal', async ({ page }) => {
  const { wire } = await fixture(page, '/pricing')
  await expect.poll(() => events(wire).map(event => event.event)).toContain('$pageview')
  for (const action of ['refuse', 'clear', 'invalid', 'failed-write']) {
    await choose(page, true)
    const result = await page.evaluate(action => {
      const w = window as unknown as HarnessWindow
      if (action === 'clear') localStorage.removeItem('cookie_consent')
      else if (action === 'invalid') localStorage.setItem('cookie_consent', '{"analytics":true}')
      else {
        if (action === 'failed-write') {
          Storage.prototype.setItem = () => { throw new DOMException('Unavailable') }
          Storage.prototype.removeItem = () => { throw new DOMException('Unavailable') }
        }
        w.consent.saveCookiePreferences({ essential: true, analytics: false, sessionRecording: false, timestamp: '' })
      }
      w.analytics.reset()
      w.analytics.pricingViewed('monthly')
      return {
        allowed: w.consentGuard.browserAnalyticsAllowed(),
        captureBlocked: w.posthog.capture(`blocked-reset-${action}`) === undefined,
        recording: w.posthog.sessionRecordingStarted(),
      }
    }, action)
    expect(result, action).toEqual({ allowed: false, captureBlocked: true, recording: false })
  }
  await page.waitForLoadState('networkidle')
  expect(events(wire).filter(event => event.event === 'pricing_viewed')).toEqual([])
  expect(events(wire).filter(event => String(event.event).startsWith('blocked-reset-'))).toEqual([])
})

test('withdrawal discards accepted batches and unload beacons; a fresh allow cannot revive them', async ({ page }) => {
  await page.clock.install()
  const { wire } = await fixture(page, '/pricing', true)
  await capture(page, 'before-withdrawal', true)
  await expect.poll(() => events(wire).map(event => event.event)).toContain('before-withdrawal')
  await capture(page, 'queued-before-withdrawal')
  expect(events(wire).map(event => event.event)).not.toContain('queued-before-withdrawal')
  await choose(page, false)
  await capture(page, 'captured-after-withdrawal', true)
  await page.evaluate(() => (window as unknown as HarnessWindow).posthog._handle_unload())
  await choose(page, true)
  await page.clock.fastForward(6000)
  await capture(page, 'fresh-after-allow', true)
  await expect.poll(() => events(wire).map(event => event.event)).toContain('fresh-after-allow')
  expect(events(wire).map(event => event.event)).not.toContain('queued-before-withdrawal')
  expect(events(wire).map(event => event.event)).not.toContain('captured-after-withdrawal')
})

test('offline retries are discarded on withdrawal and do not return after reconnect and re-allow', async ({ page, context }) => {
  await page.clock.install()
  const state = await fixture(page, '/pricing')
  await expect.poll(() => events(state.wire).map(event => event.event)).toContain('$pageview')
  state.fail(true)
  await capture(page, 'failed-before-offline', true)
  await expect.poll(() => page.evaluate(() => (window as unknown as HarnessWindow).posthog._retryQueue?.length)).toBeGreaterThan(0)
  await context.setOffline(true)
  await page.clock.fastForward(12000)
  await choose(page, false)
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog._retryQueue?.length)).toBe(0)
  await choose(page, true)
  state.fail(false)
  await context.setOffline(false)
  await page.clock.fastForward(12000)
  await capture(page, 'fresh-online', true)
  await expect.poll(() => events(state.wire).map(event => event.event)).toContain('fresh-online')
  expect(events(state.wire).filter(event => event.event === 'failed-before-offline')).toHaveLength(1)
})

test('an already dispatched request cannot be recalled, but its late failure cannot retry after withdrawal and re-allow', async ({ page }) => {
  await page.clock.install()
  const state = await fixture(page, '/pricing')
  await expect.poll(() => events(state.wire).map(event => event.event)).toContain('$pageview')
  state.hold()
  await capture(page, 'in-flight-at-withdrawal', true)
  await expect.poll(() => events(state.wire).map(event => event.event)).toContain('in-flight-at-withdrawal')
  await choose(page, false)
  await choose(page, true)
  state.release()
  await expect.poll(() => page.evaluate(() => (window as unknown as HarnessWindow).posthog._retryQueue?.length)).toBeGreaterThan(0)
  await page.clock.fastForward(12000)
  await capture(page, 'fresh-after-late-failure', true)
  await expect.poll(() => events(state.wire).map(event => event.event)).toContain('fresh-after-late-failure')
  expect(events(state.wire).filter(event => event.event === 'in-flight-at-withdrawal')).toHaveLength(1)
})

test('another tab’s refusal, storage clear and failed-write broadcast stop the real SDK', async ({ page, context }) => {
  const { wire } = await fixture(page, '/pricing')
  await expect.poll(() => events(wire).map(event => event.event)).toContain('$pageview')
  const other = await context.newPage()
  await fixture(other, '/pricing')
  for (const action of ['refuse', 'clear', 'failed-write']) {
    await choose(page, true)
    await expect.poll(() => other.evaluate(() => (window as unknown as HarnessWindow).consent.getCookiePreferences()?.analytics)).toBe(true)
    await other.evaluate(action => {
      const w = window as unknown as HarnessWindow
      if (action === 'clear') localStorage.clear()
      else {
        if (action === 'failed-write') {
          Storage.prototype.setItem = () => { throw new DOMException('Unavailable') }
          Storage.prototype.removeItem = () => { throw new DOMException('Unavailable') }
        }
        w.consent.saveCookiePreferences({ essential: true, analytics: false, sessionRecording: false, timestamp: '' })
      }
    }, action)
    await expect.poll(() => page.evaluate(() => (window as unknown as HarnessWindow).consent.getCookiePreferences()?.analytics === true)).toBe(false)
    await capture(page, `blocked-cross-tab-${action}`, true)
  }
  expect(events(wire).map(event => event.event).filter(name => String(name).startsWith('blocked-cross-tab'))).toEqual([])
  await other.close()
})

for (const withdrawal of ['deny', 'clear'] as const) {
  test(`a delayed cross-tab ${withdrawal} then allow discards pre-withdrawal batches before resuming`, async ({ page, context }) => {
    await page.clock.install()
    await page.addInitScript(() => {
      const w = window as unknown as HarnessWindow
      w.heldConsentEvents = []
      const hold = (event: StorageEvent) => {
        if (event.key !== null && event.key !== 'cookie_consent') return
        event.stopImmediatePropagation()
        w.heldConsentEvents!.push({ key: event.key, newValue: event.newValue, oldValue: event.oldValue, storageArea: event.storageArea, url: event.url })
      }
      // Hold native notifications so both remote choices reach shared storage before application
      // subscribers run, as for a suspended tab. Replay the actual events, in their native order.
      window.addEventListener('storage', hold, true)
      w.releaseConsentEvents = () => {
        window.removeEventListener('storage', hold, true)
        for (const event of w.heldConsentEvents!) window.dispatchEvent(new StorageEvent('storage', event))
      }
    })
    const { wire } = await fixture(page, '/pricing', true)
    const other = await context.newPage()
    await fixture(other, '/pricing')
    await capture(page, 'confirmed-before-history', true)
    await expect.poll(() => events(wire).map(event => event.event)).toContain('confirmed-before-history')
    // Prove batched captures flush before testing withdrawal of the next queued batch.
    await capture(page, 'confirmed-batch-before-history')
    await page.clock.fastForward(6000)
    await expect.poll(() => events(wire).map(event => event.event)).toContain('confirmed-batch-before-history')
    await capture(page, 'queued-before-remote-history')
    expect(events(wire).map(event => event.event)).not.toContain('queued-before-remote-history')
    await other.evaluate(withdrawal => {
      const w = window as unknown as HarnessWindow
      if (withdrawal === 'clear') localStorage.clear()
      else w.consent.saveCookiePreferences({ essential: true, analytics: false, sessionRecording: false, timestamp: '' })
      w.consent.saveCookiePreferences({ essential: true, analytics: true, sessionRecording: false, timestamp: '' })
    }, withdrawal)
    await expect.poll(() => page.evaluate(() => (window as unknown as HarnessWindow).heldConsentEvents?.length)).toBeGreaterThanOrEqual(2)
    expect(await page.evaluate(() => (window as unknown as HarnessWindow).consent.getCookiePreferences()?.analytics)).toBe(true)
    // A late-installed window listener cannot suspend earlier storage subscribers.
    // Verify our early hold actually preserved accepted work until history is released.
    expect(await page.evaluate(() => {
      const queue = (window as unknown as HarnessWindow).posthog._requestQueue as unknown as {
        _queue: Array<{ data: { event?: string } }>
      }
      return queue._queue.map(request => request.data.event)
    })).toContain('queued-before-remote-history')
    await page.evaluate(() => (window as unknown as HarnessWindow).releaseConsentEvents?.())
    // This marker shares the next batch with any surviving old events. Waiting for
    // it observes that batch's asynchronous compression and transport completion.
    await capture(page, 'fresh-after-remote-history')
    await page.clock.fastForward(6000)
    await expect.poll(() => events(wire).map(event => event.event)).toContain('fresh-after-remote-history')
    expect(events(wire).map(event => event.event)).not.toContain('queued-before-remote-history')
    await other.close()
  })
}

import { test, expect, type Page, type Request } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { gunzipSync } from 'node:zlib'
import ts from 'typescript'
import type { CaptureResult, PostHog } from 'posthog-js'
import type * as Privacy from '../../lib/telemetryPrivacy'
import type * as PostHogPrivacy from '../../lib/posthogPrivacy'

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
  replaySeen: CaptureResult[]
  replayDropped: number
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

// Replay applies gzip inside its JSON event envelope as well as on the HTTP body.
function unpackReplay(value: unknown): unknown {
  if (typeof value === 'string') {
    const bytes = Buffer.from(value, 'latin1')
    if (bytes[0] === 0x1f && bytes[1] === 0x8b) return unpackReplay(JSON.parse(gunzipSync(bytes).toString()))
    return value
  }
  if (Array.isArray(value)) return value.map(unpackReplay)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, unpackReplay(item)]))
  }
  return value
}

function helperScript(): string {
  const compile = (name: string) => ts.transpileModule(
    readFileSync(path.resolve(__dirname, `../../lib/${name}.ts`), 'utf8'),
    { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } },
  ).outputText
  return `(() => {
    const modules = {};
    const load = (name, execute) => { const exports = {}; execute(exports, id => modules[id]); modules[name] = exports; return exports; };
    window.privacy = load('./telemetryPrivacy', function(exports, require) { ${compile('telemetryPrivacy')} });
    window.posthogPrivacy = load('./posthogPrivacy', function(exports, require) { ${compile('posthogPrivacy')} });
  })();`
}

async function fixture(page: Page, initialPath: string): Promise<{ wire: WireRequest[]; authRequests: string[] }> {
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
  await page.addScriptTag({ path: path.resolve('node_modules/posthog-js/dist/array.full.no-external.js') })
  await page.addScriptTag({ content: helperScript() })
  await page.evaluate(({ key, host }) => {
    const w = window as unknown as HarnessWindow
    w.replaySeen = []
    w.replayDropped = 0
    w.privacy.installTelemetryNavigationGuard()
    w.privacy.onRecordingBlocked(() => w.posthog.stopSessionRecording())
    const privacyConfig = w.posthogPrivacy.postHogPrivacyConfig(w.posthog)
    const beforeSend = privacyConfig.before_send
    if (typeof beforeSend !== 'function') throw new Error('Expected application before_send boundary')
    w.posthog.init(key, {
      ...privacyConfig,
      api_host: host,
      persistence: 'localStorage', persistence_name: 'privacy-network',
      capture_pageview: false, capture_pageleave: false, autocapture: false,
      // Otherwise the real SDK intentionally drops Chromium automation as bot traffic.
      opt_out_useragent_filter: true,
      request_batching: false,
      disable_session_recording: !w.privacy.canRecordTelemetry(),
      before_send: event => {
        // Recorder debug metadata can contain callbacks; retain its JSON wire shape.
        if (event?.event === '$snapshot') w.replaySeen.push(JSON.parse(JSON.stringify(event)))
        const result = beforeSend(event)
        if (event?.event === '$snapshot' && !result) w.replayDropped += 1
        return result
      },
      loaded: client => {
        w.posthogPrivacy.initializePostHogPrivacy(client)
        client.opt_in_capturing()
        if (w.privacy.canRecordTelemetry()) client.startSessionRecording()
        else client.stopSessionRecording()
      },
    })
    w.posthog.capture('$pageview', { $current_url: window.location.href })
    // Application identity traits are sanitized before entering the SDK; inherited raw
    // persistence above separately exercises the migration of previously stored values.
    w.posthog.setPersonPropertiesForFlags(w.privacy.sanitizeTelemetry({ landing: window.location.href }))
    w.posthog.reloadFeatureFlags()
  }, { key: PROJECT_KEY, host: INGEST })
  return { wire, authRequests }
}

function events(wire: WireRequest[]): Array<Record<string, unknown>> {
  return wire.filter(request => /\/(?:e|s)\/?$/.test(new URL(request.url).pathname))
    .flatMap(request => {
      const payload = request.payload as { batch?: unknown[] } | null
      return Array.isArray(payload) ? payload : Array.isArray(payload?.batch) ? payload.batch : [payload]
    })
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
}

test('real PostHog transport removes auth URLs and cannot resume queued replay after an auth transition', async ({ page }) => {
  // Initial auth entry exercises stored attribution and /flags, which bypass before_send.
  let { wire, authRequests } = await fixture(page, `/reset-password?token=${CANARIES[0]}#access_token=${CANARIES[0]}`)
  await expect.poll(() => wire.some(request => new URL(request.url).pathname.startsWith('/flags'))).toBe(true)
  await expect.poll(() => events(wire).map(event => event.event), { message: 'The real SDK must send an event, not merely load configuration' }).toContain('$pageview')
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(false)
  expect(events(wire).filter(event => event.event === '$snapshot')).toHaveLength(0)
  for (const canary of CANARIES) expect(JSON.stringify(wire)).not.toContain(canary)
  const persistence = await page.evaluate(() => {
    const client = (window as unknown as HarnessWindow).posthog
    return JSON.stringify([client.persistence?.props, client.sessionPersistence?.props])
  })
  for (const canary of CANARIES) expect(persistence).not.toContain(canary)

  // Fresh document: prove recording really works before testing that auth stops it.
  await page.evaluate(() => (window as unknown as HarnessWindow).posthog.stopSessionRecording())
  ;({ wire, authRequests } = await fixture(page, '/pricing'))
  await expect.poll(() => page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(true)
  await page.getByRole('button', { name: 'Interact' }).click()
  await expect.poll(async () => {
    // rrweb's native gzip completion is asynchronous; flush only after allowing it to drain.
    await page.evaluate(() => {
      const w = window as unknown as HarnessWindow
      w.posthog.sessionRecording?.flushBeforeIdentityReset()
    })
    return events(wire).some(event => event.event === '$snapshot')
  }).toBe(true)
  const before = events(wire).filter(event => event.event === '$snapshot').length
  const hadCompressedSnapshot = await page.evaluate(() => {
    const w = window as unknown as HarnessWindow
    return w.replaySeen.some(event => JSON.stringify(event).includes('\\u001f'))
  })
  expect(hadCompressedSnapshot, 'real rrweb data must exercise the compressed snapshot boundary').toBe(true)

  const authLocation = await page.evaluate(async ({ token, site }) => {
    const w = window as unknown as HarnessWindow
    const queued = JSON.parse(JSON.stringify(w.replaySeen.at(-1)!)) as CaptureResult
    history.pushState({}, '', `/reset-password?token=${token}`)
    document.querySelector('main')!.innerHTML = `<h1>Reset password</h1><input type="hidden" value="${token}"><a href="${site}/auth/callback?code=${token}">Continue</a>`
    w.posthog.capture('$pageview', { $current_url: location.href, token })
    const authLocation = location.href
    await fetch('/api/auth/reset-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password: 'synthetic-password-for-local-fixture' }),
    })
    // Replay may already be compressed and awaiting a callback when the route changes.
    // Re-enter the real SDK's capture/transport boundary with the actual recorder payload.
    w.posthog.capture('$snapshot', queued.properties)
    history.replaceState({}, '', '/pricing')
    w.posthog.capture('$snapshot', queued.properties)
    w.posthog.capture('safe-after-auth', { $current_url: location.href })
    w.posthog.reloadFeatureFlags()
    return authLocation
  }, { token: CANARIES[0], site: SITE })
  await expect.poll(() => events(wire).some(event => event.event === 'safe-after-auth')).toBe(true)
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).privacy.canRecordTelemetry())).toBe(false)
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).posthog.sessionRecordingStarted())).toBe(false)
  expect(await page.evaluate(() => (window as unknown as HarnessWindow).replayDropped)).toBeGreaterThanOrEqual(2)
  expect(events(wire).filter(event => event.event === '$snapshot')).toHaveLength(before)
  expect(authLocation).toBe(`${SITE}/reset-password?token=${CANARIES[0]}`)
  expect(authRequests.map(body => JSON.parse(body))).toEqual([
    { token: CANARIES[0], new_password: 'synthetic-password-for-local-fixture' },
  ])
  for (const canary of CANARIES) expect(JSON.stringify(unpackReplay(wire))).not.toContain(canary)
})

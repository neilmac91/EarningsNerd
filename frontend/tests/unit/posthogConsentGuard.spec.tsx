import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { gunzipSync } from 'node:zlib'
import { act, cleanup, render, screen } from '@testing-library/react'
import type { CaptureResult, PostHog, PostHogConfig } from 'posthog-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PostHogQueues } from '@/lib/posthogConsent'

/**
 * The consent guard (lib/posthogConsent.ts) on the real posthog-js builds, with no stand-in client: the package entry
 * (Vitest resolves `main`) and the `module` build that Next bundles into the app. Both rename the client's private
 * members. The guard once read `_send_retriable_request` and `_retryQueue` by name, so it threw "Cannot read
 * properties of undefined (reading 'bind')" before posthog.init on every page and production PostHog never started.
 * Each failure the guard must survive is planted on a real client at `loaded`, as a later build might ship it, with
 * its flag requests on, its persistence in browser storage and its script loading on, as the app runs it. Nothing the
 * client then captures or requests may leave, and it may load no script. Those calls must store no credential URL; the
 * client must report once, and keep the consent posthog-js stores for every tab at the visitor's choice. The provider
 * runs on real clients too, with each of its failure paths planted, and an account is identified only while analytics
 * is allowed. SDK_OPTIONS turns script loading, flags and remote configuration off for the other clients, since jsdom
 * loads no script.
 *
 * posthog-js binds fetch and XMLHttpRequest when its module first runs, so both are replaced before any import: every
 * request the SDK makes is answered by the stand-in fetch, and without `withCredentials` the SDK keeps no XHR
 * transport (jsdom has no sendBeacon). Nothing leaves the process.
 */
const wire = vi.hoisted(() => {
  const state = {
    calls: [] as Array<{ url: string; events: string[]; text: string }>,
    decode: (_body: unknown): Promise<string[]> => Promise.resolve([]),
    text: (_body: unknown): Promise<string> => Promise.resolve(''),
    respond: (_events: string[]): number | Promise<number> => 200,
  }
  globalThis.fetch = (async (input: unknown, init?: { body?: unknown }) => {
    const call = { url: String(input), events: [] as string[], text: '' }
    state.calls.push(call)
    call.text = await state.text(init?.body).catch(() => '')
    call.events = await state.decode(init?.body).catch((error: unknown) => [`undecodable: ${String(error)} (${Object.prototype.toString.call(init?.body)})`])
    return new Response('{}', { status: await state.respond(call.events) })
  }) as typeof fetch
  globalThis.XMLHttpRequest = class {} as unknown as typeof XMLHttpRequest
  return state
})
const sentry = vi.hoisted(() => ({ captureException: vi.fn(), setUser: vi.fn() }))
vi.mock('@sentry/nextjs', async (original) => ({
  ...(await original<object>()), captureException: sentry.captureException, setUser: sentry.setUser,
}))
vi.mock('next/navigation', () => ({ usePathname: () => '/pricing', useSearchParams: () => new URLSearchParams() }))

async function bytesOf(body: unknown): Promise<Buffer> {
  if (typeof (body as Blob).arrayBuffer === 'function') return Buffer.from(await (body as Blob).arrayBuffer())
  return Buffer.from(ArrayBuffer.isView(body) ? body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) : body as ArrayBuffer)
}

/** A request body as the JSON it carries, whether sent as text, form data or gzip. */
async function bodyData(body: unknown): Promise<unknown> {
  if (typeof body === 'string') {
    return JSON.parse(body.startsWith('data=') ? Buffer.from(new URLSearchParams(body).get('data')!, 'base64').toString() : body)
  }
  const bytes = await bytesOf(body)
  return JSON.parse((bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes) : bytes).toString())
}

wire.text = async (body) => body === undefined || body === null ? '' : JSON.stringify(await bodyData(body))
wire.decode = async (body) => {
  if (body === undefined || body === null) return []
  const data = await bodyData(body)
  const batch = (data as { batch?: unknown })?.batch
  const items = Array.isArray(data) ? data : Array.isArray(batch) ? batch : [data]
  return items.flatMap(item => typeof (item as { event?: unknown })?.event === 'string' ? [(item as { event: string }).event] : [])
}

const KEY = 'phc_synthetic_consent_guard_test'
const INGEST = 'https://ingest.invalid'
const CANARY = 'synthetic-reset-canary'
const stored = () => JSON.stringify(Array.from({ length: localStorage.length }, (_, i) => [localStorage.key(i), localStorage.getItem(localStorage.key(i)!)]))
const sent = (event: string) => wire.calls.filter(call => call.events.includes(event)).length
const flagsSent = () => wire.calls.filter(call => call.url.includes('/flags/')).length
/** The scripts posthog-js has added to the page from the ingest host. jsdom never fetches them. */
const postHogScripts = () => Array.from(document.querySelectorAll('script[src]'), script => script.getAttribute('src')!)
  .filter(src => src.startsWith(INGEST))

// The package's `module` entry, read from its package.json as a bundler reads it.
const packageRoot = path.dirname(createRequire(import.meta.url).resolve('posthog-js/package.json'))
const moduleEntry = (JSON.parse(readFileSync(path.join(packageRoot, 'package.json'), 'utf8')) as { module: string }).module
type Sdk = { PostHog: new () => PostHog; default: PostHog }
const ENTRIES: Array<[string, () => Promise<Sdk>]> = [
  ['the package entry', async () => (await import('posthog-js')) as unknown as Sdk],
  [`the module build Next bundles (${moduleEntry})`, async () => (await import(/* @vite-ignore */ pathToFileURL(path.join(packageRoot, moduleEntry)).href)) as Sdk],
]

const unsubscribes: Array<() => void> = []
const clients: PostHog[] = []

async function choices() {
  const consent = await import('@/lib/browserConsent')
  return (analytics: boolean) => {
    consent.saveCookiePreferences({ essential: true, analytics, sessionRecording: false, timestamp: '' })
  }
}

beforeEach(() => {
  wire.calls.length = 0
  wire.respond = () => 200
  sentry.captureException.mockClear()
  sentry.setUser.mockClear()
  localStorage.clear()
})

afterEach(async () => {
  cleanup()
  while (unsubscribes.length) unsubscribes.pop()!()
  vi.useRealTimers()
  for (const client of clients.splice(0)) await client.shutdown()
  for (const script of Array.from(document.querySelectorAll('script'))) script.remove()
  window.history.replaceState(null, '', '/') // A test that stops at a credential URL leaves none for the next.
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

const SDK_OPTIONS = { api_host: INGEST, persistence: 'memory', disable_external_dependency_loading: true, advanced_disable_flags: true } as const

/** A real client, guarded and initialized as the provider does; `plant` changes it at `loaded`, as a later build might. */
async function start(sdk: Sdk, plant?: (client: PostHog, queues: PostHogQueues) => void, overrides: Partial<PostHogConfig> = {}) {
  const consent = await import('@/lib/browserConsent')
  const guard = await import('@/lib/posthogConsent')
  const privacy = await import('@/lib/posthogPrivacy')
  const client = new sdk.PostHog()
  clients.push(client)
  // Throws on main's guard: the build has no _send_retriable_request to bind.
  guard.installPostHogConsentGuard(client)
  unsubscribes.push(consent.subscribeCookiePreferences(() => guard.applyPostHogConsent(client)))
  // posthog-js swallows a throw from `loaded`, so its results are read after init rather than asserted inside it.
  let applied: boolean | undefined
  let capturingAtLoad: boolean | undefined
  client.init(KEY, {
    ...privacy.postHogPrivacyConfig(client),
    ...SDK_OPTIONS,
    autocapture: false, capture_pageview: false, capture_pageleave: false,
    opt_out_capturing_by_default: true, request_batching: true,
    ...overrides,
    loaded: (loaded) => {
      capturingAtLoad = loaded.is_capturing()
      if (plant) plant(loaded, guard.findPostHogQueues(loaded)!)
      privacy.initializePostHogPrivacy(loaded)
      applied = guard.applyPostHogConsent(loaded)
    },
  } satisfies Partial<PostHogConfig>)
  return { client, guard, applied, capturingAtLoad }
}

/**
 * Another tab's SDK, configured as the provider configures one: the same key, so it shares posthog-js's consent store
 * through localStorage, and off by default, so a cleared store reads as off. Its own host keeps its requests apart.
 */
function otherTab(sdk: Sdk) {
  const tab = new sdk.PostHog()
  clients.push(tab)
  tab.init(KEY, {
    ...SDK_OPTIONS, api_host: 'https://other-tab.invalid',
    autocapture: false, capture_pageview: false, capture_pageleave: false, opt_out_capturing_by_default: true,
  })
  return tab
}

const hide = (client: PostHog, ...objects: unknown[]) => {
  for (const key of Object.keys(client)) {
    if (objects.includes((client as unknown as Record<string, unknown>)[key])) Object.defineProperty(client, key, { enumerable: false })
  }
}

// Each way a later build could leave the guard unable to hold, planted at `loaded`.
const PLANTED_FAILURES: Array<[string, (client: PostHog, queues: PostHogQueues) => void]> = [
  ['its queues out of the guard\'s sight', (client, { retry, batch }) => hide(client, retry, batch)],
  ['a second RetryQueue', client => Object.assign(client, {
    laterRetryQueue: { _instance: client, retriableRequest: () => undefined, resume: () => undefined, unload: () => undefined },
  })],
  ['a second RequestQueue', client => Object.assign(client, {
    laterRequestQueue: { enqueue: () => undefined, enable: () => undefined, unload: () => undefined },
  })],
  ['no __request_queue', client => { delete (client as { __request_queue?: unknown }).__request_queue }],
]

describe.each(ENTRIES)('the consent guard on %s', (_entry, load) => {
  it('lets allowed requests leave and stops a withdrawn choice\'s queued, retried and in-flight requests', async () => {
    vi.useFakeTimers()
    const choose = await choices()
    choose(true)
    const { client, guard, applied } = await start(await load())
    expect(applied).toBe(true)
    const queues = guard.findPostHogQueues(client)!
    // The guard holds the queue the build really dispatches through, found by its shape.
    expect(Object.hasOwn(queues.retry, 'retriableRequest')).toBe(true)

    // The accept case: an allowed event leaves, sent at once and batched. A batch is gzipped through the async
    // CompressionStream, which needs real event-loop turns, so wait for it rather than for fake time alone.
    client.capture('accepted-instant', {}, { send_instantly: true })
    client.capture('accepted-batched')
    await vi.advanceTimersByTimeAsync(5_000) // Past the batch's flush.
    await vi.waitFor(() => expect([sent('accepted-instant'), sent('accepted-batched')]).toEqual([1, 1]))

    // Each state a withdrawal must stop: a batch waiting for its flush, a failed send waiting to retry, and a send
    // already on the wire whose failure only arrives after the withdrawal and a fresh allow.
    let release: (status: number) => void = () => undefined
    wire.respond = events => {
      if (events.includes('failed-before-withdrawal')) return 503
      if (events.includes('in-flight-at-withdrawal')) return new Promise<number>(resolve => { release = resolve })
      return 200
    }
    client.capture('queued-before-withdrawal')
    client.capture('failed-before-withdrawal', {}, { send_instantly: true })
    client.capture('in-flight-at-withdrawal', {}, { send_instantly: true })
    await vi.advanceTimersByTimeAsync(10)
    expect(queues.retry.length).toBe(1)
    expect(sent('in-flight-at-withdrawal')).toBe(1)

    choose(false)
    expect(queues.retry.length).toBe(0)
    client.capture('captured-after-withdrawal', {}, { send_instantly: true })
    choose(true)
    release(503)
    await vi.advanceTimersByTimeAsync(10)
    expect(queues.retry.length).toBe(1) // The late failure was queued for retry, still carrying its old generation.
    await vi.advanceTimersByTimeAsync(60_000) // Every flush and retry is due.
    client.capture('fresh-after-allow', {}, { send_instantly: true })
    await vi.advanceTimersByTimeAsync(10)

    expect(queues.retry.length).toBe(0)
    expect({
      queued: sent('queued-before-withdrawal'),
      failed: sent('failed-before-withdrawal'),
      inFlight: sent('in-flight-at-withdrawal'),
      afterWithdrawal: sent('captured-after-withdrawal'),
      fresh: sent('fresh-after-allow'),
    }).toEqual({ queued: 0, failed: 1, inFlight: 1, afterWithdrawal: 0, fresh: 1 })
    expect(sentry.captureException).not.toHaveBeenCalled()
  })

  it.each(PLANTED_FAILURES)('turns a client with %s off for the page, reports once and keeps every tab\'s consent at the choice', async (_plant, plant) => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const sdk = await load()
    // Another tab opts in through posthog-js's consent store, which every tab on the origin shares.
    const tab = otherTab(sdk)
    tab.opt_in_capturing({ captureEventName: false })
    const { client, guard, applied, capturingAtLoad } = await start(sdk, plant, {
      advanced_disable_flags: false, persistence: 'localStorage', disable_external_dependency_loading: false,
    })
    expect(capturingAtLoad).toBe(true) // The shared opt-in reached this client: only its own failed state can stop it.
    expect(applied).toBe(false)
    expect(client.is_capturing()).toBe(false)
    // posthog-js loads its remote configuration through a script tag right after `loaded`, past both wrappers. The
    // failed client loads none, so that configuration falls back to a request the wrappers drop (checked below).
    expect(postHogScripts()).toEqual([])

    // Nothing the failed client captures or requests leaves, sent at once, batched, as flags after an identify or on
    // pagehide through its unguarded retry queue; and on a credential URL it stores nothing it sees.
    window.history.replaceState(null, '', `/reset-password?token=${CANARY}`)
    client.capture('failed-client-instant', {}, { send_instantly: true })
    client.capture('failed-client-batched')
    client.identify('synthetic-account-7')
    client.reloadFeatureFlags()
    client._handle_unload()
    await new Promise(resolve => setTimeout(resolve, 50))
    window.history.replaceState(null, '', '/')
    expect(wire.calls.filter(call => call.url.startsWith(INGEST))).toEqual([])
    expect(stored()).not.toContain(CANARY)

    // It keeps the shared store at the visitor's choice, as a healthy tab does: the other tab follows a refusal and an
    // allow, and a logout's reset(), which clears the store, does not leave it cleared.
    choose(false)
    expect(tab.is_capturing()).toBe(false)
    choose(true)
    expect(tab.is_capturing()).toBe(true)
    client.reset()
    guard.applyPostHogConsent(client)
    expect([tab.is_capturing(), client.is_capturing()]).toEqual([true, false])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBeInstanceOf(guard.PostHogConsentGuardError)
    expect(sentry.captureException.mock.calls[0][1]).toEqual({ tags: { posthog_js: client.version } })
  })

  it('keeps every tab\'s consent at the choice when a logout\'s reset meets the guard\'s first failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const sdk = await load()
    const tab = otherTab(sdk)
    tab.opt_in_capturing({ captureEventName: false })
    const { client, guard, applied } = await start(sdk)
    expect(applied).toBe(true)
    // The guard held until now. reset() clears the store every tab shares, and the application that follows it (as
    // lib/analytics.ts runs one) is the first to find the queues gone, so it alone can put the store back.
    const { retry, batch } = guard.findPostHogQueues(client)!
    hide(client, retry, batch)
    client.reset()
    expect(tab.is_capturing()).toBe(false)
    expect(guard.applyPostHogConsent(client)).toBe(false)
    expect([tab.is_capturing(), client.is_capturing()]).toEqual([true, false])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
  })

  it('never throws for a failed client, though the SDK throws while it stores the choice', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const { client, guard, applied } = await start(await load())
    expect(applied).toBe(true)
    vi.spyOn(client, 'opt_in_capturing').mockImplementation(() => { throw new Error('planted: consent storage is unavailable') })
    // lib/analytics.ts applies the choice after a logout's reset with nothing around it to catch a throw. Neither the
    // application that first finds the guard broken (the catch branch) nor a later one (the failed branch) may throw.
    const { retry, batch } = guard.findPostHogQueues(client)!
    hide(client, retry, batch)
    expect(guard.applyPostHogConsent(client)).toBe(false)
    expect(guard.applyPostHogConsent(client)).toBe(false)
    expect(client.opt_in_capturing).toHaveBeenCalledTimes(2)
  })

  it('never throws for a failed client under a refusal either, though the SDK throws while it stores it', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const { client, guard, applied } = await start(await load())
    expect(applied).toBe(true)
    const { retry, batch } = guard.findPostHogQueues(client)!
    hide(client, retry, batch)
    vi.spyOn(client, 'opt_out_capturing').mockImplementation(() => { throw new Error('planted: consent storage is unavailable') })
    // The refusal reaches the client through its subscription, at the guard's first failure (the catch branch). The
    // choice's event does not hand a listener's throw back to this call, so the page's error event records any.
    const thrown: unknown[] = []
    const onError = (event: ErrorEvent) => {
      thrown.push(event.error)
      event.preventDefault()
    }
    window.addEventListener('error', onError)
    try {
      choose(false)
    } finally {
      window.removeEventListener('error', onError)
    }
    expect(thrown).toEqual([])
    expect(guard.applyPostHogConsent(client)).toBe(false) // A later application (the failed branch).
    expect(client.opt_out_capturing).toHaveBeenCalledTimes(2)
  })
})

describe('before_send', () => {
  // Each reason it drops an event for: a refusal the shared store has not caught up with, a failed guard, a snapshot.
  const DROPS: Array<[string, string, (choose: (analytics: boolean) => void, client: PostHog) => Promise<void>]> = [
    ['an event after a refusal', 'refused-event', async choose => choose(false)],
    ['an event of a client whose guard failed', 'failed-client-event', async (_choose, client) => {
      vi.spyOn(console, 'error').mockImplementation(() => undefined)
      ;(await import('@/lib/posthogConsent')).failPostHogClosed(client, new Error('planted: guard failure'))
    }],
    ['a replay snapshot', '$snapshot', async () => undefined],
  ]
  it.each(DROPS)('cleans stored attribution even for %s, which it drops', async (_drop, event, plant) => {
    const choose = await choices()
    choose(true)
    const { PostHog } = await import('posthog-js')
    const privacy = await import('@/lib/posthogPrivacy')
    const client = new PostHog()
    clients.push(client)
    client.init(KEY, { ...SDK_OPTIONS, autocapture: false, capture_pageview: false, capture_pageleave: false })
    await plant(choose, client)
    // posthog-js stores the raw page URL as session attribution before it calls before_send.
    client.register({ $client_session_props: { props: { u: `https://example.test/reset-password?token=${CANARY}` } } })
    expect(privacy.beforeSendPostHog(client, { event, properties: {} } as unknown as CaptureResult)).toBeNull()
    expect(JSON.stringify(client.persistence?.props)).not.toContain(CANARY)
  })

  it('drops every event of a client whose guard failed, though analytics is allowed', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const { PostHog } = await import('posthog-js')
    const privacy = await import('@/lib/posthogPrivacy')
    const guard = await import('@/lib/posthogConsent')
    const client = new PostHog()
    clients.push(client)
    client.init(KEY, { ...SDK_OPTIONS, autocapture: false, capture_pageview: false, capture_pageleave: false })
    const event = { event: 'allowed-event', properties: {} } as unknown as CaptureResult
    expect(privacy.beforeSendPostHog(client, event)).not.toBeNull() // The accept case.
    // Called directly: its own is_capturing would otherwise stop the event before before_send.
    guard.failPostHogClosed(client, new Error('planted guard failure'))
    expect(privacy.beforeSendPostHog(client, event)).toBeNull()
  })
})

/** The app's provider and an account-readiness probe, on `client` or, with none, on the package entry's singleton. */
async function renderProvider(client?: PostHog) {
  vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', KEY)
  vi.stubEnv('NEXT_PUBLIC_POSTHOG_HOST', INGEST)
  if (client) vi.doMock('posthog-js', async (original) => ({ ...(await original<object>()), default: client }))
  const { PostHogProvider } = await import('@/app/posthog-provider')
  const { usePostHogReady } = await import('@/lib/posthogReady')
  const choose = await choices()
  function Ready() {
    return <output data-testid="posthog-ready">{String(usePostHogReady())}</output>
  }
  const page = () => <PostHogProvider><Ready /></PostHogProvider>
  const view = render(page())
  return { choose, page, view, ready: () => screen.getByTestId('posthog-ready').textContent }
}

describe('the provider on the real SDK', () => {
  it('starts PostHog under the guard after an allow, never before it, and stops it after a refusal', async () => {
    const { default: posthog } = await import('posthog-js')
    const { choose, ready } = await renderProvider()
    act(() => choose(false))
    expect([posthog.__loaded, ready()]).toEqual([false, 'false'])
    expect(wire.calls).toEqual([])

    act(() => choose(true))
    expect([posthog.__loaded, posthog.is_capturing(), ready()]).toEqual([true, true, 'true'])
    // The app leaves posthog-js's script loading on, so a healthy client asks for its remote configuration as a script
    // (the failed clients below must not).
    expect(postHogScripts()).toEqual([`${INGEST}/array/${KEY}/config.js`])
    posthog.capture('provider-accepted', {}, { send_instantly: true })
    await vi.waitFor(() => expect(sent('provider-accepted')).toBe(1))

    act(() => choose(false))
    expect([posthog.is_capturing(), ready()]).toEqual([false, 'false'])
    posthog.capture('after-refusal', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-refusal')).toBe(0)

    // posthog-js stores an identity in its cookie and local storage even while capturing is off, so an account is
    // identified only while analytics is allowed (lib/analytics.ts), whichever page asks.
    const { analytics } = await import('@/lib/analytics')
    const holds = (id: string) => (stored() + decodeURIComponent(document.cookie)).includes(id)
    analytics.identify('synthetic-account-identify-check')
    expect(holds('synthetic-account-identify-check')).toBe(false)
    act(() => choose(true))
    const flagsBefore = flagsSent()
    analytics.identify('synthetic-account-identify-check')
    expect(holds('synthetic-account-identify-check')).toBe(true)
    // The allowed identify sends `$identify` once its async gzip finishes and reloads flags after a short debounce, and
    // the page-view tracker's `$pageview` waits in a batch. Let the first two leave and drain the batch with a refusal:
    // any of them would otherwise reach the stand-in fetch during a later test and read as that test's client sending.
    await vi.waitFor(() => expect(sent('$identify')).toBe(1))
    await vi.waitFor(() => expect(flagsSent()).toBeGreaterThan(flagsBefore))
    act(() => choose(false))
    expect(sentry.captureException).not.toHaveBeenCalled()
  })
})

// posthog-js keeps an identified reader's id across page loads until reset(), and only the dashboard's Log out reset it.
// A reader with no account carries none: hooks/usePostHogUserIdentification.ts forgets it once the reader is a guest,
// and the provider resets one a browser without a session kept from an earlier visit before posthog-js sends anything.
describe('an account PostHog keeps when the reader has none', () => {
  beforeEach(() => {
    vi.resetModules()
    // posthog-js persists to cookies too, which the file's beforeEach leaves; each case starts from none.
    for (const cookie of document.cookie.split(';')) {
      document.cookie = `${cookie.split('=')[0].trim()}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  })
  afterEach(async () => {
    ;(await import('@/lib/api/session')).clearSessionActive()
    vi.doUnmock('posthog-js')
    vi.resetModules()
  })

  /**
   * A page load of the app's provider and lib/analytics.ts on a fresh client, after an allow. The client reads what an
   * earlier page load stored, as a reload's would. (The package entry's own client survives vi.resetModules, since
   * Vitest leaves node_modules out of it, so each page load gets its own.)
   */
  async function visit() {
    cleanup()
    vi.resetModules()
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    clients.push(client)
    const before = wire.calls.length
    const { choose } = await renderProvider(client)
    const { analytics } = await import('@/lib/analytics')
    act(() => choose(true))
    expect(client.__loaded).toBe(true)
    return { client, analytics, choose, sinceLoad: () => wire.calls.slice(before) }
  }

  /** A page load that identifies the reader, once identify's requests have left. */
  async function identifiedVisit(id: string) {
    const page = await visit()
    const flagsBefore = flagsSent()
    page.analytics.identify(id)
    await vi.waitFor(() => expect(sent('$identify')).toBe(1))
    await vi.waitFor(() => expect(flagsSent()).toBeGreaterThan(flagsBefore))
    return page
  }

  /** A page load with analytics refused: PostHog never loads, so lib/analytics.ts reaches a client that has not. */
  async function refusedVisit() {
    cleanup()
    vi.resetModules()
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    clients.push(client)
    const { choose } = await renderProvider(client)
    const { analytics } = await import('@/lib/analytics')
    act(() => choose(false))
    expect(client.__loaded).toBe(false)
    return { analytics }
  }

  /** The page-view tracker's batched $pageview, once it has left (its flush waits a few seconds). */
  const pageViewSent = () => vi.waitFor(() => expect(sent('$pageview')).toBeGreaterThan(0), { timeout: 8000 })

  it('is forgotten once the reader is a guest, and a guest without one is left alone', async () => {
    const { client, analytics, choose } = await identifiedVisit('synthetic-account-forget-check')
    expect(client.get_distinct_id()).toBe('synthetic-account-forget-check')
    const device = client.get_property('$device_id')
    analytics.forgetAccount() // As the identification hook does once the account goes away, whichever way.
    const anonymous = client.get_distinct_id()
    expect(anonymous).not.toBe('synthetic-account-forget-check')
    expect(client.get_property('$device_id')).not.toBe(device) // Nothing later ties back to the account by device.
    expect((stored() + decodeURIComponent(document.cookie)).includes('synthetic-account-forget-check')).toBe(false)
    // reset() clears the consent every tab shares; the visitor's allow is restored, so PostHog stays on.
    expect(client.is_capturing()).toBe(true)
    expect(sentry.setUser).toHaveBeenLastCalledWith(null)
    sentry.setUser.mockClear()
    analytics.forgetAccount()
    expect(client.get_distinct_id()).toBe(anonymous)
    expect(sentry.setUser).toHaveBeenCalledWith(null) // Sentry's user goes even when PostHog holds no account.
    act(() => choose(false)) // Drains the page-view tracker's batch.
  })

  it('is reset before anything is sent when a browser without a session loads PostHog again', async () => {
    const first = await identifiedVisit('synthetic-account-stale-check')
    const device = first.client.get_property('$device_id') as string
    act(() => first.choose(false)) // Drains the first page load's batch, so nothing of it is still in flight.
    // The next page's address carries a credential, which nothing that page sends or stores may carry.
    window.history.replaceState(null, '', `/reset-password?token=${CANARY}`)
    const { client, choose, sinceLoad } = await visit()
    expect(client.get_distinct_id()).not.toBe('synthetic-account-stale-check')
    expect(client.get_property('$device_id')).not.toBe(device)
    // reset() clears the privacy seed too; it is written after the reset, so this page keeps its sanitized attribution.
    expect(client.get_property('$initial_person_info')).toMatchObject({ u: `${window.location.origin}/reset-password` })
    await pageViewSent() // The page-view tracker's first $pageview, which leaves in a batch.
    const carries = (value: string) => sinceLoad().filter(call => (call.url + call.text).includes(value))
    expect([carries('synthetic-account-stale-check'), carries(device), carries(CANARY)]).toEqual([[], [], []])
    expect((stored() + decodeURIComponent(document.cookie)).includes(CANARY)).toBe(false)
    act(() => choose(false))
  }, 20_000)

  it('is reset at the next load, whoever\'s session it is, when the account went away while PostHog was off', async () => {
    const first = await identifiedVisit('synthetic-account-pending-check')
    act(() => first.choose(false))
    // A later page with analytics refused: PostHog does not load there, so forgetting the account leaves word. Sentry's
    // user, which identify sets whatever the choice, goes too.
    const refused = await refusedVisit()
    refused.analytics.identify('synthetic-account-pending-check')
    expect(sentry.setUser).toHaveBeenLastCalledWith({ id: 'synthetic-account-pending-check' })
    refused.analytics.forgetAccount()
    expect(sentry.setUser).toHaveBeenLastCalledWith(null)
    // Another account then signs in on this browser and allows analytics.
    ;(await import('@/lib/api/session')).markSessionActive()
    const { client, choose, sinceLoad } = await visit()
    expect(client.get_distinct_id()).not.toBe('synthetic-account-pending-check')
    await pageViewSent()
    expect(sinceLoad().filter(call => (call.url + call.text).includes('synthetic-account-pending-check'))).toEqual([])
    act(() => choose(false))
  }, 20_000)

  it('leaves an anonymous browser\'s identity alone across a load', async () => {
    const first = await visit()
    const anonymous = first.client.get_distinct_id()
    act(() => first.choose(false))
    const { client, choose } = await visit()
    expect(client.get_distinct_id()).toBe(anonymous)
    act(() => choose(false))
  })

  it('starts another account on a fresh identity instead of switching the one PostHog holds', async () => {
    const { client, analytics, choose } = await identifiedVisit('synthetic-account-first')
    const device = client.get_property('$device_id')
    analytics.identify('synthetic-account-first') // The same account again, as after a plan change: nothing resets.
    expect([client.get_distinct_id(), client.get_property('$device_id')]).toEqual(['synthetic-account-first', device])
    const flagsBefore = flagsSent()
    analytics.identify('synthetic-account-second') // Another tab signed in, or a session ended unseen.
    expect(client.get_distinct_id()).toBe('synthetic-account-second')
    expect(client.get_property('$device_id')).not.toBe(device)
    await vi.waitFor(() => expect(sent('$identify')).toBe(2)) // Identified afresh, not switched silently.
    await vi.waitFor(() => expect(flagsSent()).toBeGreaterThan(flagsBefore))
    act(() => choose(false))
  })

  it('is kept while the browser\'s session goes on', async () => {
    const first = await identifiedVisit('synthetic-account-session-check')
    act(() => first.choose(false))
    ;(await import('@/lib/api/session')).markSessionActive()
    const { client, choose } = await visit()
    expect(client.get_distinct_id()).toBe('synthetic-account-session-check')
    act(() => choose(false))
  })
})

describe('the provider when PostHog cannot run under its guard', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.resetModules()
  })
  afterEach(() => {
    vi.doUnmock('posthog-js')
    vi.doUnmock('@/lib/posthogPrivacy')
    vi.resetModules()
  })

  // Before an allow the provider touches nothing, so a broken guard cannot report from every page view.
  const untouchedBeforeConsent = (client: PostHog, choose: (analytics: boolean) => void) => {
    act(() => choose(false))
    expect(client.__loaded).toBe(false)
    expect(sentry.captureException).not.toHaveBeenCalled()
  }

  it('never starts a client without _send_request, and reports that once', async () => {
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    Object.defineProperty(client, '_send_request', { value: undefined })
    const { choose, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    act(() => choose(false))
    act(() => choose(true))
    expect([client.__loaded, ready()]).toEqual([false, 'false'])
    expect(wire.calls).toEqual([])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toMatchObject({ name: 'PostHogConsentGuardError' })
  })

  it('keeps a client whose queues are out of the guard\'s sight off and not ready, across a remount, and reports once', async () => {
    const { PostHog } = await import('posthog-js')
    const { findPostHogQueues } = await import('@/lib/posthogConsent')
    // Learn which fields this build keeps its queues in, then plant a client whose fields hide them from the guard.
    const probe = new PostHog()
    probe.init(KEY, SDK_OPTIONS)
    const { retry, batch } = findPostHogQueues(probe)!
    const fields = Object.keys(probe).filter(key => [retry, batch].includes((probe as unknown as Record<string, never>)[key]))
    await probe.shutdown()
    expect(fields).toHaveLength(2)
    const client = new PostHog()
    clients.push(client)
    for (const key of fields) Object.defineProperty(client, key, { value: undefined, writable: true, enumerable: false, configurable: true })
    const { choose, page, view, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    expect([client.__loaded, ready()]).toEqual([true, 'false'])
    expect(postHogScripts()).toEqual([]) // No remote configuration script, unlike the healthy provider above.
    // GlobalErrorBoundary's "Try again" mounts the provider again over the loaded client. Seeded not ready, the page-view
    // tracker never mounts, not even for the first commit.
    const capture = vi.spyOn(client, 'capture')
    view.unmount()
    render(page())
    expect(ready()).toBe('false')
    expect(capture.mock.calls.map(([event]) => event)).toEqual([])
    client.capture('after-guard-failure', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-guard-failure')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toMatchObject({ name: 'PostHogConsentGuardError' })
  })

  it('turns PostHog off and reports a throw inside `loaded`, which posthog-js would swallow', async () => {
    const planted = new Error('planted: privacy seeding threw')
    vi.doMock('@/lib/posthogPrivacy', async (original) => ({
      ...(await original<object>()),
      initializePostHogPrivacy: () => { throw planted },
    }))
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    clients.push(client)
    const { choose, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    expect([client.__loaded, ready()]).toEqual([true, 'false'])
    expect(postHogScripts()).toEqual([])
    // Off, not only reported: later choices never opt it in, and nothing it captures leaves.
    act(() => choose(false))
    act(() => choose(true))
    client.capture('after-loaded-throw', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect([client.is_capturing(), ready(), sent('after-loaded-throw')]).toEqual([false, 'false', 0])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBe(planted)
  })

  it('turns PostHog off and not ready when its guard stops holding on a later choice', async () => {
    const { PostHog } = await import('posthog-js')
    const { findPostHogQueues } = await import('@/lib/posthogConsent')
    const client = new PostHog()
    clients.push(client)
    const { choose, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    expect(ready()).toBe('true')
    // Planted after a healthy load: the SDK now keeps its queues where the guard cannot see them, so the next
    // application returns false (no throw) and only that answer can lower readiness.
    const { retry, batch } = findPostHogQueues(client)!
    hide(client, retry, batch)
    act(() => choose(true))
    expect([ready(), client.is_capturing()]).toEqual(['false', false])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toMatchObject({ name: 'PostHogConsentGuardError' })
  })

  it('turns PostHog off and reports a throw while applying a later refusal', async () => {
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    clients.push(client)
    const { choose, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    expect([client.__loaded, client.is_capturing(), ready()]).toEqual([true, true, 'true'])
    // The SDK's own consent storage throws while it stores the refusal (storage full or blocked).
    const planted = new Error('planted: consent storage is unavailable')
    vi.spyOn(client, 'opt_out_capturing').mockImplementation(() => { throw planted })
    act(() => choose(false))
    act(() => choose(true))
    expect(ready()).toBe('false')
    // The shared store reads opted in (the refusal never stored, and the allow mirrored), so only the client's own
    // failed state stops it now.
    expect([client.consent.isOptedIn(), client.is_capturing()]).toEqual([true, false])
    client.capture('after-failed-refusal', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-failed-refusal')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBe(planted)
  })

  it('turns PostHog off, not ready, and drops what was already queued after a throw while applying a later allow', async () => {
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    clients.push(client)
    const { choose, ready } = await renderProvider(client)
    untouchedBeforeConsent(client, choose)
    act(() => choose(true))
    expect(ready()).toBe('true')
    client.capture('queued-before-failure')
    // The SDK throws while it applies the visitor's allow again (saved again here, or another tab's allow).
    const planted = new Error('planted: consent storage is unavailable')
    vi.spyOn(client, 'opt_in_capturing').mockImplementation(() => { throw planted })
    act(() => choose(true))
    expect([ready(), client.is_capturing()]).toEqual(['false', false])
    // The batch queued while it was healthy leaves through the guard on pagehide, and the failed client drops it.
    client._handle_unload()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(sent('queued-before-failure')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBe(planted)
  })
})

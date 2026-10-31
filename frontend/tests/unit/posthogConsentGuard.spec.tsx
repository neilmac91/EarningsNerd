import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { gunzipSync } from 'node:zlib'
import { act, cleanup, render, screen } from '@testing-library/react'
import type { PostHog, PostHogConfig } from 'posthog-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PostHogQueues } from '@/lib/posthogConsent'

/**
 * The consent guard (lib/posthogConsent.ts) on the real posthog-js builds, with no stand-in client: the package entry
 * (Vitest resolves `main`) and the `module` build that Next bundles into the app. Both rename the client's private
 * members. The guard once read `_send_retriable_request` and `_retryQueue` by name, so it threw "Cannot read
 * properties of undefined (reading 'bind')" before posthog.init on every page and production PostHog never started.
 * Each failure the guard must survive is planted on a real client at `loaded`, as a later build might ship it: the
 * client must then send nothing for the rest of the page, report once, and leave the consent posthog-js stores for
 * every tab alone. The provider runs on real clients too, with each of its failure paths planted.
 *
 * posthog-js binds fetch and XMLHttpRequest when its module first runs, so both are replaced before any import: every
 * request the SDK makes is answered by the stand-in fetch, and without `withCredentials` the SDK keeps no XHR
 * transport (jsdom has no sendBeacon). Nothing leaves the process.
 */
const wire = vi.hoisted(() => {
  const state = {
    calls: [] as Array<{ url: string; events: string[] }>,
    decode: (_body: unknown): Promise<string[]> => Promise.resolve([]),
    respond: (_events: string[]): number | Promise<number> => 200,
  }
  globalThis.fetch = (async (input: unknown, init?: { body?: unknown }) => {
    const call = { url: String(input), events: [] as string[] }
    state.calls.push(call)
    call.events = await state.decode(init?.body).catch((error: unknown) => [`undecodable: ${String(error)} (${Object.prototype.toString.call(init?.body)})`])
    return new Response('{}', { status: await state.respond(call.events) })
  }) as typeof fetch
  globalThis.XMLHttpRequest = class {} as unknown as typeof XMLHttpRequest
  return state
})
const sentry = vi.hoisted(() => ({ captureException: vi.fn() }))
vi.mock('@sentry/nextjs', async (original) => ({ ...(await original<object>()), captureException: sentry.captureException }))
vi.mock('next/navigation', () => ({ usePathname: () => '/pricing', useSearchParams: () => new URLSearchParams() }))

async function bytesOf(body: unknown): Promise<Buffer> {
  if (typeof (body as Blob).arrayBuffer === 'function') return Buffer.from(await (body as Blob).arrayBuffer())
  return Buffer.from(ArrayBuffer.isView(body) ? body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) : body as ArrayBuffer)
}

wire.decode = async (body) => {
  if (body === undefined || body === null) return []
  let data: unknown
  if (typeof body === 'string') {
    data = JSON.parse(body.startsWith('data=') ? Buffer.from(new URLSearchParams(body).get('data')!, 'base64').toString() : body)
  } else {
    const bytes = await bytesOf(body)
    data = JSON.parse((bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes) : bytes).toString())
  }
  const batch = (data as { batch?: unknown })?.batch
  const items = Array.isArray(data) ? data : Array.isArray(batch) ? batch : [data]
  return items.flatMap(item => typeof (item as { event?: unknown })?.event === 'string' ? [(item as { event: string }).event] : [])
}

const KEY = 'phc_synthetic_consent_guard_test'
const INGEST = 'https://ingest.invalid'
const sent = (event: string) => wire.calls.filter(call => call.events.includes(event)).length

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
  localStorage.clear()
})

afterEach(async () => {
  cleanup()
  while (unsubscribes.length) unsubscribes.pop()!()
  vi.useRealTimers()
  for (const client of clients.splice(0)) await client.shutdown()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

const SDK_OPTIONS = { api_host: INGEST, persistence: 'memory', disable_external_dependency_loading: true, advanced_disable_flags: true } as const

/** A real client, guarded and initialized as the provider does; `plant` changes it at `loaded`, as a later build might. */
async function start(sdk: Sdk, plant?: (client: PostHog, queues: PostHogQueues) => void) {
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
    loaded: (loaded) => {
      capturingAtLoad = loaded.is_capturing()
      if (plant) plant(loaded, guard.findPostHogQueues(loaded)!)
      privacy.initializePostHogPrivacy(loaded)
      applied = guard.applyPostHogConsent(loaded)
    },
  } satisfies Partial<PostHogConfig>)
  return { client, guard, applied, capturingAtLoad }
}

/** Another tab's SDK: a client on the same key, sharing posthog-js's consent store through localStorage. */
function otherTab(sdk: Sdk) {
  const tab = new sdk.PostHog()
  clients.push(tab)
  tab.init(KEY, { ...SDK_OPTIONS, autocapture: false, capture_pageview: false, capture_pageleave: false })
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

  it.each(PLANTED_FAILURES)('turns a client with %s off for the page, reports once and leaves other tabs alone', async (_plant, plant) => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const sdk = await load()
    // Another tab opts in through posthog-js's consent store, which every tab on the origin shares.
    const tab = otherTab(sdk)
    tab.opt_in_capturing({ captureEventName: false })
    const { client, guard, applied, capturingAtLoad } = await start(sdk, plant)
    expect(capturingAtLoad).toBe(true) // The shared opt-in reached this client: only its own failed state can stop it.
    expect(applied).toBe(false)
    // The failed client never writes the shared consent, so the other tab keeps capturing through both choices.
    choose(false)
    choose(true)
    expect(tab.is_capturing()).toBe(true)
    // That tab's opt-in does not revive the failed client either: nothing it captures leaves, sent at once, batched
    // or on pagehide through its unguarded retry queue.
    expect(client.is_capturing()).toBe(true)
    client.capture('failed-client-instant', {}, { send_instantly: true })
    client.capture('failed-client-batched')
    client._handle_unload()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect([sent('failed-client-instant'), sent('failed-client-batched')]).toEqual([0, 0])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBeInstanceOf(guard.PostHogConsentGuardError)
    expect(sentry.captureException.mock.calls[0][1]).toEqual({ tags: { posthog_js: client.version } })
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
    posthog.capture('provider-accepted', {}, { send_instantly: true })
    await vi.waitFor(() => expect(sent('provider-accepted')).toBe(1))

    act(() => choose(false))
    expect([posthog.is_capturing(), ready()]).toEqual([false, 'false'])
    posthog.capture('after-refusal', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-refusal')).toBe(0)
    expect(sentry.captureException).not.toHaveBeenCalled()
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
    // GlobalErrorBoundary's "Try again" mounts the provider again over the loaded client.
    view.unmount()
    render(page())
    expect(ready()).toBe('false')
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
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBe(planted)
  })

  it('turns PostHog off and reports a throw while applying a later choice', async () => {
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
    // The refusal never reached the SDK's consent, which still reads opted in: only the failed state stops it now.
    expect(client.is_capturing()).toBe(true)
    client.capture('after-failed-refusal', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-failed-refusal')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBe(planted)
  })
})

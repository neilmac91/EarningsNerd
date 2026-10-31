import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { gunzipSync } from 'node:zlib'
import { act, cleanup, render } from '@testing-library/react'
import type { PostHog, PostHogConfig } from 'posthog-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The consent guard (lib/posthogConsent.ts) on the real posthog-js builds, with no stand-in client: the package entry
 * (Vitest resolves `main`) and the `module` build that Next bundles into the app. Both rename the client's private
 * members. The guard once read `_send_retriable_request` and `_retryQueue` by name, so it threw "Cannot read
 * properties of undefined (reading 'bind')" before posthog.init on every page and production PostHog never started.
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

/** A real client, guarded and initialized as the provider does, with captures sent as they come or batched. */
async function start(sdk: Sdk) {
  const consent = await import('@/lib/browserConsent')
  const guard = await import('@/lib/posthogConsent')
  const privacy = await import('@/lib/posthogPrivacy')
  const client = new sdk.PostHog()
  clients.push(client)
  // Throws on main's guard: the build has no _send_retriable_request to bind.
  guard.installPostHogConsentGuard(client)
  unsubscribes.push(consent.subscribeCookiePreferences(() => guard.applyPostHogConsent(client)))
  // posthog-js swallows a throw from `loaded`, so the result is read after init rather than asserted inside it.
  let applied: boolean | undefined
  client.init(KEY, {
    ...privacy.postHogPrivacyConfig(client),
    api_host: INGEST, persistence: 'memory',
    autocapture: false, capture_pageview: false, capture_pageleave: false,
    disable_external_dependency_loading: true, advanced_disable_flags: true,
    opt_out_capturing_by_default: true, request_batching: true,
    loaded: (loaded) => {
      privacy.initializePostHogPrivacy(loaded)
      applied = guard.applyPostHogConsent(loaded)
    },
  } satisfies Partial<PostHogConfig>)
  return { client, guard, applied }
}

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

  it('keeps PostHog off and reports once when it cannot find a queue it guards', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const choose = await choices()
    choose(true)
    const sdk = await load()
    const guard = await import('@/lib/posthogConsent')
    const options = { api_host: INGEST, persistence: 'memory', disable_external_dependency_loading: true, advanced_disable_flags: true } as const
    // A returning visitor: the SDK persisted an opt-in on an earlier page, so the client starts capturing and only the
    // fail-closed opt-out can stop it.
    const earlier = new sdk.PostHog()
    earlier.init(KEY, options)
    earlier.opt_in_capturing({ captureEventName: false })
    await earlier.shutdown()
    const client = new sdk.PostHog()
    clients.push(client)
    guard.installPostHogConsentGuard(client)
    unsubscribes.push((await import('@/lib/browserConsent')).subscribeCookiePreferences(() => guard.applyPostHogConsent(client)))
    let applied: boolean | undefined
    let capturingAtLoad: boolean | undefined
    client.init(KEY, {
      ...options, autocapture: false, capture_pageview: false, capture_pageleave: false, opt_out_capturing_by_default: true,
      loaded: (loaded) => {
        capturingAtLoad = loaded.is_capturing()
        // Planted: an SDK that keeps its queues where the guard cannot see them.
        const { retry, batch } = guard.findPostHogQueues(loaded)!
        for (const key of Object.keys(loaded)) {
          const value = (loaded as unknown as Record<string, unknown>)[key]
          if (value === retry || value === batch) Object.defineProperty(loaded, key, { enumerable: false })
        }
        applied = guard.applyPostHogConsent(loaded)
      },
    })
    expect(capturingAtLoad).toBe(true)
    expect(applied).toBe(false)
    expect(client.is_capturing()).toBe(false)
    choose(false)
    choose(true) // A later allow on this page never opts in.
    expect(client.is_capturing()).toBe(false)
    client.capture('after-guard-failure', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-guard-failure')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toBeInstanceOf(guard.PostHogConsentGuardError)
    expect(sentry.captureException.mock.calls[0][1]).toEqual({ tags: { posthog_js: client.version } })
  })
})

describe('the provider on the real SDK', () => {
  it('starts PostHog under the guard after an allow, never before it, and stops it after a refusal', async () => {
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', KEY)
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_HOST', INGEST)
    const { default: posthog } = await import('posthog-js')
    const { PostHogProvider } = await import('@/app/posthog-provider')
    const choose = await choices()
    const view = render(<PostHogProvider><p>Page</p></PostHogProvider>)
    expect(posthog.__loaded).toBe(false)
    act(() => choose(false))
    expect(posthog.__loaded).toBe(false)
    expect(wire.calls).toEqual([])

    act(() => choose(true))
    expect(posthog.__loaded).toBe(true)
    expect(posthog.is_capturing()).toBe(true)
    posthog.capture('provider-accepted', {}, { send_instantly: true })
    await vi.waitFor(() => expect(sent('provider-accepted')).toBe(1))

    act(() => choose(false))
    expect(posthog.is_capturing()).toBe(false)
    posthog.capture('after-refusal', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-refusal')).toBe(0)
    expect(sentry.captureException).not.toHaveBeenCalled()
    view.unmount()
  })
})

describe('the provider when the guard cannot hold', () => {
  // A real client with one change planted, as a later posthog-js build might make it, under the app's provider.
  async function renderProvider(client: PostHog) {
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', KEY)
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_HOST', INGEST)
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.resetModules()
    vi.doMock('posthog-js', async (original) => ({ ...(await original<object>()), default: client }))
    const { PostHogProvider } = await import('@/app/posthog-provider')
    const choose = await choices()
    render(<PostHogProvider><p>Page</p></PostHogProvider>)
    return choose
  }
  afterEach(() => { vi.doUnmock('posthog-js') })

  it('never starts a client without _send_request, and reports that once', async () => {
    const { PostHog } = await import('posthog-js')
    const client = new PostHog()
    Object.defineProperty(client, '_send_request', { value: undefined })
    const choose = await renderProvider(client)
    act(() => choose(true))
    act(() => choose(false))
    act(() => choose(true))
    expect(client.__loaded).toBe(false)
    expect(wire.calls).toEqual([])
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toMatchObject({ name: 'PostHogConsentGuardError' })
  })

  it('keeps a loaded client off when its queues are out of the guard\'s sight, and reports that once', async () => {
    const { PostHog } = await import('posthog-js')
    const { findPostHogQueues } = await import('@/lib/posthogConsent')
    // Learn which fields this build keeps its queues in, then plant a client whose fields hide them from the guard.
    const probe = new PostHog()
    probe.init(KEY, { api_host: INGEST, persistence: 'memory', disable_external_dependency_loading: true, advanced_disable_flags: true })
    const { retry, batch } = findPostHogQueues(probe)!
    const fields = Object.keys(probe).filter(key => [retry, batch].includes((probe as unknown as Record<string, never>)[key]))
    await probe.shutdown()
    expect(fields).toHaveLength(2)
    const client = new PostHog()
    clients.push(client)
    for (const key of fields) Object.defineProperty(client, key, { value: undefined, writable: true, enumerable: false, configurable: true })
    const choose = await renderProvider(client)
    act(() => choose(true))
    expect(client.__loaded).toBe(true)
    expect(client.is_capturing()).toBe(false)
    act(() => choose(false))
    act(() => choose(true))
    expect(client.is_capturing()).toBe(false)
    client.capture('after-guard-failure', {}, { send_instantly: true })
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(sent('after-guard-failure')).toBe(0)
    expect(sentry.captureException).toHaveBeenCalledTimes(1)
    expect(sentry.captureException.mock.calls[0][0]).toMatchObject({ name: 'PostHogConsentGuardError' })
  })
})

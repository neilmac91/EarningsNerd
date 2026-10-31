import * as Sentry from '@sentry/nextjs'
import type { PostHog, QueuedRequestWithOptions } from 'posthog-js'
import { getCookiePreferences, getCookieWithdrawalRevision } from './browserConsent'

type ConsentRequest = QueuedRequestWithOptions & { __earningsnerdConsentGeneration?: number }
/** The client's retry queue and batch queue. posthog-js declares both classes but does not export them. */
export interface PostHogQueues {
  retry: NonNullable<PostHog['_retryQueue']>
  batch: NonNullable<PostHog['_requestQueue']>
}
interface Guard { attach: () => void; withdraw: () => void; syncWithdrawal: () => boolean; resume: () => void }

const guards = new WeakMap<PostHog, Guard>()
// Clients whose guard could not hold: analytics stays off on them for the rest of the page.
const failed = new WeakSet<PostHog>()

/** posthog-js no longer has a request path the consent guard holds. */
export class PostHogConsentGuardError extends Error {
  constructor(message: string) {
    super(`PostHog consent guard: ${message}`)
    this.name = 'PostHogConsentGuardError'
  }
}

export const browserAnalyticsAllowed = () => getCookiePreferences()?.analytics === true

const hasMethods = (value: unknown, names: readonly string[]) =>
  typeof value === 'object' && value !== null
  && names.every(name => typeof (value as Record<string, unknown>)[name] === 'function')

/**
 * Finds the client's two request queues by their shape. posthog-js's npm builds (the `module` entry Next bundles,
 * and `main`) rename the client's private members, so `_retryQueue`, `_requestQueue` and `_send_retriable_request`
 * are undefined at run time although its typings declare them. The queues' own methods, and the retry queue's
 * `_instance`, keep their names. `init` builds both queues; before it there are none. A loaded client without
 * exactly one of each throws, so an SDK that moves them fails loudly instead of leaving a queue unguarded.
 */
export function findPostHogQueues(client: PostHog): PostHogQueues | undefined {
  const retry: PostHogQueues['retry'][] = []
  const batch: PostHogQueues['batch'][] = []
  for (const key of Object.keys(client)) {
    const value: unknown = Object.getOwnPropertyDescriptor(client, key)?.value
    if (hasMethods(value, ['retriableRequest', 'resume', 'unload']) && (value as { _instance?: unknown })._instance === client) {
      retry.push(value as PostHogQueues['retry'])
    } else if (hasMethods(value, ['enqueue', 'enable', 'unload'])) {
      batch.push(value as PostHogQueues['batch'])
    }
  }
  if (!client.__loaded && !retry.length && !batch.length) return undefined
  if (retry.length !== 1 || batch.length !== 1) {
    throw new PostHogConsentGuardError(`expected one RetryQueue and one RequestQueue on the loaded client, found ${retry.length} and ${batch.length}`)
  }
  // Withdrawal clears the DOM-ready queue by its name, which every build keeps; renamed, that clear would do nothing.
  if (!Array.isArray(client.__request_queue)) throw new PostHogConsentGuardError('the loaded client has no __request_queue')
  return { retry: retry[0], batch: batch[0] }
}

/**
 * posthog-js 1.440.0 runs before_send at capture, not when queued/retried requests leave. Its RetryQueue calls
 * sendRequest directly, bypassing client._send_request. Every request leaves through client._send_request (a name
 * every build keeps) or the retry queue's retriableRequest (batches, unbatched captures and retries alike), so the
 * guard wraps those two and finds the queue by its shape, never by a private name the build renames. It throws a
 * PostHogConsentGuardError when it cannot hold; applyPostHogConsent then turns the client off (failPostHogClosed).
 * Gated against the real builds by tests/unit/posthogConsentGuard.spec.tsx and tests/e2e/telemetry-network.spec.ts,
 * and every name it reaches by tests/unit/posthogShippedMembers.spec.ts; rerun them on SDK upgrades. The generation
 * is request metadata, never event data/headers. Late failures retain it when the SDK copies request options for
 * retry, so a new opt-in cannot revive withdrawn work.
 */
export function installPostHogConsentGuard(client: PostHog): void {
  const existing = guards.get(client)
  if (existing) { existing.attach(); return }
  if (typeof client._send_request !== 'function') throw new PostHogConsentGuardError('the client has no _send_request')
  let generation = 0
  let withdrawalRevision = getCookieWithdrawalRevision()
  let discarding = false
  let queues: PostHogQueues | undefined
  const guardedRetries = new WeakSet<object>()
  const permitted = (options: ConsentRequest) => {
    options.__earningsnerdConsentGeneration ??= generation
    syncWithdrawal()
    return !discarding && browserAnalyticsAllowed() && options.__earningsnerdConsentGeneration === generation
  }
  const dropped = (options: QueuedRequestWithOptions) => {
    // Terminal denial: do not report a successful delivery or schedule another retry.
    // This is a local drop, not an HTTP response from the provider.
    options.callback?.({ statusCode: 403 })
  }
  const attach = () => {
    const found = findPostHogQueues(client)
    if (!found) return
    const { retry } = found
    if (!guardedRetries.has(retry)) {
      const send = retry.retriableRequest.bind(retry)
      retry.retriableRequest = (options, transport) => {
        if (!permitted(options)) { dropped(options); return }
        send(options, transport)
      }
      guardedRetries.add(retry)
    }
    queues = found
  }
  const send = client._send_request.bind(client)
  client._send_request = options => {
    if (!permitted(options)) { dropped(options); return }
    send(options)
  }
  const withdraw = () => {
    generation += 1
    discarding = true
    try {
      // These SDK drain methods empty both queues. Our dispatch guards drop their payloads;
      // they must never be called unguarded as an opt-out cleanup (unload normally sends).
      client.__request_queue = []
      queues?.batch.unload()
      queues?.retry.unload()
    } finally { discarding = false }
  }
  const syncWithdrawal = () => {
    const latestRevision = getCookieWithdrawalRevision()
    if (latestRevision === withdrawalRevision) return false
    withdrawalRevision = latestRevision
    withdraw()
    return true
  }
  guards.set(client, { attach, withdraw, syncWithdrawal, resume: () => queues?.retry.resume() })
  attach()
}

/** Whether this client's guard has failed: it sends no events for the rest of the page (posthogPrivacy's before_send). */
export const postHogGuardFailed = (client: PostHog) => failed.has(client)

/**
 * Turns this client off for the rest of the page and reports why, once. Without its guard a withdrawal could not stop
 * queued or retried requests, so a failed client sends no events: posthogPrivacy's before_send drops every one, per
 * client. posthog-js's own opt-out is not used for this. All tabs share that store, so another tab's opt-in would
 * revive the failed client, and the failed client's opt-out would switch healthy tabs off. Nor does it stop silently:
 * the report is a Sentry issue. #1552's guard threw before init and left only a console line, which Sentry kept as a
 * log and raised no issue for.
 */
export function failPostHogClosed(client: PostHog, error: unknown): void {
  if (failed.has(client)) return
  failed.add(client)
  console.error('PostHog: analytics is off on this page', error)
  try {
    Sentry.captureException(error, { tags: { posthog_js: String(client.version) } })
  } catch {
    /* monitoring must never break the app */
  }
}

/**
 * Applies the visitor's current choice under the guard; before init it only installs the guard. Returns false, with
 * the client turned off and the failure reported, when the guard cannot hold (failPostHogClosed). Never throws for
 * that. A failed client's SDK consent is left alone, since every tab shares it.
 */
export function applyPostHogConsent(client: PostHog): boolean {
  if (failed.has(client)) return false
  try {
    installPostHogConsentGuard(client)
  } catch (error) {
    failPostHogClosed(client, error)
    return false
  }
  if (!client.__loaded) return true
  const guard = guards.get(client)!
  // Invalidate an intervening cross-tab refusal before applying the latest allow. Reading only
  // today's storage value would miss deny -> allow events delivered together to a suspended tab.
  const withdrew = guard.syncWithdrawal()
  client.stopSessionRecording()
  if (browserAnalyticsAllowed()) {
    guard.resume()
    client.opt_in_capturing({ captureEventName: false })
  } else {
    // Drain even if the SDK's independent persistence throws while storing its opt-out.
    try { client.opt_out_capturing() } finally { if (!withdrew) guard.withdraw() }
  }
  return true
}

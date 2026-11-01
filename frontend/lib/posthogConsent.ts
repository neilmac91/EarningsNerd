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
 * sendRequest directly, bypassing client._send_request. Every request that carries data leaves through
 * client._send_request (a name every build keeps) or the retry queue's retriableRequest (batches, unbatched captures
 * and retries alike), so the guard wraps those two and finds the queue by its shape, never by a private name the build
 * renames. The scripts posthog-js loads (its remote configuration and the extensions that configuration enables) go
 * around both and carry no event data. The guard throws a PostHogConsentGuardError when it cannot hold;
 * applyPostHogConsent then turns the client off (failPostHogClosed).
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
    // A failed client sends nothing more through either wrapper: queued batches, retries, flags, remote configuration.
    return !discarding && !failed.has(client) && browserAnalyticsAllowed() && options.__earningsnerdConsentGeneration === generation
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

/** Whether this client's guard has failed: it is then off for the rest of the page (failPostHogClosed). */
export const postHogGuardFailed = (client: PostHog) => failed.has(client)

/**
 * posthog-js keeps its consent in a store every tab on the origin shares, and reset() clears it. A failed client keeps
 * that store at the visitor's choice, as every healthy tab does, so it never switches another tab off or leaves the
 * store cleared. Its own capturing never depends on the store: its is_capturing stays false.
 */
const mirrorChoice = (client: PostHog) => {
  if (!client.__loaded) return
  try {
    if (browserAnalyticsAllowed()) client.opt_in_capturing({ captureEventName: false })
    else client.opt_out_capturing()
  } catch {
    // The SDK's consent persistence can throw. The failed client is off either way.
  }
}

/**
 * Turns this client off for the rest of the page and reports why, once. Without its guard a withdrawal could not stop
 * queued or retried requests, so after the failure nothing more leaves through either wrapper and the client loads no
 * further script. That holds per client, in three layers:
 * - its own is_capturing reads false (a public name every build keeps), so posthog-js captures nothing for it;
 * - posthogPrivacy's before_send drops any event that still arrives;
 * - the guard's wrappers drop every request, flags and remote configuration included, and the client's script loading
 *   is switched off, so its remote configuration falls back from a script tag to a request the wrappers drop.
 * posthog-js's own opt-out is not relied on, since every tab shares that store (mirrorChoice). posthog-js still writes
 * the client's own storage on identity and session changes; lib/analytics.ts identifies only while analytics is
 * allowed. A request already on the wire is not recalled, and a script loaded before the failure keeps running. Nor
 * does the failure pass silently: the report is a Sentry issue. #1552's guard threw before init and left only a
 * console line, which Sentry kept as a log, raising no issue.
 */
export function failPostHogClosed(client: PostHog, error: unknown): void {
  if (failed.has(client)) return
  failed.add(client)
  client.is_capturing = () => false
  try {
    // A public option, read each time posthog-js loads a script. The provider never initializes a failed client, so
    // one that has not loaded has nothing to load.
    if (client.__loaded) client.set_config({ disable_external_dependency_loading: true })
  } catch {
    // set_config sets the option before it updates the SDK's persistence, which can throw; the other layers hold
    // either way.
  }
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
 * that. A failed client only mirrors the choice into the store every tab shares (mirrorChoice).
 */
export function applyPostHogConsent(client: PostHog): boolean {
  if (failed.has(client)) {
    mirrorChoice(client)
    return false
  }
  try {
    installPostHogConsentGuard(client)
  } catch (error) {
    failPostHogClosed(client, error)
    mirrorChoice(client)
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

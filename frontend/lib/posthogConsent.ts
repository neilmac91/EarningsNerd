import type { PostHog, QueuedRequestWithOptions } from 'posthog-js'
import { getCookiePreferences, getCookieWithdrawalRevision } from './browserConsent'

type ConsentRequest = QueuedRequestWithOptions & { __earningsnerdConsentGeneration?: number }
const guards = new WeakMap<PostHog, { withdraw: () => void; attachRetry: () => void; syncWithdrawal: () => boolean }>()

export const browserAnalyticsAllowed = () => getCookiePreferences()?.analytics === true

/**
 * posthog-js 1.438.12 runs before_send at capture, not when queued/retried requests leave.
 * Its RetryQueue calls sendRequest directly, bypassing client._send_request. Keep the three
 * typed SDK entry points here, with real-SDK transport tests; recheck them on SDK upgrades.
 * The generation is request metadata, never event data/headers. Late failures retain it when
 * the SDK copies request options for retry, so a new opt-in cannot revive withdrawn work.
 */
export function installPostHogConsentGuard(client: PostHog): void {
  const existing = guards.get(client)
  if (existing) { existing.attachRetry(); return }
  let generation = 0
  let withdrawalRevision = getCookieWithdrawalRevision()
  let discarding = false
  let guardedRetry: PostHog['_retryQueue']
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
  const attachRetry = () => {
    const queue = client._retryQueue
    if (!queue || queue === guardedRetry) return
    guardedRetry = queue
    const send = queue.retriableRequest.bind(queue)
    queue.retriableRequest = (options, transport) => {
      if (!permitted(options)) { dropped(options); return }
      send(options, transport)
    }
  }
  const send = client._send_request.bind(client)
  client._send_request = options => {
    if (!permitted(options)) { dropped(options); return }
    send(options)
  }
  const retriable = client._send_retriable_request.bind(client)
  client._send_retriable_request = (options, transport) => {
    attachRetry()
    if (!permitted(options)) { dropped(options); return }
    retriable(options, transport)
  }
  const withdraw = () => {
    generation += 1
    discarding = true
    try {
      // These SDK drain methods empty both queues. Our dispatch guards drop their payloads;
      // they must never be called unguarded as an opt-out cleanup (unload normally sends).
      client.__request_queue = []
      client._requestQueue?.unload()
      client._retryQueue?.unload()
    } finally { discarding = false }
  }
  const syncWithdrawal = () => {
    const latestRevision = getCookieWithdrawalRevision()
    if (latestRevision === withdrawalRevision) return false
    withdrawalRevision = latestRevision
    withdraw()
    return true
  }
  guards.set(client, { attachRetry, withdraw, syncWithdrawal })
  attachRetry()
}

export function applyPostHogConsent(client: PostHog): void {
  installPostHogConsentGuard(client)
  if (!client.__loaded) return
  // Invalidate an intervening cross-tab refusal before applying the latest allow. Reading only
  // today's storage value would miss deny -> allow events delivered together to a suspended tab.
  const withdrew = guards.get(client)?.syncWithdrawal()
  client.stopSessionRecording()
  if (browserAnalyticsAllowed()) {
    client._retryQueue?.resume()
    client.opt_in_capturing({ captureEventName: false })
  } else {
    // Drain even if the SDK's independent persistence throws while storing its opt-out.
    try { client.opt_out_capturing() } finally { if (!withdrew) guards.get(client)?.withdraw() }
  }
}

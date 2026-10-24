/** Browser analytics only. API account events follow their separate policy (D-051). */
export interface CookiePreferences {
  essential: boolean
  analytics: boolean
  /** Retained for migration; recording is unavailable in this release. */
  sessionRecording: boolean
  timestamp: string
  version?: number
}

// Version 3 removes the recording choice and validates the stored schema. Earlier allows need
// a fresh choice; a well-formed refusal remains a refusal, including the pre-versioned schema.
export const CONSENT_VERSION = 3
const STORAGE_KEY = 'cookie_consent'
const CHANGE_EVENT = 'cookieConsentChanged'
const CHANNEL = 'earningsnerd-browser-consent'
let unsavedChoice: CookiePreferences | null | undefined
let channel: BroadcastChannel | undefined
let subscribers = 0
let withdrawalRevision = 0

/** Historical withdrawal edges invalidate queued work even when shared storage already holds a later allow. */
export const getCookieWithdrawalRevision = () => withdrawalRevision

function parseChoice(value: unknown): CookiePreferences | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const choice = value as Record<string, unknown>
  if (Object.keys(choice).some(key => !['essential', 'analytics', 'sessionRecording', 'timestamp', 'version'].includes(key))) return null
  if (choice.essential !== true || typeof choice.analytics !== 'boolean' || typeof choice.sessionRecording !== 'boolean') return null
  if (typeof choice.timestamp !== 'string' || !Number.isFinite(Date.parse(choice.timestamp))) return null
  if (choice.version !== undefined && (!Number.isInteger(choice.version) || (choice.version as number) < 1)) return null
  if (choice.analytics && (choice.version !== CONSENT_VERSION || choice.sessionRecording !== false)) return null
  return {
    essential: true, analytics: choice.analytics, sessionRecording: false, timestamp: choice.timestamp,
    ...(typeof choice.version === 'number' ? { version: choice.version } : {}),
  }
}

function parseStored(value: string | null): CookiePreferences | null {
  try { return value ? parseChoice(JSON.parse(value)) : null } catch { return null }
}

export function getCookiePreferences(): CookiePreferences | null {
  if (typeof window === 'undefined') return null
  if (unsavedChoice !== undefined) return unsavedChoice ? { ...unsavedChoice } : null
  try { return parseStored(localStorage.getItem(STORAGE_KEY)) } catch { return null }
}

function notify(withdrawn = false) {
  if (withdrawn) withdrawalRevision += 1
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: getCookiePreferences() }))
}

function storageChanged(event: StorageEvent) {
  try {
    if (event.storageArea !== null && event.storageArea !== localStorage) return
  } catch { /* Deny if browser storage itself has become inaccessible. */ }
  if (event.key !== null && event.key !== STORAGE_KEY) return
  // A failed refusal/clear is a fail-closed latch until an explicit choice in this document.
  // Delayed grant events cannot remove it and revive the stale allow still left on disk.
  if (unsavedChoice?.analytics === true) unsavedChoice = undefined
  // Preserve the historical edge separately from the latest choice. Another tab may already
  // have saved deny -> allow before we handle either event: queued pre-denial work must still
  // be discarded. Event values can invalidate work, but only the current validated store allows.
  notify(event.key === null || parseStored(event.newValue)?.analytics !== true)
}

/** One subscription for the dialog, PostHog and Vercel; event payloads never grant permission. */
export function subscribeCookiePreferences(update: () => void): () => void {
  if (subscribers++ === 0) {
    window.addEventListener('storage', storageChanged)
    try {
      channel = new BroadcastChannel(CHANNEL)
      channel.onmessage = event => {
        // Broadcast refusal/clear even if storage writes failed. Allows travel only through
        // successful shared storage, never through an unvalidated event or channel payload.
        if (event.data !== 'withdraw') return
        unsavedChoice = { essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString(), version: CONSENT_VERSION }
        notify(true)
      }
    } catch { /* Storage events still synchronize browsers without BroadcastChannel. */ }
  }
  window.addEventListener(CHANGE_EVENT, update)
  return () => {
    window.removeEventListener(CHANGE_EVENT, update)
    if (--subscribers === 0) {
      window.removeEventListener('storage', storageChanged)
      channel?.close()
      channel = undefined
    }
  }
}

export function saveCookiePreferences(preferences: CookiePreferences): { preferences: CookiePreferences; persisted: boolean } {
  const choice: CookiePreferences = {
    essential: true,
    analytics: preferences.analytics === true,
    sessionRecording: false,
    timestamp: new Date().toISOString(),
    version: CONSENT_VERSION,
  }
  if (typeof window === 'undefined') return { preferences: choice, persisted: false }
  // Apply in memory before touching fallible storage or notifying SDKs. A failed refusal must
  // never fall back to the previous stored allow in capture/send hooks.
  unsavedChoice = choice
  let persisted = false
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(choice))
    persisted = true
    unsavedChoice = undefined
  } catch {
    // Best effort removal of a stale allow. Failure still cannot undo this document's choice.
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* Keep the in-memory choice. */ }
  }
  notify(!choice.analytics)
  if (!choice.analytics && !persisted) {
    try { channel?.postMessage('withdraw') } catch { /* Current document remains opted out. */ }
  }
  return { preferences: choice, persisted }
}

export function clearCookiePreferences(): boolean {
  if (typeof window === 'undefined') return false
  unsavedChoice = null
  let persisted = false
  try { localStorage.removeItem(STORAGE_KEY); persisted = true; unsavedChoice = undefined } catch { /* Remain off in memory. */ }
  notify(true)
  if (!persisted) {
    try { channel?.postMessage('withdraw') } catch { /* Current document remains opted out. */ }
  }
  return persisted
}

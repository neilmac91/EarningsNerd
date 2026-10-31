import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let store: typeof import('@/lib/browserConsent')
const key = 'cookie_consent'
const allowed = () => ({ essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-23T12:00:00.000Z', version: store.CONSENT_VERSION })
let unsubscribe: (() => void) | undefined

beforeEach(async () => {
  vi.resetModules()
  localStorage.clear()
  store = await import('@/lib/browserConsent')
})
afterEach(() => { unsubscribe?.(); unsubscribe = undefined; vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear() })

describe('browser consent is validated, immediate and synchronized', () => {
  it.each([
    null, [], 'true', true, {},
    { analytics: 'false' }, { analytics: 'true' }, { analytics: 1 }, { analytics: null },
    { sessionRecording: 'false' }, { sessionRecording: true }, { essential: 'true' },
    { essential: false }, { timestamp: null }, { timestamp: 'not a date' },
    { version: '3' }, { version: -1 }, { version: 3.1 }, { extra: true },
  ])('never grants permission to malformed JSON %j', value => {
    const candidate = value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0 ? { ...allowed(), ...value } : value
    localStorage.setItem(key, JSON.stringify(candidate))
    expect(store.getCookiePreferences()).toBeNull()
  })

  it('accepts only the current allow; preserves valid prior refusals while disabling legacy recording', () => {
    localStorage.setItem(key, JSON.stringify(allowed()))
    expect(store.getCookiePreferences()?.analytics).toBe(true)
    for (const version of [undefined, 1, 2]) {
      localStorage.setItem(key, JSON.stringify({ ...allowed(), version }))
      expect(store.getCookiePreferences()).toBeNull()
      localStorage.setItem(key, JSON.stringify({ ...allowed(), version, analytics: false, sessionRecording: true }))
      expect(store.getCookiePreferences()).toMatchObject({ analytics: false, sessionRecording: false })
    }
  })

  it.each(['save', 'clear'] as const)('%s immediately withdraws and notifies even when both storage writes and removal throw', action => {
    localStorage.setItem(key, JSON.stringify(allowed()))
    const observed: unknown[] = []
    unsubscribe = store.subscribeCookiePreferences(() => observed.push(store.getCookiePreferences()))
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Unavailable', 'QuotaExceededError') })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new DOMException('Unavailable', 'SecurityError') })
    const result = action === 'save' ? store.saveCookiePreferences({ ...allowed(), analytics: false }).persisted : store.clearCookiePreferences()
    expect(result).toBe(false)
    expect(JSON.parse(localStorage.getItem(key)!)).toEqual(allowed()) // The old allow is still on disk.
    expect(store.getCookiePreferences()?.analytics).not.toBe(true)
    expect(observed).toHaveLength(1)
    expect((observed[0] as { analytics?: boolean } | null)?.analytics).not.toBe(true)
    // A queued storage notification for the earlier grant arrives after the failed refusal.
    window.dispatchEvent(new StorageEvent('storage', { key, storageArea: localStorage, newValue: JSON.stringify(allowed()) }))
    expect(store.getCookiePreferences()?.analytics).not.toBe(true)
    expect((observed.at(-1) as { analytics?: boolean } | null)?.analytics).not.toBe(true)
  })

  it.each(['refusal', 'remove', 'clear', 'malformed'] as const)('synchronizes another tab’s %s, ignoring event details as authority', change => {
    localStorage.setItem(key, JSON.stringify(allowed()))
    const update = vi.fn()
    unsubscribe = store.subscribeCookiePreferences(update)
    if (change === 'refusal') localStorage.setItem(key, JSON.stringify({ ...allowed(), analytics: false }))
    else if (change === 'malformed') localStorage.setItem(key, JSON.stringify({ ...allowed(), analytics: 'false' }))
    else localStorage.removeItem(key)
    window.dispatchEvent(new StorageEvent('storage', { key: change === 'clear' ? null : key, storageArea: localStorage, newValue: JSON.stringify(allowed()) }))
    expect(update).toHaveBeenCalledOnce()
    expect(store.getCookiePreferences()?.analytics).not.toBe(true)
    window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: allowed() }))
    expect(store.getCookiePreferences()?.analytics).not.toBe(true)
  })

  it('normalizes the saved choice without mutating caller state or enabling replay', () => {
    const input = { ...allowed(), sessionRecording: true }
    expect(store.saveCookiePreferences(input)).toMatchObject({ persisted: true, preferences: { analytics: true, sessionRecording: false } })
    expect(input.sessionRecording).toBe(true)
    expect(store.getCookiePreferences()?.sessionRecording).toBe(false)
  })

  it.each(['deny', 'remove', 'clear', 'malformed'] as const)('retains the historical %s edge when shared storage already contains a later allow', change => {
    localStorage.setItem(key, JSON.stringify(allowed()))
    const observed: Array<{ allowed: boolean; withdrawal: number }> = []
    unsubscribe = store.subscribeCookiePreferences(() => observed.push({
      allowed: store.getCookiePreferences()?.analytics === true,
      withdrawal: store.getCookieWithdrawalRevision(),
    }))
    const newValue = change === 'deny' ? JSON.stringify({ ...allowed(), analytics: false })
      : change === 'malformed' ? JSON.stringify({ ...allowed(), analytics: 'false' }) : null
    window.dispatchEvent(new StorageEvent('storage', { key: change === 'clear' ? null : key, storageArea: localStorage, newValue }))
    window.dispatchEvent(new StorageEvent('storage', { key, storageArea: localStorage, newValue: JSON.stringify(allowed()) }))
    expect(observed).toEqual([{ allowed: true, withdrawal: 1 }, { allowed: true, withdrawal: 1 }])
  })

  it.each(['broadcast-first', 'storage-first'] as const)('keeps a broadcast refusal latched with delayed grant events (%s)', order => {
    let receive: ((event: { data: unknown }) => void) | undefined
    vi.stubGlobal('BroadcastChannel', class {
      set onmessage(callback: typeof receive) { receive = callback }
      close() {}
      postMessage() {}
    })
    localStorage.setItem(key, JSON.stringify(allowed()))
    unsubscribe = store.subscribeCookiePreferences(() => {})
    const delayedGrant = () => window.dispatchEvent(new StorageEvent('storage', { key, storageArea: localStorage, newValue: JSON.stringify(allowed()) }))
    if (order === 'storage-first') delayedGrant()
    receive?.({ data: 'withdraw' })
    delayedGrant()
    expect(store.getCookiePreferences()?.analytics).toBe(false)
    // An explicit choice here, rather than an unsequenced storage event, can release the latch.
    expect(store.saveCookiePreferences(allowed()).persisted).toBe(true)
    expect(store.getCookiePreferences()?.analytics).toBe(true)
  })
})

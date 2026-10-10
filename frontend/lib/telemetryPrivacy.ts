// Shared by browser analytics and Sentry's browser/server collection boundaries.
const REDACTED = '[REDACTED]'
const CREDENTIAL_NAMES = /^(?:token|accesstoken|refreshtoken|idtoken|authorization|password|secret|apikey|code|invite|invitetoken)$/i
const QUERY_CREDENTIAL = /([?&#](?:token|access_token|refresh_token|id_token|authorization|password|secret|api_key|code|invite|invite_token)=)[^&#\s"'<>]*/gi
const AUTH_PATH = /^\/(?:login|register|forgot-password|reset-password|verify-email|check-email|auth)(?:\/|$)/i

function isCredentialName(name: string): boolean {
  return CREDENTIAL_NAMES.test(name.replace(/[$_-]/g, ''))
}

/** Telemetry needs the page path, never URL query parameters or fragments. */
export function sanitizeTelemetryUrl(value: string): string {
  try {
    const url = new URL(value, 'https://telemetry.invalid')
    // Only parse URL-shaped strings; error messages are handled by the text boundary below.
    if (!/^(?:https?:\/\/|\/|\?|#)/i.test(value) || /\s/.test(value)) {
      return value.replace(QUERY_CREDENTIAL, `$1${REDACTED}`)
    }
    url.search = ''
    url.hash = ''
    if (/^https?:\/\//i.test(value)) return url.href
    if (value.startsWith('//')) return `//${url.host}${url.pathname}${url.search}`
    if (value.startsWith('?')) return url.search
    if (value.startsWith('#')) return ''
    return `${url.pathname}${url.search}`
  } catch {
    return value.replace(QUERY_CREDENTIAL, `$1${REDACTED}`)
  }
}

export function sanitizeTelemetryText(value: string): string {
  if (/^(?:https?%3a|%2f)/i.test(value)) {
    try {
      const decoded = decodeURIComponent(value)
      const clean = sanitizeTelemetryText(decoded)
      return clean === decoded ? value : encodeURIComponent(clean)
    } catch { /* Fall back to redacting any readable query parameters. */ }
  }
  if (/^(?:https?:\/\/|\/|\?|#)/i.test(value) && !/\s/.test(value)) {
    return sanitizeTelemetryUrl(value)
  }
  return value
    .replace(/https?:\/\/[^\s"'<>]+/gi, sanitizeTelemetryUrl)
    .replace(/\/[^\s"'<>?#]*[?#][^\s"'<>]*/g, sanitizeTelemetryUrl)
    .replace(QUERY_CREDENTIAL, `$1${REDACTED}`)
    .replace(/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi, `Bearer ${REDACTED}`)
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, REDACTED)
}

/** Recursion includes arrays, person properties, persisted attribution and error contexts. */
export function sanitizeTelemetry<T>(value: T, preservePostHogProjectToken = false): T {
  const seen = new WeakMap<object, unknown>()
  const visit = (item: unknown, path: string[]): unknown => {
    if (typeof item === 'string') return sanitizeTelemetryText(item)
    if (!item || typeof item !== 'object' || item instanceof Date) return item
    if (seen.has(item)) return seen.get(item)
    if (Array.isArray(item)) {
      const result: unknown[] = []
      seen.set(item, result)
      item.forEach((entry, index) => result.push(visit(entry, [...path, String(index)])))
      return result
    }
    const result: Record<string, unknown> = {}
    seen.set(item, result)
    for (const [name, entry] of Object.entries(item)) {
      // PostHog's properties.token is the public ingestion key, not an auth credential.
      const projectToken = preservePostHogProjectToken && path.length === 1 && path[0] === 'properties' && name === 'token'
      Object.defineProperty(result, name, {
        value: projectToken ? entry : isCredentialName(name) ? REDACTED : visit(entry, [...path, name]),
        enumerable: true,
        writable: true,
        configurable: true,
      })
    }
    return result
  }
  return visit(value, []) as T
}

export function isCredentialLocation(value: string): boolean {
  try {
    const url = new URL(value, 'https://telemetry.invalid')
    return AUTH_PATH.test(url.pathname) || [...url.searchParams.keys()].some(isCredentialName) ||
      /(?:^#|[?&#])(?:token|access_token|refresh_token|id_token|code)=/i.test(url.hash)
  } catch {
    return true
  }
}

// A recorder may queue compressed snapshots. Once this document touches an auth route, never
// resume it after a SPA transition: only a fresh safe document can start a new recording.
let recordingBlocked = false
const recordingBlockListeners = new Set<() => void>()

export function protectTelemetryRoute(url: string): void {
  if (!recordingBlocked && isCredentialLocation(url)) {
    recordingBlocked = true
    recordingBlockListeners.forEach((listener) => {
      try { listener() } catch { /* The snapshot boundary still drops data if stopping fails. */ }
    })
  }
}

export function canRecordTelemetry(): boolean {
  if (typeof window === 'undefined') return false
  protectTelemetryRoute(window.location.href)
  return !recordingBlocked
}

export function onRecordingBlocked(listener: () => void): () => void {
  recordingBlockListeners.add(listener)
  return () => { recordingBlockListeners.delete(listener) }
}

/** Install before SDKs: covers browser history/popstate as well as Next router transitions. */
export function installTelemetryNavigationGuard(): () => void {
  const checkLocation = () => protectTelemetryRoute(window.location.href)
  checkLocation()
  const originalPush = window.history.pushState
  const originalReplace = window.history.replaceState
  const guard = (original: History['pushState']): History['pushState'] => function (this: History, data, unused, url) {
    if (url != null) protectTelemetryRoute(new URL(String(url), window.location.href).href)
    return original.call(this, data, unused, url)
  }
  const push = guard(originalPush)
  const replace = guard(originalReplace)
  window.history.pushState = push
  window.history.replaceState = replace
  window.addEventListener('popstate', checkLocation, true)
  window.addEventListener('hashchange', checkLocation, true)
  window.addEventListener('pageshow', checkLocation, true)
  return () => {
    if (window.history.pushState === push) window.history.pushState = originalPush
    if (window.history.replaceState === replace) window.history.replaceState = originalReplace
    window.removeEventListener('popstate', checkLocation, true)
    window.removeEventListener('hashchange', checkLocation, true)
    window.removeEventListener('pageshow', checkLocation, true)
  }
}

/**
 * The way back to the cookie settings after a first choice. The consent bar shows only until a visitor chooses, and
 * /privacy's withdrawal sentence says consent can be withdrawn "through our cookie consent banner or settings", so
 * the site footer's "Cookie settings" (components/Footer.tsx) asks the one mounted CookieConsent to open its settings
 * dialog, through a window event as CookieConsent's own `cookieConsentChanged` travels the other way. React-free, so
 * the footer does not import the consent component to reach it.
 */
export const OPEN_COOKIE_SETTINGS_EVENT = 'openCookieSettings'

export function openCookieSettings(): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(OPEN_COOKIE_SETTINGS_EVENT))
}
